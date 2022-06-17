import random

from typing import Optional

from django.db import models
from django.db.models import Sum, JSONField
from django.contrib.postgres.fields import ArrayField
from django.conf import settings

from .textchoices import TransactionTypeChoice, RoundTypeChoice, PlayerTurnChoice, UserRoleTypeChoice


class Table(models.Model):
    """Class for holding info about available tables"""

    key = models.CharField(max_length=32,
                           verbose_name='Table unique key')
    name = models.CharField(max_length=32,
                            verbose_name='Table name')
    description = models.TextField(default='',
                                   blank=True)
    max_players = models.PositiveSmallIntegerField(default=6,
                                                   verbose_name='Maximum players')
    min_bet = models.SmallIntegerField(default=5)

    in_wait = models.BooleanField(default=True)

    def __str__(self):
        return f'Table: {self.name} ({self.key})'

    @property
    def active_players(self):
        return PlayerGame.objects.filter(table_id=self.id).count()

    def get_first_free_place(self):
        seats = list(self.players.values_list('seat_index', flat=True))
        for seat in range(0, self.max_players - 1):
            if seat not in seats:
                return seat
        return -1

    def get_random_free_place(self):
        seats = list(self.players.values_list('seat_index', flat=True))
        free = False
        while not free:
            random_seet = random.randint(0, 5)
            free = random_seet not in seats
        return random_seet

    def get_last_game(self):
        return self.games.filter(active=True).last()

    def get_prev_game(self, current_game):
        return self.games.filter(
            id__lt=current_game.id,
            created_at__lt=current_game.created_at
        ).order_by('-id').first()

    def game_counter(self):
        return self.games.filter(active=False).count()

    @property
    def players_at_game(self):
        return self.players.filter(game__isnull=False)


class UserTable(models.Model):
    table = models.ForeignKey(
        Table,
        on_delete=models.CASCADE
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        unique=True
    )
    last_seen = models.DateTimeField(auto_now_add=True)

    seat = models.SmallIntegerField(default=0)


