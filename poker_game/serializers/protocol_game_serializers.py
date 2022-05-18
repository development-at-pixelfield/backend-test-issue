from collections import OrderedDict
from typing import Optional, List

from rest_framework import serializers

from poker_game.models import Round, PlayerGame, PlayerTurn, Game, Table
from user.models import User

from poker_game.textchoices import RoundTypeChoice



def format_cards_response(data: List[List]):
    return ["".join(map(str, item)) for item in data]

class BaseGameSerializer(serializers.Serializer):
    """
    Base serializer with defined requested user
    """

    def __init__(self, with_label_representation: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.with_label_representation = with_label_representation

    def create(self, validated_data):
        """
        :param validated_data:
        :return:
        """

    def update(self, instance, validated_data):
        """
        :param instance:
        :param validated_data:
        :return:
        """

    def get_user(self) -> "User":
        return self.context.get("current_user")

    def get_field(self, field_name):
        fields = self._readable_fields
        matched = [field for field in fields if field.field_name == field_name]
        return matched.pop() if matched else None

    def to_representation(self, instance):
        """
        Object instance -> Dict of primitive datatypes.
        """
        ret: OrderedDict = super().to_representation(instance=instance)
        if not self.with_label_representation:
            return ret

        for field_name in ret.keys():
            field = self.get_field(field_name=field_name)
            ret[field_name] = {
                "value": ret[field_name],
                "label": field.label
            }
        return ret


class AuthSerializer(BaseGameSerializer):
    """
    Login auth response
    """
    a_u = serializers.IntegerField()

    class Meta:
        fields = "__all__"


class LastBetInfoSerializer(serializers.Serializer):
    """
    Last bet amount info serializer
    """
    bt_a = serializers.IntegerField(label="Bet amount")
    bt_ui = serializers.IntegerField(label="User id")
    bt_ua = serializers.CharField(label="User username")

    class Meta:
        fields = "__all__"


class PlayerGameSerializer(BaseGameSerializer):
    """
    Player game serializer.
    Used for active and inactive players on table
    """

    def __init__(
            self,
            round_model: Round = None,
            **kwargs
    ):
        self.round_model: Round = round_model
        super().__init__(**kwargs)

    """
    Player data serializer.
    Used for messages:
    1. User join to table
    2. User join to table and wait next game
    3. User disconnected
    4. User leave from table
    """
    u_id = serializers.SerializerMethodField(label="User id")
    u_n = serializers.SerializerMethodField(label="User name")
    u_bl = serializers.SerializerMethodField(default=0, label="User balance")
    u_h = serializers.SerializerMethodField(default=[], label="User hand cards")
    u_p = serializers.SerializerMethodField(label="User place")
    u_r = serializers.SerializerMethodField(label="User role")
    u_bt = serializers.SerializerMethodField(label="User bets")
    u_a = serializers.SerializerMethodField(label="User is active in current game")
    u_f = serializers.SerializerMethodField(label="User folded")

    def get_u_id(self, model, *args, **kwargs):
        """
        Permanent attribute from user
        :return:
        """
        return model.user_id

    def get_u_n(self, model, *args, **kwargs):
        """
        Permanent attribute from user
        :return:
        """
        return model.user.username

    def get_u_bl(self, model, *args, **kwargs):
        """
        Permanent attribute from user
        :return:
        """
        return model.user.get_balance()

    def get_u_h(self, model, *args, **kwargs):

        """
        Depend on user round, user cards
        :return:
        """
        cards = self.round_model.cards if self.round_model else None
        user = self.get_user()
        if not model.is_fold and (user.id == model.user_id or (self.round_model and self.round_model.game and self.round_model.game.winners is not None)):
            user_cards = cards.get(str(model.user_id)) if self.round_model and user else None
            return format_cards_response(user_cards) if user_cards else None
        return None

    def get_u_p(self, model, *args, **kwargs):
        """
        Permanent per table/game
        :return:
        """
        return model.seat_index

    def get_u_r(self, model, *args, **kwargs):
        """
        Current user role model
        :return:
        """
        role_model = model.role()
        return role_model.role if role_model else None

    def get_u_a(self, model, *args, **kwargs):
        """
        User is active, connected to game
        :return:
        """
        return 1 if model.game is not None else 0

    def get_u_bt(self, model, *args, **kwargs):
        return model.bets_amount() if model.game else 0

    def get_u_f(self, model, *args, **kwargs):
        return model.is_fold

    class Meta:
        fields = "__all__"


class RoundGameSerializer(BaseGameSerializer):
    """
    Round game serializer
    for handle attributes for current round
    """
    rg_c = serializers.SerializerMethodField(label="Round cards opened on table")
    rg_ri = serializers.SerializerMethodField(label="Turn index")
    rg_rt = serializers.SerializerMethodField(label="Game round type")
    rg_lb = serializers.SerializerMethodField(label="Last bet amount")
    rg_mb = serializers.SerializerMethodField(label="Round min bet amount")
    rg_bc = serializers.SerializerMethodField(label="Round bidding is closed")

    def get_rg_bc(self, model, *args, **kwargs):
        """
        Check if round closed
        :param model:
        :param args:
        :param kwargs:
        :return:
        """
        return model.bidding_closed()

    def get_rg_c(self, model, *args, **kwargs):
        """
        Current cards on table
        :return:
        """
        cards_on_table = model.cards_on_table
        return format_cards_response(cards_on_table) if cards_on_table else None

    def get_rg_ri(self, model, *args, **kwargs):
        """
        Index from 0-4:
        Pre-flop
        Flop
        Turn
        River
        Endgame
        :return:
        """
        return model.turn_index

    def get_rg_rt(self, model, *args, **kwargs):
        """
        Game round type
        Pre-flop
        Flop
        Turn
        River
        Endgame
        :return:
        """
        return model.type

    def get_rg_lb(self, model, *args, **kwargs):
        """
        Last bet info from game
        :return:
        """
        last_bet = model.last_bet()

        if not last_bet:
            return None

        return LastBetInfoSerializer(instance={
            "bt_a": last_bet.amount,
            "bt_ui": last_bet.user_id,
            "bt_ua": last_bet.user.username,
        }).data

    def get_rg_mb(self, model, *args, **kwargs):
        """
        Current min bet amount for current round
        :return:
        """
        return model.get_min_bet_amount()

    class Meta:
        fields = "__all__"


class UserTurnPossibility(BaseGameSerializer):
    """
    User turn possibility
    """
    cc = serializers.IntegerField(label="User can check")
    cb = serializers.IntegerField(label="User can bet")
    cf = serializers.IntegerField(label="User can fold")
    caf = serializers.IntegerField(label="User can auto fold")


class PlayerTurnSerializer(BaseGameSerializer):
    """
    Player turn serializer
    Used for messages:
    1. User make turn
    2. Game table balance
    """

    def __init__(
            self,
            game_round: Round,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.game_round: Round = game_round
        self.current_player: PlayerGame = self.game_round.get_current_player()

    ut_ui = serializers.SerializerMethodField(label="Last user id")
    ut_un = serializers.SerializerMethodField(label="last user username")
    ut_t = serializers.SerializerMethodField(label="Last user type turn: check, pass, all_in, bet")
    ut_cui = serializers.SerializerMethodField(label="Current user turn id")
    ut_cun = serializers.SerializerMethodField(label="Current user turn username")
    ut_cut = serializers.SerializerMethodField(label="Current user turn possibles")

    def get_ut_ui(self, model, *args, **kwargs):
        """
        Return user id
        :return:
        """
        return model.user_id

    def get_ut_un(self, model, *args, **kwargs):
        """
        Return user nickname
        :return:
        """
        return model.user.username

    def get_ut_t(self, model, *args, **kwargs):
        """
        Return type of last turn
        :return:
        """
        return model.action_choice

    def get_ut_cui(self, *args, **kwargs):
        """
        Current user turn id
        :return:
        """
        return self.current_player.user_id if self.current_player else None

    def get_ut_cun(self, *args, **kwargs):
        """
        Current user turn username
        :return:
        """
        return self.current_player.user.username if self.current_player else None

    def get_ut_cut(self, *args, **kwargs):
        """
        Return user turn
        :return:
        """
        role = self.current_player and self.current_player.role()
        if not role:
            return None
        print(role, "Roles")
        data = {
            "cc": role.can_check(),
            "cb": role.can_bet(),
            "cf": role.can_fold(),
            "caf": False
        }

        return UserTurnPossibility(instance=data).data

    class Meta:
        fields = "__all__"


class TableGameSerializer(BaseGameSerializer):

    def __init__(self, game_model: Game = None, round_model: Round = None, **kwargs):
        """
        Init main TableGame serializer to load current status if game/table
        :param game_model:
        :param round_model:
        :param kwargs:
        """
        super().__init__(**kwargs)
        self.game_model: Optional[Game] = game_model
        self.round_model: Optional[Round] = round_model
        self.table_model: Table = self.instance

    """
    Table game status
    """
    g_tk = serializers.SerializerMethodField(label="Table key")
    g_mb = serializers.SerializerMethodField(label="Table min bet")
    g_mp = serializers.SerializerMethodField(label="Table max_players")
    g_r = serializers.SerializerMethodField(label="Round table information")
    g_b = serializers.SerializerMethodField(label="Game balance information")
    g_lt = serializers.SerializerMethodField(label="Last user turn")
    g_pl = serializers.SerializerMethodField(label="Game players")
    g_w = serializers.SerializerMethodField(label="Game winners")

    def get_g_w(self, model, *args, **kwargs):
        """
        It is return game winners
        :param model:
        :param args:
        :param kwargs:
        :return:
        """
        winners = self.game_model.winners if self.game_model and self.game_model.winners else []
        return [{'u': winner[0], 'a':winner[1], 'c':winner[2]} for winner in winners]

    def get_g_tk(self, *args, **kwargs):
        """
        Return table key for model
        :return:
        """
        return self.table_model.key

    def get_g_mb(self, *args, **kwargs):
        """
        Return table min_bet
        :return:
        """
        return self.table_model.min_bet

    def get_g_mp(self, *args, **kwargs):
        """
        Return table max_players
        :return:
        """
        return self.table_model.max_players

    def get_g_r(self, *args, **kwargs):
        """
        Return table round data
        :return:
        """
        if not self.round_model:
            return None

        serializer = RoundGameSerializer(
            instance=self.round_model,
            with_label_representation=self.with_label_representation,
        )

        return serializer.data

    def get_g_b(self, *args, **kwargs):
        """
        Game model current bank
        :return:
        """
        if not self.game_model:
            return None
        return self.game_model.bank

    def get_g_lt(self, *args, **kwargs):
        """
        Game last user turn
        :return:
        """
        if not self.game_model:
            return None

        last_turn = self.game_model.get_last_turn()
        if not last_turn:
            return None

        if self.round_model is None and not self.round_model.current_player():
            return None

        serializer = PlayerTurnSerializer(
            game_round=self.round_model,
            instance=last_turn,
            with_label_representation=self.with_label_representation,
        )
        return serializer.data

    def get_g_pl(self, *args, **kwargs):
        """
        Get players
        :param args:
        :param kwargs:
        :return:
        """
        players = self.table_model.players.all()
        serializer = PlayerGameSerializer(
            round_model=self.round_model,
            instance=players,
            many=True,
            context=self.context,
            with_label_representation=self.with_label_representation
        )
        return serializer.data

    class Meta:
        fields = "__all__"
