import datetime
import socket
import socketserver
import time
from typing import Optional, Tuple, List, TypedDict

from poker_game.poker import game_protocol
from poker_game.poker.game_protocol import out_game_protocol
from tcp_server.enums.errors import GameErrorsCode
from tcp_server.logger import logger
from user import models
from user.models import User
from poker_game.models import UserTransaction, Game, Round, Table, PlayerGame
from poker_game.textchoices import TransactionTypeChoice
from tcp_server.enums import commands
from poker_game.poker.game import PokerGame
from tcp_server.tcp_game_connection_protocol import GameConnectionProtocol

import sys


def debug(message: str):
    return logger.debug(message)


def info(message):
    return logger.info(message)


class TCPGameConnection:
    def __init__(self, user: User, connection: socketserver.BaseRequestHandler):
        self.connection = connection
        self.user = user


class TableConnections(TypedDict):
    table_key: str
    connections: List[TCPGameConnection]


class TCPGameHandler:
    connections: List[TCPGameConnection] = []
    table_connections: List[TableConnections] = []
    protocol = GameConnectionProtocol
    game = PokerGame()
    START_NEW_GAME_DELAY = 7
    AUTO_FOLD_TIME_OUT = 1

    @classmethod
    def on_authenticate_user(cls, *args):
        """
        :param args:
        :return:
        """
        user_id = args[0]
        message = out_game_protocol.user_auth_message()
        cls.send_message_through_user(user_id, message)

    @classmethod
    def on_join_game(cls, *args):
        """
        Receive message on joing game
        :param args:
        :return:
        """
        user_id, command_name = args
        data = cls.protocol(command_name).parse_join_game_data()
        table_key = data.get('table_key')
        user = User.objects.get(id=user_id)
        valid, error_code = cls._validate_join(
            user=user,
        )
        if not valid:
            return cls._send_error(
                user_id=user.id,
                error_code=error_code
            )

        cls.add_connection_to_table(user, table_key)
        count_players, exist_on_game = cls.game.connect_player_to_table(table_key=table_key, user=user)
        print(f'count_players: {count_players}')
        print(f'exist_on_game: {exist_on_game}')
        current_game = cls.game.get_current_game(table_key=table_key)
        print(f'current_game: {current_game}')
        start_game = not current_game and count_players >= 2
        if not start_game and current_game and count_players == 2:
            print('start game over')
            start_game = True
        print(f'start_game: {start_game}')

        if start_game:
            current_round = cls.game.start_game(table_key=table_key)
            cls.game.setup_start_game_bets(round_model=current_round)

        cls._send_table_status(table_key=table_key)

    @classmethod
    def on_table_status(cls, *args):
        """
        Parse game info command
        :param args:
        :return:
        """
        protocol = cls.protocol(args[1])
        parsed_data = protocol.parse_join_game_data()
        user_id = args[0]
        table_key = parsed_data.get('table_key')
        cls._send_table_status_to_user(
            table_key=table_key,
            user_id=user_id
        )

    @classmethod
    def on_bet(cls, *args):
        """
        On user bet event
        :param args: 
        :return: 
        """""
        protocol = cls.protocol(args[1])
        amount = int(protocol.parse_bet().get('amount'))
        user_id = args[0]
        success, error, round_model, is_last_turn = cls.game.bet(user_id, amount)

        if not success:
            return cls._send_error(user_id=user_id, error_code=error)

        cls.after_user_turn(round_model=round_model)

    @classmethod
    def on_auto_fold(cls, *args):
        """
        On user auto fold
        :param args:
        :return:
        """
        user_id = args[0]
        success, error, round_model, is_last_turn = cls.game.auto_fold(user_id)
        if not success:
            return cls._send_error(user_id=user_id, error_code=error)

        cls.after_user_turn(round_model=round_model)

    @classmethod
    def on_check(cls, *args):
        """
        main logic in check_fold_handler
        :param args:
        :return:
        """
        user_id = args[0]
        success, error, round_model, is_last_turn = cls.game.check(user_id)
        if not success:
            return cls._send_error(user_id=user_id, error_code=error)

        cls.after_user_turn(round_model=round_model)

    @classmethod
    def on_fold(cls, *args):
        """
        Fold handler
        :param args:
        :return:
        """
        user_id = args[0]
        success, error, round_model, is_last_turn = cls.game.fold(user_id)
        if not success:
            return cls._send_error(user_id=user_id, error_code=error)

        players_count = round_model.game.get_active_players().count()

        if players_count <= 1:
            cls.game.stop_game(game=round_model.game, round=round_model)
            cls._send_table_status(table_key=round_model.game.table.key)
            time.sleep(cls.START_NEW_GAME_DELAY)
            current_round = cls.game.start_game(table_key=round_model.game.table.key)
            cls.game.setup_start_game_bets(round_model=current_round)
            return cls._send_table_status(table_key=round_model.game.table.key)

        cls.after_user_turn(round_model=round_model)

    @classmethod
    def after_user_turn(cls, round_model: Round):
        """
        Runs ever after user turn
        :param round_model:
        :return:
        """
        game_finished = False
        table_key = round_model.game.table.key
        if round_model.bidding_closed(True):
            new_round = cls.game.run_next_round(game_round=round_model)
            if new_round.is_end_round:
                cls.game.end_game(new_round)
                cls._send_table_status(table_key=table_key)
                game_finished = True

        if game_finished:
            time.sleep(cls.START_NEW_GAME_DELAY)
            current_round = cls.game.start_game(table_key=table_key)
            cls.game.setup_start_game_bets(round_model=current_round)

        cls._send_table_status(table_key=table_key)
        cls._check_auto_fold(round_model=round_model)

    @classmethod
    def _check_auto_fold(cls, round_model: Round):
        current_player = round_model.get_current_player()
        if not current_player:
            return

        user_id = int(current_player.user_id)
        connection = cls.get_connection_by_user(user_id=user_id)

        if current_player.is_fold or not connection:
            # time.sleep(cls.AUTO_FOLD_TIME_OUT)
            success, error, round_model, is_last_turn = cls.game.auto_fold(user_id)
            debug("In auto fold")
            debug(str(success))
            debug(error)
            debug(str(round_model))
            debug(str(is_last_turn))

            players_count = round_model.game.get_active_players().count()

            if players_count <= 1:
                cls.game.stop_game(game=round_model.game)
                cls._send_table_status(table_key=round_model.game.table.key)
                time.sleep(cls.START_NEW_GAME_DELAY)
                current_round = cls.game.start_game(table_key=round_model.game.table.key)
                cls.game.setup_start_game_bets(round_model=current_round)
                return cls._send_table_status(table_key=round_model.game.table.key)

            cls.after_user_turn(round_model=round_model)


    @classmethod
    def add_connection_to_table(cls, user: User, table_key: str):
        """
        add new connection to table connections by table_key
        :param user:
        :param table_key: str
        :return:
        """
        connection = cls.get_connection_by_user(user.id)
        table: Optional[TableConnections] = cls.get_table_connections(table_key=table_key)
        debug(str(connection) + ": Connection for user")
        if not table:
            table = TableConnections(connections=[connection], table_key=table_key)
            cls.table_connections.append(table)
        if connection not in table['connections']:
            table['connections'].append(connection)

    @classmethod
    def remove_connection_from_list(cls, user_id: int):
        """
        method removed connection from connections list
        :param user_id:
        :return:
        """
        return [cls.connections.remove(connection) for connection in cls.connections if connection.user.id == user_id]

    @classmethod
    def get_connection_by_user(cls, user_id: int):
        """
        method removed connection from connections list
        :param user_id:
        :return:
        """
        try:
            return next(connection for connection in cls.connections if connection.user.id == user_id)
        except StopIteration:
            return None

    @classmethod
    def remove_connection_through_user(cls, user_id: int, table_key: str):
        """
        Method removed connection from table connections dict
        :param table_key:
        :param user_id:
        :return:
        """
        connections = cls.get_table_connections(table_key=table_key)
        [
            connections['connections'].remove(connection)
            for connection in connections['connections']
            if connection.user.id == user_id
        ]

    @classmethod
    def remove_user_from_tables_connections(cls, user_id: int):
        """
        Method removed connection from table connections dict
        :param table_key:
        :param user_id:
        :return:
        """
        for table in cls.table_connections:
            [
                table["connections"].remove(connection)
                for connection in table["connections"]
                if connection.user and connection.user.id == user_id
            ]

    @classmethod
    def send_message_through_user(cls, user_id: int, message: str):
        """
        basic message handler
        :param user_id:
        :param message:
        :return:
        """
        connection = cls.get_connection_by_user(user_id)
        if not connection:
            return
        cls.send_to_connection(connection.connection, message)

    @classmethod
    def send_to_connection(cls, connection: socketserver.BaseRequestHandler, message: str):
        logger.debug(f"Debug: {str(message).encode('utf-8')}")
        connection.request.send(str(message).encode('utf-8'))

    @classmethod
    def get_table_connections(cls, table_key) -> Optional[TableConnections]:
        connections = (table for table in cls.table_connections if table['table_key'] == table_key)
        try:
            return next(connections)
        except StopIteration:
            return None

    @classmethod
    def _send_error(cls, user_id: int, error_code: str):
        """
        Send error message to connection by user and with error code
        :param user_id:
        :param error_code:
        :return:
        """
        message = cls.protocol().format_error(error_code=error_code)
        return cls.send_message_through_user(user_id=user_id, message=message)

    @classmethod
    def _validate_join(cls, user: User):
        """
        Validate if user able to join
        @TODO check if table is full filed
        :param user:
        :param table_key:
        :return:
        """
        if user.get_balance() <= 0:
            return False, GameErrorsCode.BL

        return True, None

    @classmethod
    def _send_table_status(cls, table_key: str):
        """
        Send table status for all players
        :param table_key:
        :return:
        """
        table = cls.game.get_table_from_db(table_key=table_key)
        table_connections: TableConnections = cls.get_table_connections(table_key=table_key)
        for connection in table_connections['connections']:
            message = out_game_protocol.table_status(
                current_user=connection.user,
                table_model=table
            )
            cls.send_to_connection(connection=connection.connection, message=message)

    @classmethod
    def _send_table_status_to_user(cls, table_key: str, user_id: str):
        table = cls.game.get_table_from_db(table_key=table_key)
        table_connections: TableConnections = cls.get_table_connections(table_key=table_key)
        connections = (connection for connection in table_connections['connections'] if connection.user.id == user_id)
        try:
            connection = next(connections)
            message = out_game_protocol.table_status(
                current_user=connection.user,
                table_model=table
            )
            cls.send_to_connection(connection=connection.connection, message=message)
        except StopIteration:
            pass

    @classmethod
    def remove_player_from_game(cls, user_id: int):
        player = PlayerGame.objects.filter(user_id=user_id).first()
        if player and player.game:
            table_key = player.game.table.key
            return cls.game.leave_game(table_key, user_id)

        if player:
            player.delete()

    @classmethod
    def remove_not_active_user(cls, user_id: int):
        player = PlayerGame.objects.filter(user_id=user_id).first()
        if player and not player.game:
            table_key = player.table.key
            return cls.game.leave_game(table_key, user_id)

        if player:
            player.delete()

    @classmethod
    def user_reconnection(cls, user_id: int):
        player = PlayerGame.objects.filter(user_id=user_id).first()
        if player and player.game:
            table_key = player.game.table.key
            cls.game.leave_game(table_key, user_id)
            cls._send_table_status(table_key=table_key)

    @classmethod
    def on_leave_game(cls, *args):
        """
        LG: leave game and delete user connection from table_connections
        :param args:
        :return:
        """
        protocol = cls.protocol(args[1])
        parsed_data = protocol.parse_leave_game_data()
        table_key = parsed_data.get('table_key')
        user_id = args[0]
        cls.game.leave_game(table_key, user_id)
        cls.remove_connection_through_user(user_id, table_key)
        cls.remove_not_active_user(user_id=user_id)
        time.sleep(1)
        print('sending _send_table_status')
        cls._send_table_status(table_key=table_key)


