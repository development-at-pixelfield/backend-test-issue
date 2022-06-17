import random
from itertools import chain, product
from typing import List


class CardDealer:
    _cards_values = ['S', 'H', 'D', 'C']
    _cards_suits = ['A', 'J', 'Q', 'K', 2, 3, 4, 5, 6, 7, 8, 9, 10]
    deck = []

    def __init__(
            self,
            cards_on_hand: List = None
    ):
        """
        Init dealer. Pass cards on hand.
        :param cards_on_hand:
        """
        self.cards_on_hand = list(chain(*self.cards_on_hand)) if cards_on_hand else []

    def cards_generator(self):
        """
        Generates 52 cards and set them to deck,
        check duplicates
        """
        self.deck = list(product(self._cards_suits, self._cards_values))
        return self.deck

    def cards_shuffle(self):
        """random deck shuffle"""
        for i in range(3):
            random.shuffle(self.deck)

    @property
    def cards_list(self):
        """return cards List"""
        return self.deck

    def add_cards_to_players(self, players, amount: int):
        """
        takes 'amount' cards from deck list, removes this two cards from deck and put in active_players_cards
        :param: players - active_players list from python PokerGame class
        :param: amount - amount of cards for each user
        """
        active_players_cards = {}

        for player in players:
            active_players_cards[player.id] = self.deck[0:amount]
            self.deck = self.deck[amount:]

        return active_players_cards

    def add_two_to_player_hand(self, players):
        """
        takes 2 cards from deck list, removes this two cards from deck and put in active_players_cards
        :param: players - active_players list from python PokerGame class
        """
        return self.add_cards_to_players(players, 2)

    def add_cards_on_table(self, amount: int):
        """
        Takes(removes) 'amount' cards from deck and returns them
        """

        assert amount > 0

        cards_on_table = {
            'table': self.deck[0:amount]
        }
        self.deck = self.deck[amount:]
        return cards_on_table

    def add_three_on_table(self):
        """
        takes three cards from  and remove them from deck
        :return:
        """
        return self.add_cards_on_table(3)

    def add_one_on_table(self):
        """
        takes three cards from  and remove them from deck
        :return:
        """
        return self.add_cards_on_table(1)

    def add_on_table(self, is_flop=False):

        counts = 3 if is_flop else 1

        # pick random 'counts' elements
        cards = random.sample(self.deck, counts)

        # delete them from deck
        for card in cards:
            self.deck.remove(card)

        # return it
        return {
            'table': cards
        }
