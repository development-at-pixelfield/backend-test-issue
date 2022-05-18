import random
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
        self.cards_on_hand = cards_on_hand if cards_on_hand else []
        if self.cards_on_hand:
            tmp = []
            for item in self.cards_on_hand:
                for single in item:
                    tmp.append(single)
            self.cards_on_hand = tmp

    def cards_generator(self):
        """
        Generates 52 cards and append them into deck,
        check duplicates
        """
        self.deck = []
        [
            self.deck.append([value, suit])
            for value in self._cards_values for suit in self._cards_suits
            if [value, suit] not in self.cards_on_hand
        ]
        return self.deck

    def cards_shuffle(self):
        """random deck shuffle"""
        for i in range(3):
            random.shuffle(self.deck)

    def cards_list(self):
        """return cards List"""
        return self.deck

    def add_two_to_player_hand(self, players):
        """
        takes 2 cards from deck list, removes this two cards from deck and put in active_players_cards
        :param: players - active_players list from python PokerGame class
        """
        active_players_cards = {}
        for player in players:
            cards = [self.deck[0], self.deck[1]]
            [self.deck.remove(card) for card in cards]
            active_players_cards[player.id] = cards
        return active_players_cards

    def add_three_on_table(self):
        """
        takes three cards from  and remove them from deck
        :return:
        """
        cards_on_table = {}
        cards = self.deck[0:3]
        [self.deck.remove(card) for card in cards]
        cards_on_table['table'] = cards
        return cards_on_table

    def add_one_on_table(self):
        """
        takes three cards from  and remove them from deck
        :return:
        """
        cards_on_table = {}
        card = self.deck[0]
        self.deck.remove(card)
        cards_on_table['table'] = card
        return cards_on_table

    def add_to_table(self, is_flop=False):
        counts = 3 if is_flop else 1
        cards_on_table = {}
        cards = random.sample(self.deck, counts)
        [self.deck.remove(card) for card in cards]
        cards_on_table['table'] = cards
        return cards_on_table