class TCPBrokerConnections:
    receive_listener_active = True
    game_handler = TCPGameHandler
    proxy_methods = {
        commands.AUTH_REQUEST: 'on_authenticate_user',
        commands.JOIN_GAME: 'on_join_game',
        commands.LEAVE_GAME: 'on_leave_game',
        commands.BET: 'on_bet',
        commands.CHECK: 'on_check',
        commands.FOLD: 'on_fold',
        commands.AUTO_FOLD: 'on_auto_fold',
        commands.TABLE_STATUS: 'on_table_status',
    }

    SLEEP_TIME = 3

    @classmethod
    def connect_user(cls, connection: socketserver.BaseRequestHandler, data: str):
        """
        establishes a connection with user by user unique token
        and appends connection to connections list, then listens new messages from user
        :param connection:
        :param data:
        :return:
        """
        protocol = cls.game_handler.protocol(data)
        parsed_data = protocol.auth_args()
        user_token = parsed_data.get('short_live_token')
        user = cls._auth_user(user_token, connection=connection)

        if not user:
            debug(f"Connection fail for token:{user_token}")
            return cls._auth_fail(connection=connection)
        info(f"User connected to server:{user.id}")
        cls.handle_command(user_id=user.id, data=data)
        cls.listen_messages(user.id, connection)
        cls._remove_connections_by_user(user_id=user.id)
        cls.game_handler.remove_not_active_user(user_id=user.id)
        connection.finish()

    @classmethod
    def _auth_user(cls, user_token: str, connection: socketserver.BaseRequestHandler) -> Optional["models.User"]:
        """
        Auth user|Reconnect to current table
        :param connection: tcp connection
        :param user_token: string user token
        :return:
        """
        user = User.objects.filter(socket_access_token=user_token).first()
        if not user:
            cls.game_handler.send_to_connection(connection=connection, message=commands.AUTH_FAILED)
            connection.finish()
            return
        active_connection = cls.game_handler.get_connection_by_user(user_id=user.id)
        if active_connection is not None:
            cls._remove_connections_by_user(user_id=user.id)
            active_connection.connection.finish()
            debug(f"Finished connected user prev: {user.email}")

        print(cls.game_handler.connections, "connections")
        return cls._connect(
            user=user,
            connection=connection
        )

    @classmethod
    def _connect(cls, user: "models.User", connection: socketserver.BaseRequestHandler):
        """
        When connection happens:
        1. Remove current connections from existing tables
        2. Add connection to new list
        :param user:
        :param connection:
        :return:
        """
        cls.game_handler.connections.append(
            TCPGameConnection(connection=connection, user=user)
        )
        return user

    @classmethod
    def _auth_fail(cls, connection):
        cls.game_handler.send_to_connection(connection, message=commands.AUTH_FAILED)
        connection.finish()

    @classmethod
    def _remove_connections_by_user(cls, user_id):
        """
        Remove connections from tables and from connections list
        1. Remove current connections from existing tables
        2. Add connection to new list
        :return:
        """
        cls.game_handler.remove_connection_from_list(user_id=user_id)
        cls.game_handler.remove_user_from_tables_connections(user_id=user_id)

    @classmethod
    def listen_messages(cls, user_id: int, connection: socketserver.BaseRequestHandler):
        """
        listen messages from players and move data to command handler
        :param connection: socketserver.BaseRequestHandler instance
        :param user_id: int user pk
        :return:
        """
        try:
            while cls.receive_listener_active:
                if cls.is_socket_closed(connection):
                    debug(f"Connection closed for user_id: {user_id}")
                    break
                if data := connection.request.recv(1024):
                    debug(f"Receive message at {datetime.datetime.now()}")
                    cls.handle_command(user_id, data)
        except ConnectionResetError as e:
            debug(f"Connection closed for user_id: {user_id}")

    @classmethod
    def handle_command(cls, user_id: int, data: str):
        """
        commands handler for handling player commands like JG, CG and other
        :param data:
        :param user_id: user id
        :return:
        """
        protocol = cls.game_handler.protocol(data)
        command = protocol.parse_command()
        method = cls.proxy_methods.get(command)
        if method:
            info(f"Receive data from tcp_client, user_id: {user_id}, data: {data},method: "
                 f"{method}, time: {datetime.datetime.now()}")

            getattr(cls.game_handler, method)(user_id, data)

    @classmethod
    def is_socket_closed(cls, connection: socketserver.BaseRequestHandler) -> bool:
        try:
            # this will try to read bytes without blocking and also without removing them from buffer (peek only)
            data = connection.request.recv(16, socket.MSG_DONTWAIT | socket.MSG_PEEK)
            if len(data) == 0:
                return True
        except BlockingIOError:
            return False  # socket is open and reading from it would block
        except ConnectionResetError:
            return True  # socket was closed for some other reason
        except Exception as e:
            return False
        return False
