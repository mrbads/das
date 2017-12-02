import socket, threading, select, json
from common.network_util import read_message, pack, TCPConnectionError
from common.constants import *
from common.command import Command

import logging
logger = logging.getLogger("sys." + __name__.split(".")[-1])


class ClientTransport:
    def __init__(self, game, port=TRANSPORT.port, host=TRANSPORT.host):
        self.game = game
        self.id = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

        logger.info("Connection established to port Server@{}:{}".format(host, port))

    def check_recv(self):
        while self.game.up:
            socket_list = [self.sock]
            read_sockets, write_sockets, error_sockets = select.select(socket_list, [], [])
            for sock in read_sockets:
                # incoming message from remote server
                try:
                    data = read_message(sock)
                except TCPConnectionError as e:
                    logger.error(str(e))
                    self.shutdown()
                    return

                if not data:
                    logger.error('\nDisconnected from server')
                    self.shutdown()
                    return
                else:
                    # TODO: double check if that's the correct behaviour
                    # execute all commands from server
                    json_data = json.loads(data)
                    if json_data['type'] == MSG_TYPE.COMMAND:
                        logger.debug("received message {}".format(data[:GLOBAL.MAX_LOG_LENGTH]))
                        command_obj = Command.from_json(json_data['payload'])
                        command_obj.apply(self.game)
                    else:
                        logger.warning("Unknown message type received")

    def listen(self):
        transport_thread = threading.Thread(target=self.check_recv)
        transport_thread.daemon = True
        transport_thread.start()

    def setup_client(self):
        """
        This BLOCKING function will be called in the creation of each client. It will synchronously wait for the server
        to sent the game map and clientId
        :return: map and id
        """
        data_id = read_message(self.sock)
        json_id = json.loads(data_id)
        if json_id['type'] == MSG_TYPE.INIT:
            id = json_id['payload']
        else:
            raise BaseException("Failure in initializing game with the server")

        # wait until i receive my own join message. This is needed to get the initial state
        while True:
            data_join = read_message(self.sock)
            json_join = json.loads(data_join)
            command_join = json.loads(json_join['payload'])
            if command_join["type"] == "NewPlayerCommand" and command_join['client_id'] == id:
                return id, command_join['initial_state']

    def send_data(self, data, type=None):
        """
        send data to server
        :param data: string data to be sent
        :return:
        """
        try:
            if not type is None:
                data = json.dumps({"type": type, "payload": data})

            logger.debug("sending {}".format(data))
            self.sock.sendall(pack(data))
        except Exception as e:
            logger.error("Error while sending data " + str(e))


    def shutdown(self):
        self.game.up = False
        self.sock.close()