class UserTransaction(models.Model):
    """
    User Transaction table, count all transactions from user
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    amount = models.IntegerField()
    type = models.CharField(
        choices=TransactionTypeChoice.choices,
        max_length=28
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=['user_id', ]
            )
        ]


class Game(models.Model):
    """
    main game class
    """
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name="games")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    winners = JSONField(default=None, null=True, blank=True)

    @property
    def bank(self):
        queryset = self.bets.get_queryset()
        return queryset.aggregate(Sum('amount'))['amount__sum']

    @property
    def roles(self):
        queryset = self.user_roles.get_queryset()
        return [[i.user.id, i.role] for i in queryset.filter(active=True)]

    def get_small_blind_role(self) -> "UserRole":
        queryset = self.user_roles.get_queryset()
        return queryset.filter(role__contains=[UserRoleTypeChoice.SMALL_BLIND]).first()

    def get_big_blind_role(self) -> "UserRole":
        queryset = self.user_roles.get_queryset()
        return queryset.filter(role__contains=[UserRoleTypeChoice.BIG_BLIND]).first()

    def get_dealer_role(self) -> "UserRole":
        queryset = self.user_roles.get_queryset()
        return queryset.filter(role__contains=[UserRoleTypeChoice.DEALER]).first()

    def get_last_turn(self) -> Optional["PlayerTurn"]:
        return PlayerTurn.objects.filter(
            game_id=self.id,
        ).last()

    def current_round(self):
        return self.rounds.last()

    def get_active_players(self):
        return self.players.get_queryset().filter(is_fold=False)


class Round(models.Model):
    """
    game's round, which include game statuses like Pre-Flop, Flop. Turn, River, End_Game
    """
    type = models.CharField(
        choices=RoundTypeChoice.choices,
        max_length=28
    )
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="rounds")
    cards = models.JSONField(null=True, blank=True)
    order = models.SmallIntegerField(default=None)
    turn_index = models.PositiveSmallIntegerField(default=0)
    highest_bet = models.PositiveSmallIntegerField(default=0)
    highest_bet_at_this_round = models.BooleanField(default=False)
    highest_bet_seat_index = models.PositiveSmallIntegerField(default=0)

    @property
    def filtered_cards(self):
        cards_filtered = {}
        for user in self.game.players.filter(is_fold=False):
            key = str(user.user_id)
            cards_filtered[key] = self.cards[key]
        cards_filtered['table'] = self.cards['table']
        return cards_filtered

    @property
    def is_end_round(self):
        return self.type == RoundTypeChoice.END_GAME.value

    @property
    def cards_round(self):
        cards: dict = self.cards
        values = dict(cards).values() if self.cards else []
        data = [[card for card in cards] for cards in values]
        return data

    @property
    def cards_on_table(self):
        cards: dict = self.cards
        if "table" in cards.keys():
            return cards.get("table")
        return []

    @property
    def game_round_index(self):
        values = list(RoundTypeChoice.values)
        return values.index(self.type)

    @property
    def highest_total_bet(self) -> int:
        max_bet = 0
        for user in self.game.players.all():
            current_bet = self.get_user_total_bet(user.user_id)
            if current_bet > max_bet:
                max_bet = current_bet
        return max_bet

    def get_user_total_bet(self, user_id: int) -> int:
        total_bet = Bet.objects.filter(
            round_id=self.id,
            user_id=user_id,
        ).aggregate(Sum('amount'))['amount__sum']
        return total_bet if total_bet else 0

    def last_bet(self) -> Optional["Bet"]:
        """
        Will return Last bet
        :return:
        """
        return Bet.objects.filter(
            round_id=self.id
        ).last()

    def last_bets(self):
        """
        Will return Last bet
        :return:
        """
        return Bet.objects.filter(
            round_id=self.id
        ).order_by("-id")[:2].all()

    def get_totals_bets(self):
        last_bets = self.last_bets()
        total_bets_pre = 0
        total_bets_last = 0

        if len(last_bets) > 0:
            total_bets_pre = Bet.objects.filter(
                round_id=self.id,
                user_id=last_bets[0].user_id
            ).aggregate(Sum('amount'))['amount__sum']

        if len(last_bets) > 1:
            total_bets_last = Bet.objects.filter(
                round_id=self.id,
                user_id=last_bets[1].user_id
            ).aggregate(Sum('amount'))['amount__sum']

        return total_bets_pre or 0, total_bets_last or 0

    def bidding_closed(self, in_main: bool = False):
        """
        Will return bidding finished
        in case if last bid was call(closed) the bidding
        1. Calculate if total last the same
        2. Compare last with prev one
        :return:
        """

        if in_main:
            if self.highest_bet_at_this_round:
                self.highest_bet_at_this_round = False
                self.save()
                return False
        return self.turn_index == self.highest_bet_seat_index

    def get_min_bet_amount(self):
        """
        Will return bidding finished
        in case if last bid was call(closed) the bidding
        1. Calculate if total last the same
        2. Compare last with prev one
        :return:
        """
        player = self.get_current_player()
        if not player:
            return 0
        max_bet = self.highest_bet
        user_bet = self.get_user_total_bet(player.user_id)
        return max_bet - user_bet

    def get_current_player(self) -> Optional["PlayerGame"]:
        return PlayerGame.objects.filter(
            seat_index=self.turn_index,
            game=self.game
        ).first()


class PlayerGame(models.Model):
    """
    Relations model,
    show which active user now in game and wait next game
    """
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='players', null=True)
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name="players", null=True)
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    seat_index = models.PositiveSmallIntegerField(null=False)
    is_fold = models.BooleanField(default=False)

    def is_all_in(self) -> Optional["PlayerTurn"]:
        """
        Check if user all in in this game
        :return:
        """
        return PlayerTurn.object.filter(
            game_id=self.game_id,
            user_id=self.user_id,
            action_choice=PlayerTurnChoice.ALL_IN
        ).first()

    def all_in_round(self) -> Optional["Round"]:
        """
        Get all in around
        :return:
        """
        if turn := self.is_all_in():
            return turn.round

    def role(self) -> Optional["UserRole"]:
        """
        Role in current game
        :return:
        """
        return UserRole.objects.filter(
            game_id=self.game_id,
            user_id=self.user_id
        ).first()

    def bets_amount(self):
        return Bet.objects.filter(
            game_id=self.game_id,
            user_id=self.user_id
        ).aggregate(Sum('amount'))['amount__sum']


class PlayerTurn(models.Model):
    """
    turn - True mean user's turn.
    action_choice - user's choice in current round
    """
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='player_turn')
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    action_choice = models.CharField(choices=PlayerTurnChoice.choices, max_length=28, null=True, blank=True)

    def __str__(self):
        return f'Turn: {self.user} ({self.action_choice})'

class Bet(models.Model):
    """
    betting on round, user can bet some cash in current game
    """
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='bets')
    user = models.ForeignKey('user.User', on_delete=models.CASCADE, )
    amount = models.IntegerField()
    round = models.ForeignKey(Round, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(
                fields=['game_id', ]
            )
        ]


class UserRole(models.Model):
    """
    user's role can be dealer, big blind, small blind. depends on round
    """
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    game = models.ForeignKey(Game, related_name='user_roles', on_delete=models.CASCADE)
    role = ArrayField(models.CharField(choices=UserRoleTypeChoice.choices, max_length=28))
    active = models.BooleanField(default=True)
    seat_index = models.PositiveSmallIntegerField(null=True)

    @property
    def round(self):
        return self.game.rounds.last()

    def user_turn_in_round(self):
        return PlayerTurn.objects.filter(
            round_id=self.round.id,
            user_id=self.user_id
        ).first()

    def has_rise(self):
        return PlayerTurn.objects.filter(
            round_id=self.round.id,
            action_choice=PlayerTurnChoice.RISE
        ).first()

    def user_game_all_in(self):
        return PlayerTurn.objects.filter(
            game_id=self.game_id,
            user_id=self.user_id,
            action_choice=PlayerTurnChoice.ALL_IN
        ).first()

    def user_turn_is(self, turn_type):
        turn = self.user_turn_in_round()
        if not turn:
            return False
        return turn.action_choice.action_choice == turn_type

    def has_fold(self):
        return PlayerTurn.objects.filter(
            game_id=self.round.game_id,
            user_id=self.user_id,
            action_choice=PlayerTurnChoice.FOLD
        ).first()

    @property
    def user_is_fold_in_round(self):
        return self.user_turn_is(turn_type=PlayerTurnChoice.FOLD)

    @property
    def user_is_check_in_round(self):
        return self.user_turn_is(turn_type=PlayerTurnChoice.CHECK)

    @property
    def user_is_bet_in_round(self):
        return self.user_turn_is(turn_type=PlayerTurnChoice.BET)

    def can_bet(self):
        """
        Only current user can bet
        :return:
        """
        if self.user_game_all_in():
            return False

        return self.seat_index == self.round.turn_index

    def can_check(self):
        """
        Check can user on row and:
        1. No actions with rise or re-rise
        :return:
        """
        if not self.seat_index == self.round.turn_index:
            return False

        if self.user_game_all_in():
            return False

        round = self.game.current_round()
        player = round.get_current_player()
        max_bet = round.highest_bet
        user_bet = round.get_user_total_bet(player.user_id)

        return max_bet == user_bet

    def can_fold(self):
        """
        Check if user can fold in round
        :return:
        """
        return self.seat_index == self.round.turn_index

    def can_auto_fold(self):
        """
        Check if auto fold
        :return:
        """
        if not self.seat_index == self.round.turn_index:
            return False

        return True
