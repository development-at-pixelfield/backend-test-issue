from typing import Tuple, TypedDict
from poker_game.textchoices import UserRoleTypeChoice

from tcp_server.enums import commands
from tcp_server.enums.errors import GameErrors


class AuthArgs(TypedDict):
    command_type: str
    short_live_token: str


class JGArgs(TypedDict):
    command_type: str
    table_key: str


class GameStatusArgs(TypedDict):
    command_type: str
    table_key: str


class LGArgs(TypedDict):
    command_type: str
    table_key: str


class BTArgs(TypedDict):
    command_type: str
    amount: str


class GameConnectionProtocolMessages:
    BET = "{user_id}:{username}:{amount}|{next_player_id}|{can_check}:{can_bet}"
    CHECK = "{user_id}:{next_player_turn}|{can_check}:{can_bet}"
    FOLD = "{user_id}:{next_player_turn}|{can_check}:{can_bet}"


class GameConnectionProtocol:
    DM = '|'
    FORMAT_MESSAGE = '\n<PokerGame>{0}</PokerGame>'

    def __init__(self, data=None):
        self.data = data
        self.messages = GameConnectionProtocolMessages

    def join_game(self, user_id, username, cash, table_slot):
        """
        Format message when user join game
        :param user_id:
        :param username:
        :param cash:
        :param table_slot:
        :return:
        """
        args = (
            commands.JOIN_GAME,
            user_id,
            username,
            cash,
            table_slot
        )
        return self._format_response(args)

    def leave_game(self, user_id):
        """
        Format message when user leave game
        :param user_id:
        :return:
        """
        args = (
            commands.LEAVE_GAME,
            user_id
        )
        return self._format_response(args)

    def auth_args(self) -> AuthArgs:
        """
        Arguments from user auth
        :return:
        """
        return self._parse_data(('command_type', 'short_live_token'))

    def parse_join_game_data(self) -> JGArgs:
        """
        Arguments from user auth
        :return:
        """
        return self._parse_data(('command_type', 'table_key'))

    def parse_leave_game_data(self) -> LGArgs:
        """
        Arguments from user leave game data
        :return:
        """
        return self._parse_data(('command_type', 'table_key'))

    def parse_bet(self) -> BTArgs:
        """
        Arguments from user bet game data
        :return:
        """
        return self._parse_data(('command_type', 'amount'))

    def parse_game_info_data(self) -> GameStatusArgs:
        """
        Arguments from game info data
        :return:
        """
        return self._parse_data(('command_type', 'table_key'))

    def parse_command(self):
        """
        Parse command type from data
        :return:
        """
        data = self.data.decode('utf-8').split(self.DM)
        return data[0]

    @staticmethod
    def parse_cards(cards_list: dict):
        """
        parse all cards to better view
        :param cards_list:
        :return:
        """
        cards = {}
        for key in cards_list.keys():
            cards[key] = []
        for key, value in cards_list.items():
            for card in value:
                para = f'{card[0]}{card[1]}'
                cards[key].append(para)
        return cards

    def parse_cards_after_win(self, cards_list: dict):
        """
        parse cards without table cards, only users cards
        :param cards_list:
        :return:
        """
        cards = {}
        message = f'{commands.ALL_CARDS}{self.DM}'
        for key in cards_list.keys():
            if key != 'table':
                cards[key] = []
        for key, value in cards_list.items():
            if key != 'table':
                for card in value:
                    para = f'{card[0]}{card[1]}'
                    cards[key].append(para)
        for key, value in cards.items():
            message += f"{key}:{value[0]}:{value[1]}|"
        return message

    def format_table_info_start(
            self,
            roles: list,
            current_player: int,
            min_bet: int,
            user_can_bet: int,
            user_can_check: int
    ) -> str:
        """
        Format table info  include roles, current player turn and minimal bet
        :param user_can_bet:
        :param user_can_check:
        :param roles:
        :param current_player:
        :param min_bet:
        :return:
        """
        role_type = UserRoleTypeChoice
        user_roles = [f'{one[0]}:{1 if role_type.BIG_BLIND in one[1] else 0}:' \
                      f'{1 if role_type.SMALL_BLIND in one[1] else 0}:' \
                      f'{1 if role_type.DEALER in one[1] else 0}|' for one in roles]
        args = (
            commands.TABLE_STATUS,
            f"{''.join(f'{role}' for role in user_roles)}{min_bet}{self.DM}{current_player}",
            f"{user_can_check}:{user_can_bet}"
        )
        return self._format_response(args)

    def format_cards_message(self, first_card: list, second_card: list):
        """
        return user's two cards
        :param first_card:
        :param second_card:
        :return:
        """
        args = (
            commands.CARDS_PLAYER,
            first_card,
            second_card
        )
        return self._format_response(args)

    def format_bet_message(
            self,
            user_id: int,
            username: str,
            amount: int,
            next_turn_index: int,
            can_check: bool,
            can_bet: bool
    ) -> str:
        """
        Create message to inform user for bet
        :param user_id:
        :param username:
        :param amount:
        :param next_turn_index:
        :param can_check:
        :param can_bet:
        :return: str message protocol for user
        """
        command = self.messages.BET.format(
            user_id,
            username,
            amount,
            next_turn_index,
            can_check,
            can_bet
        )
        args = (
            commands.BET,
            command
        )
        return self._format_response(args=args)

    def format_check_message(
            self,
            user_id: int,
            next_turn_index,
            can_check,
            can_bet
    ) -> str:
        """
        Check message format
        :param user_id:
        :param next_turn_index:
        :param can_check:
        :param can_bet:
        :return:
        """
        command = self.messages.CHECK.format(
            user_id,
            next_turn_index,
            can_check,
            can_bet,
        )
        args = (
            commands.CHECK,
            command
        )
        return self._format_response(args)

    def fold_message_format(
            self,
            user_id,
            next_turn_index,
            can_check,
            can_bet
    ) -> str:
        """
        Fold message format
        :param user_id:
        :param next_turn_index:
        :param can_check:
        :param can_bet:
        :return:
        """
        command = self.messages.FOLD.format(
            user_id,
            next_turn_index,
            can_check,
            can_bet,
        )
        args = (
            commands.FOLD,
            command
        )
        return self._format_response(args)

    def winner_message(self, users: list) -> str:
        args = (
            commands.WINNER,
            *[user for user in users]
        )
        return self._format_response(args)

    def format_table_cards_message(self, cards: list) -> str:
        args = (
            commands.CARDS_TABLE,
            *[card for card in cards]
        )
        return self._format_response(args)

    def format_error(self, error_code):
        """
        Error formatting by code references
        :param error_code:
        :return:
        """
        args = (
            commands.ERROR,
            GameErrors.CODES.get(error_code, GameErrors.DEFAULT)
        )
        return self._format_response(args)

    def _format_response(self, args) -> str:
        """
        Format every message for response
        :param args:
        :return:
        """
        message = self.DM.join(map(str, args))
        return self.FORMAT_MESSAGE.format(message)

    def format_response(self, *args) -> str:
        """
        Format every message for response
        :param args:
        :return:
        """
        return self._format_response(args)

    def _parse_data(self, keys_list: Tuple) -> dict:
        """
        Parse data for prepare key: values to next process
        :param keys_list: dict with parsed data
        :return:
        """
        data = self.data.decode('utf-8').split(self.DM)
        return dict(zip(keys_list, data))
