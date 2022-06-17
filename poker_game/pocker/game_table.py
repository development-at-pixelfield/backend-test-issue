from typing import List

from poker_game.models import UserTable, PlayerGame
from poker_game.poker.cards import CardDealer
from poker_game.poker.player import Player


class FullGameRoomException(Exception):
    pass


class DuplicateRoomPlayerException(Exception):
    pass


class UnknownRoomPlayerException(Exception):
    pass


class GameTable:
    MAX_PLAYERS = 6

    def __init__(self, table_key):
        self._seats = [None for i in range(GameTable.MAX_PLAYERS)]
        self._players = {}
        self.table_key = table_key
        self.card_dealer = CardDealer()
        self.active_players: List[Player] = []

    @property
    def card_dealer(self):
        return self.card_dealer

    @property
    def players(self):
        return [
            self._players[player_id] for player_id in self._seats
            if player_id is not None
        ]

    @property
    def players_counts(self):
        return len(self.players)

    def append_player_to_active(self, player):
        self.active_players.append(player)

    @property
    def seats(self):
        return list(self._seats)

    def get_player(self, player_id):
        print(self._players, "players length")
        player = self._players[player_id]
        if player:
            return player
        else:
            return False

    def add_or_update_player(self, player):
        if player.id in self._players:
            print('add_or_update_player A')
            seat = self.player_seat(player.id)
        else:
            print('add_or_update_player B')
            seat = self.get_next_seat_index()
        print(f'add_or_update_player seat: {seat}')
        print(f'add_or_update_player seats: {self._seats}')

        self._seats[seat] = player.id
        self._players[player.id] = player

    def remove_player(self, player_id):
        try:
            seat = self._seats.index(player_id)
            del self._players[player_id]
            self._seats[seat] = None
            UserTable.objects.filter(user_id=player_id).delete()
            [self.active_players.remove(player) for player in self.active_players if player.id == player_id]
            print('self active players. ', self.active_players)
        except ValueError:
            raise UnknownRoomPlayerException

    def player_seat(self, player_id):
        try:
            seat = self._seats.index(player_id)
            return seat
        except ValueError:
            raise UnknownRoomPlayerException

    def get_player_table_slot(self, order: int):
        player_seat = self.active_players[order]
        return self.active_players.index(player_seat)

    def get_next_seat_index(self):
        """
        Will return next index for player
        :return:
        """
        next_index = len(self._players)
        if next_index - 1 >= GameTable.MAX_PLAYERS:
            return -1
        return next_index
