import json
from typing import List

from rest_framework.renderers import JSONRenderer

from poker_game.models import Table, Game, Round
from poker_game.serializers.protocol_game_serializers import AuthSerializer, TableGameSerializer
from user.models import User


class GameMessagesProtocol:

    @staticmethod
    def user_auth_message(auth_success: bool = True):
        """
        Auth user message
        :param auth_success:
        :return:
        """

        data = {
            'a_u': int(auth_success)
        }

        return GameMessagesProtocol.format_response(
            AuthSerializer(instance=data).data
        )

    @staticmethod
    def table_status(
            current_user: User,
            table_model: Table
    ):
        """
        Table status
        :return:
        """
        game: Game = table_model.get_last_game()
        round_model: Round = game.current_round() if game else None

        serializer = TableGameSerializer(
            game_model=game,
            round_model=round_model,
            instance=table_model,
            context={"current_user": current_user},
            with_label_representation=False
        )
        return GameMessagesProtocol.format_response(serializer.data)

    @staticmethod
    def format_response(data: dict):
        """
        Base format response
        :param data:
        :return:
        """
        renderer = JSONRenderer()
        renderer.compact = True
        return renderer.render(data=data)


out_game_protocol = GameMessagesProtocol()
