from typing import Optional, List, Tuple, TYPE_CHECKING

import math

from tcp_server.enums.errors import GameErrorsCode
from .cards import CardDealer
from .game_table import GameTable
from poker_game.models import Table, Game, Round, PlayerGame, UserRole, PlayerTurn, Bet, UserTransaction
from .player import Player
from ..textchoices import RoundTypeChoice, UserRoleTypeChoice, TransactionTypeChoice, PlayerTurnChoice
from .winner_checker import check_the_winner
from ..typing import UserRoundTurnInfo

if TYPE_CHECKING:
    from user.models import User


class PokerGame:
    round_methods = {
        RoundTypeChoice.FLOP: '_next_table_round',
        RoundTypeChoice.TURN: '_next_table_round',
        RoundTypeChoice.RIVER: '_next_table_round',
        RoundTypeChoice.END_GAME: 'end_game'
    }

    def __init__(self):
        self.tables = []

    def create_table(self, table_key: str):
        """
        create a local table
        :param table_key:
        :return:
        """
        table = GameTable(table_key)
        self.tables.append(table)

    @staticmethod
    def get_table_from_db(table_key: str) -> Table:
        """
        get current table from DB
        :param table_key:
        :return:
        """
        return Table.objects.get(key=table_key)

    def get_table(self, table_key: str) -> Optional[GameTable]:
        """
        get current table locally
        :param table_key:
        :return:
        """
        table = [table for table in self.tables if table.table_key == table_key]
        return table[0] if table else None

    @property
    def tables_list(self) -> List[GameTable]:
        return self.tables

    def connect_player_to_table(self, table_key: str, user: "User") -> Tuple[int, bool]:
        """
        Connect player to table and return count players on table
        :param user: User model
        :param table_key:
        :return:
        """
        table = self.get_table(table_key)
        if not table:
            self.create_table(table_key)

        table = self.get_table(table_key)
        table_model = self.get_table_from_db(table_key)

        player = Player(
            user_id=user.id,
            name=user.username,
            cash=user.get_balance(),
            seat_index=table_model.get_random_free_place()
            # seat_index=table_model.get_first_free_place()
        )
        table.add_or_update_player(
            player
        )
        PlayerGame.objects.get_or_create(
            table=self.get_table_from_db(table_key),
            user_id=user.id,
            seat_index=player.seat_index
        )
        exit_on_game = False
        if game := self.get_current_game(table_key):
            exit_on_game = PlayerGame.objects.filter(
                user_id=user.id,
                game_id=game.id
            ).first()
            table.append_player_to_active(player=player)

        return table_model.players.count(), exit_on_game

    def get_users_on_table(self, table_key: str) -> List[Player.user_info]:
        """
        get all users from current table
        :param table_key:
        :return:
        """
        table = self.get_table(table_key)
        return [player.user_info() for player in table.players()]

    def get_free_table_slot(self, table_key: str) -> int:
        """get table slot and return him position"""
        table = self.get_table(table_key)
        table_slot = [seat for seat in table.seats() if seat is not None]
        return int(table_slot.index(table_slot[-1])) if table_slot else 1

    def leave_game(self, table_key: str, user_id: int):
        print('leave_game')
        table = self.get_table_from_db(table_key)
        game = Game.objects.filter(
            table_id=table.id,
        ).last()

        if not game:
            PlayerGame.objects.filter(
                game_id__isnull=True,
                user_id=user_id
            ).delete()
            return

        actual_player_not_playing = PlayerGame.objects.filter(
            game_id__isnull=True,
            user_id=user_id
        ).exists()
        print(f'actual_player_not_playing: {actual_player_not_playing}')

        if actual_player_not_playing:
            PlayerGame.objects.filter(
                game_id__isnull=True,
                user_id=user_id
            ).delete()
            print('actual_player_not_playing deleted')
        else:

            folded, error, round_model, is_last_turn = self.fold(user_id)
            print(f'fold round_model: {round_model}')

            if not round_model:
                print('no round model...')
                round_model = game.current_round()
                print(f'game round_model: {round_model}')

            current_player = round_model.get_current_player()
            print(f'current_player: {current_player}')

            if current_player:
                print(f'current_player game: {current_player.game}')
                current_seat = current_player.seat_index
                print(f'current_seat: {current_seat}')

                if round_model.turn_index == current_seat:
                    next_player = self._get_next_player_by_seat(round_model, current_seat)
                    if next_player:
                        round_model.turn_index = next_player.seat_index
                        round_model.save()

                if not folded:
                    if round_model:
                        PlayerTurn.objects.create(
                            user_id=user_id,
                            game_id=game.id,
                            round_id=round_model.id,
                            action_choice=PlayerTurnChoice.FOLD
                        )
                        PlayerGame.objects.filter(
                            user_id=user_id,
                            game_id=round_model.game_id,
                        ).update(is_fold=True)

                next_player = self._get_next_player_by_seat(round_model, current_seat)
                if next_player:
                    round_model.turn_index = next_player.seat_index
                    round_model.save()

            try:
                PlayerTurn.objects.create(
                    user_id=user_id,
                    game_id=round_model.game_id,
                    round_id=round_model.id,
                    action_choice=PlayerTurnChoice.LEAVE
                )
                print('added leave game turn')
            except:
                print('not able to add leave game turn')
                pass

            print(f'table.players.count() before: {table.players.count()}; game.id: {game.id}; user_id: {user_id}')

            PlayerGame.objects.filter(
                game_id=game.id,
                user_id=user_id
            ).delete()

            print(f'table.players.count(): {table.players.count()}')

        print(f'--- table.players.count(): {table.players.count()}')
        print(f'--- table.players_at_game.count(): {table.players_at_game.count()}')
        if table.players_at_game.count() == 1:
            self.stop_game(game, round_model)
        elif table.players.count() == 1:
            self.stop_game(game, round_model)
        if table.players.count() == 0:
            game = table.get_last_game()
            print(f'remove game: {game}')
            if game:
                PlayerGame.objects.filter(game=game).all().delete()
                game.delete()

        try:
            print(f'--- actual player count: {table.players.count()}')
            if table.players.count() == 1:
                player = table.players.first()
                print(f'--- only player: {player}')
                print(f'--- only player game_id: {player.game_id}')
                if player.game_id is None:
                    game = table.get_last_game()
                    print(f'remove game 2: {game}')
                    if game:
                        PlayerGame.objects.filter(game=game).all().delete()
                        game.delete()
                    player_last_turn = PlayerTurn.objects.filter(user_id=user_id).order_by('-id').first()
                    print(f'--- player_last_turn: {player_last_turn}')
                    if player_last_turn:
                        print(f'--- player_last_turn action_choice: {player_last_turn.action_choice}')
                        if player_last_turn.action_choice == PlayerTurnChoice.LEAVE:
                            player.delete()
                            print(f'--- player deleted')
        except:
            pass
        

    def stop_game(self, game: Game, round: Round):
        game.type = RoundTypeChoice.END_GAME
        last_player = game.get_active_players().last()
        bank = game.bank
        print('stop_game')
        print(f'bank: {bank}')
        print(f'last_player: {last_player}')
        if bank and bank > 0 and last_player:
            print('bulk add')
            UserTransaction.objects.create(
                user_id=last_player.user_id,
                amount=bank,
                type=TransactionTypeChoice.WIN_GAME
            )
            if not bank:
                bank = 0
            game.winners = [(int(last_player.user_id), int(bank), '')]
        # # game.active = False # this caused that after FOLD winners has not
        #                       # been shown
        game.save()

    def start_game(self, table_key: str) -> Round:
        """
        Start game handler
        :param table_key: key table
        :return:
        """
        Game.objects.filter(
            table__key=table_key
        ).update(
            active=False,
        )
        table_db = self.get_table_from_db(table_key)
        return self.pre_flop(table_db=table_db)

    def pre_flop(self, table_db: Table) -> Round:
        """
        initializes card dealer for deal cards to player hands,
        creates Game, Round if not exists,
        initializes game, round, player_game, player_turn relations and save instances into db
        and starts game...
        param table_db:
        :return:
        """
        game = Game.objects.create(table_id=table_db.id)
        game_id = game.id
        table = self.get_table(table_db.key)
        table.active_players = []
        [table.active_players.append(player) for player in table.players()]
        table_db.in_wait = False
        table_db.save()
        card_dealer = CardDealer()
        card_dealer.cards_generator()
        card_dealer.cards_shuffle()
        round_model = Round.objects.create(
            game_id=game_id,
            type=RoundTypeChoice.PRE_FLOP,
            cards=card_dealer.add_two_to_player_hand(players=table.active_players),
            order=0,
            highest_bet=0,
        )
        self.add_players(game=game)
        self.add_user_roles(round_model=round_model)
        return round_model

    def end_game(self, game_round: Round):
        evaluates = check_the_winner(game_round.filtered_cards)
        winners = [i[0] for i in evaluates]
        game_bank = game_round.game.bank
        table = self.get_table(game_round.game.table.key)
        winner_bank_raw = (game_bank / len(winners))
        winner_bank = math.floor(game_bank / len(winners))
        print(f'game_bank: {game_bank}')
        print(f'len winners: {len(winners)}')
        print(f'winners: {winners}')
        print(f'winner_bank: {winner_bank}')
        print(f'winner_bank_raw: {winner_bank_raw}')
        combination = evaluates[0][2]
        print(f'combination: {combination}')
        inserted = UserTransaction.objects.bulk_create(
            [
                UserTransaction(
                    user_id=user_id,
                    amount=winner_bank,
                    type=TransactionTypeChoice.WIN_GAME
                )
                for user_id in winners
            ]
        )
        print(f'inserted: {inserted}')
        Game.objects.filter(
            table__key=table.table_key
        ).update(
            winners=[(int(winner), int(winner_bank), combination) for winner in winners]
        )

    def add_players(self, game: Game):
        """add active players to the game"""
        table = self.get_table(game.table.key)
        PlayerGame.objects.filter(
            table__key=table.table_key
        ).update(game_id=game.id, is_fold=False)

    def get_is_auto_fold_now(self, round_model: Round):
        current_player = round_model.get_current_player()
        if current_player.is_fold:
            return True, current_player
        return False

    @staticmethod
    def remove_player_from_game(user_id: int):
        PlayerGame.objects.get(user_id=user_id).delete()

    @staticmethod
    def player_is_fold(user_id: int):
        return PlayerGame.objects.filter(user_id=user_id, is_fold=True).count() > 0

    @staticmethod
    def add_user_roles(round_model: Round):
        user_role = UserRoleTypeChoice
        game = round_model.game
        table = game.table
        active_players = game.players.values('seat_index', 'user_id')
        players_count = len(active_players)
        prev_game = table.get_prev_game(current_game=game)
        dealer_role = prev_game.get_dealer_role() if prev_game else None

        if dealer_role:
            next_player = PokerGame._get_next_player_by_seat(round_model, dealer_role.seat_index)
            dealer_index = next_player.seat_index
            next_player = PokerGame._get_next_player_by_seat(round_model, dealer_index)
            small_blind_index = next_player.seat_index
            next_player = PokerGame._get_next_player_by_seat(round_model, small_blind_index)
            big_blind_index = next_player.seat_index
        else:
            dealer_index = game.players.first().seat_index
            next_player = PokerGame._get_next_player_by_seat(round_model, dealer_index)
            small_blind_index = next_player.seat_index
            next_player = PokerGame._get_next_player_by_seat(round_model, small_blind_index)
            big_blind_index = next_player.seat_index

        round_model.turn_index = small_blind_index
        round_model.highest_bet_seat_index = small_blind_index
        round_model.save()

        roles_config = {
            dealer_index: [user_role.DEALER] if players_count >= 3 else [user_role.DEALER, user_role.BIG_BLIND],
            small_blind_index: [user_role.SMALL_BLIND],
            big_blind_index: [user_role.BIG_BLIND] if players_count >= 3 else [user_role.DEALER, user_role.BIG_BLIND]
        }
        if players_count > len(roles_config):
            [
                roles_config.update(
                    {
                        player.get('seat_index'): [user_role.PLAYER]
                    }
                )
                for player in active_players if player.get('seat_index') not in roles_config.keys()
            ]
        for player in active_players:
            UserRole.objects.create(
                **player,
                role=roles_config.get(player.get('seat_index')),
                game_id=game.id,
            )

    def is_valid_bet(self, user_id: int, amount: int) -> Tuple[
        bool,
        Optional[str],
        Optional[PlayerGame],
        Optional[Round],
    ]:
        """
        Validate bet
        :param user_id:
        :param amount:
        :return:
        """
        valid_turn, error, player, round_model = PokerGame._is_valid_turn(user_id=user_id)
        if not valid_turn:
            return valid_turn, error, player, round_model

        min_bet = round_model.get_min_bet_amount()

        if amount < min_bet:
            return False, GameErrorsCode.MIN_BET_AMOUNT, player, round_model

        role = PokerGame._get_user_current_role(
            player=player,
            round_model=round_model
        )

        if not role.can_bet():
            return False, GameErrorsCode.NOT_YOUR_TURN, player, round_model

        return True, None, player, round_model

    @staticmethod
    def is_valid_check(user_id: int):
        """
        Validate check action
        :param user_id:
        :return:
        """
        valid_turn, error, player, round_model = PokerGame._is_valid_turn(user_id=user_id)
        if not valid_turn:
            return valid_turn, error, player, round_model

        role = UserRole.objects.filter(
            user_id=player.user_id,
            game_id=round_model.game_id,
        ).first()

        if not role.can_check():
            return False, GameErrorsCode.NOT_YOUR_TURN, player, round_model

        return True, None, player, round_model

    @staticmethod
    def is_valid_auto_fold(user_id: int):
        """
        Validate check action
        :param user_id:
        :return:
        """
        valid_turn, error, player, round_model = PokerGame._is_valid_turn(user_id=user_id)
        if not valid_turn:
            return valid_turn, error, player, round_model

        role = UserRole.objects.filter(
            user_id=player.user_id,
            game_id=round_model.game_id,
        ).first()

        if not role.can_auto_fold():
            return False, GameErrorsCode.NOT_YOUR_TURN, player, round_model

        return True, None, player, round_model

    def is_valid_fold(self, user_id: int):
        """
        Validate check action
        :param user_id:
        :return:
        """
        valid_turn, error, player, round_model = PokerGame._is_valid_turn(user_id=user_id)
        if not valid_turn:
            return valid_turn, error, player, round_model
        return True, None, player, round_model

    def bet(self, user_id: int, amount: int) -> Tuple[
        bool,
        Optional[str],
        Round,
        bool
    ]:
        """
        register new bet in DB from current user's turn
        :param user_id:
        :param amount:
        :return:
        """
        valid, error, player, round_model = self.is_valid_bet(
            user_id=user_id,
            amount=amount
        )
        if not valid:
            return valid, error, round_model, False


        amount = int(amount)
        max_bet = round_model.highest_total_bet

        PokerGame.register_bet(user_id=user_id, amount=amount, round_model=round_model)
        
        user_bet = round_model.get_user_total_bet(user_id)
        if user_bet > max_bet:
            round_model.highest_bet_seat_index = player.seat_index
            round_model.highest_bet_at_this_round = True
            round_model.highest_bet = user_bet
            round_model.save()

        round_model, is_last_turn = self._on_after_turn(game_round=round_model)
        return True, None, round_model, is_last_turn

    def check(self, user_id: int) -> Tuple[
        bool,
        Optional[str],
        Round,
        bool
    ]:
        valid, error, player, round_model = self.is_valid_check(
            user_id=user_id,
        )

        if not valid:
            return valid, error, round_model, False

        PlayerTurn.objects.create(
            user_id=user_id,
            game_id=round_model.game_id,
            round_id=round_model.id,
            action_choice=PlayerTurnChoice.CHECK
        )
        round_model, is_last_turn = self._on_after_turn(game_round=round_model)
        return True, None, round_model, is_last_turn

    def auto_fold(self, user_id: int) -> Tuple[
        bool,
        Optional[str],
        Round,
        bool
    ]:
        valid, error, player, round_model = self.is_valid_auto_fold(
            user_id=user_id,
        )

        PlayerTurn.objects.create(
            user_id=user_id,
            game_id=round_model.game_id,
            round_id=round_model.id,
            action_choice=PlayerTurnChoice.AUTO_FOLD
        )
        round_model, is_last_turn = self._on_after_turn(game_round=round_model)
        return True, None, round_model, is_last_turn

    def fold(self, user_id: int) -> Tuple:
        valid, error, player, round_model = self.is_valid_fold(
            user_id=user_id,
        )
        if not valid:
            return valid, error, round_model, False

        if round_model:
            PlayerTurn.objects.create(
                user_id=user_id,
                game_id=round_model.game_id,
                round_id=round_model.id,
                action_choice=PlayerTurnChoice.FOLD
            )

            PlayerGame.objects.filter(
                user_id=user_id,
                game_id=round_model.game_id,
            ).update(is_fold=True)

        round_model, is_last_turn = self._on_after_turn(game_round=round_model)
        return True, None, round_model, is_last_turn

    @staticmethod
    def users_round_turn_info(game_round: Round) -> List[UserRoundTurnInfo]:
        """
        1 is current user, 0 is for next user
        1 will use with BT, CK, FD actions
        0 for SC game_info message
        :param game_round:
        :return:
        """
        user_roles = UserRole.objects.filter(round_id=game_round.pk).all()
        result = []
        for user_role in user_roles:
            result.append(
                UserRoundTurnInfo(
                    (user_role.user_id, int(user_role.can_bet()), int(user_role.can_check()))
                )
            )
        return result

    @staticmethod
    def get_cards(table_key: str) -> Round.cards:
        game_round = Round.objects.filter(game__table__key=table_key).last()
        return game_round.cards

    @staticmethod
    def get_current_game(table_key) -> Game:
        """
        Return current game by table key
        :param table_key:
        :return:
        """
        return Game.objects.filter(
            table__key=table_key,
            active=True
        ).last()

    @staticmethod
    def get_current_round(table_key):
        """
        Return current round model
        :param table_key:
        :return:
        """
        return Round.objects.filter(game__table__key=table_key).last()

    def get_player_on_row(self, round_model: Round) -> Player:
        """
        Get current player on row
        :param round_model:
        :return:
        """
        # turn_index is index of seet of player
        index_turn = round_model.turn_index if round_model else 0

        player_model: PlayerGame = round_model.game.players.get_queryset().filter(
            seat_index=index_turn
        ).last()

        if not player_model:
            self.add_players(game=round_model.game)
            player_model = round_model.game.players.get_queryset().filter(
                seat_index=index_turn
            ).last()

        return Player(
            user_id=player_model.user_id,
            name=player_model.user.username,
            cash=player_model.user.get_balance(),
            seat_index=player_model.seat_index
        )

    def setup_start_game_bets(self, round_model: Round):
        small_blind = round_model.game.get_small_blind_role()
        big_blind = round_model.game.get_big_blind_role()
        if not small_blind or not big_blind:
            return
        min_bet_amount = round_model.game.table.min_bet
        PokerGame.register_bet(
            user_id=small_blind.user_id,
            amount=round(min_bet_amount / 2, 0),
            round_model=round_model
        )
        PokerGame.register_bet(
            user_id=big_blind.user_id,
            amount=min_bet_amount,
            round_model=round_model
        )
        dealer = UserRole.objects.filter(game_id=round_model.game_id,
                                         role__contains=[UserRoleTypeChoice.DEALER]).first()
        next_player = self._get_next_player_by_seat(round_model, dealer.seat_index)

        round_model.turn_index = next_player.seat_index
        round_model.highest_bet = min_bet_amount
        round_model.save()

    @staticmethod
    def register_bet(user_id: int, amount: int, round_model: Round) -> Tuple[UserTransaction, PlayerTurn, Bet]:
        """
        Register bet
        :param user_id:
        :param amount:
        :param round_model:
        :return:
        """
        transaction = UserTransaction.objects.create(
            user_id=user_id,
            amount=-amount,
            type=TransactionTypeChoice.BET
        )
        turn = PlayerTurn.objects.create(
            user_id=user_id,
            game_id=round_model.game_id,
            round_id=round_model.id,
            action_choice=PokerGame._get_bet_type(round_model=round_model, bet_amount=amount)
        )
        bet = Bet.objects.create(
            game_id=round_model.game_id,
            user_id=user_id,
            amount=amount,
            round_id=round_model.id
        )
        return bet, turn, transaction

    @staticmethod
    def _is_valid_turn(user_id: int) -> Tuple[
        bool,
        Optional[str],
        Optional[PlayerGame],
        Optional[Round]
    ]:
        player: PlayerGame = PlayerGame.objects.filter(user_id=user_id).first()
        if not player:
            return False, GameErrorsCode.NOT_ACTIVE_PLAYER, player, None

        round_model = Round.objects.filter(game_id=player.game_id).last()

        if round_model and round_model.turn_index != player.seat_index:
            return False, GameErrorsCode.NOT_YOUR_TURN, player, round_model
        return True, None, player, round_model

    def _on_after_turn(self, game_round: Round) -> Tuple[Round, bool]:
        if not game_round:
            return None, True
        last_turn, next_player_index = self._get_next_player_index(
            round_model=game_round
        )
        if next_player_index is not None:
            Round.objects.filter(pk=game_round.pk).update(
                order=next_player_index,
                turn_index=next_player_index
            )
        game_round.refresh_from_db()
        return game_round, last_turn

    @staticmethod
    def _get_next_round_type(game_round: Round):
        types = {
            RoundTypeChoice.PRE_FLOP: RoundTypeChoice.FLOP,
            RoundTypeChoice.FLOP: RoundTypeChoice.TURN,
            RoundTypeChoice.TURN: RoundTypeChoice.RIVER,
            RoundTypeChoice.RIVER: RoundTypeChoice.END_GAME,

        }
        return types.get(game_round.type)

    def run_next_round(self, game_round: Round):
        """
        Run next round
        :param game_round:
        :return:
        """
        next_round = PokerGame._get_next_round_type(game_round)

        if next_round == RoundTypeChoice.END_GAME:
            game_round.type = next_round
            game_round.save()
            return game_round

        return self._next_table_round(game_round)

    @staticmethod
    def _get_next_player_by_seat(game_round: Round, seat_index: int) -> PlayerGame:
        next_player = PlayerGame.objects \
                                        .filter(game=game_round.game,
                                                is_fold=False,
                                                seat_index__gt=seat_index) \
                                        .order_by('seat_index') \
                                        .first()
        if next_player is None:
            next_player = PlayerGame.objects \
                                            .filter(game=game_round.game,
                                                    is_fold=False) \
                                            .order_by('seat_index') \
                                            .first()
        return next_player

    def _get_next_player_index(self, round_model: Round) -> Tuple[bool, int]:
        """
        Get next index for user turn.
        :param round_model:
        :param table:
        :param now: if now return current user's turn
        :return:
        """
        current_on_row = self.get_player_on_row(round_model=round_model)
        count_players = round_model.game.players.get_queryset().count()
        is_last = current_on_row.seat_index + 1 == count_players
        next_index = current_on_row.seat_index + 1 if not is_last else 0

        next_player = PlayerGame.objects \
                                        .filter(game=round_model.game,
                                                is_fold=False,
                                                seat_index__gt=current_on_row.seat_index) \
                                        .order_by('seat_index') \
                                        .first()
        is_last = next_player is None
        if next_player is None:
            next_player = PlayerGame.objects \
                                            .filter(game=round_model.game,
                                                    is_fold=False) \
                                            .order_by('seat_index') \
                                            .first()
        if not next_player:
            return False, None
        next_index = next_player.seat_index
        return is_last, next_index

    def _next_table_round(self, prev_round_model: Round) -> Round:
        """
        Switch to next round the game
        :param prev_round_model:
        :return:
        """
        card_dealer = CardDealer(
            cards_on_hand=prev_round_model.cards_round
        )
        card_dealer.cards_generator()
        next_round_type = PokerGame._get_next_round_type(
            game_round=prev_round_model
        )
        cards = card_dealer.add_to_table(
            is_flop=next_round_type == RoundTypeChoice.FLOP
        )
        updated_cards = prev_round_model.cards
        if not updated_cards.get("table"):
            updated_cards["table"] = []
        updated_cards['table'] = updated_cards['table'] + cards['table']

        turn_index = 1 if next_round_type != RoundTypeChoice.PRE_FLOP else 0
        dealer = UserRole.objects.filter(game_id=prev_round_model.game_id,
                                         role__contains=[UserRoleTypeChoice.DEALER]).first()
        next_player = self._get_next_player_by_seat(prev_round_model, dealer.seat_index)

        new_round = Round.objects.create(
            cards=updated_cards,
            type=next_round_type,
            game_id=prev_round_model.game_id,
            order=turn_index,
            turn_index=next_player.seat_index,
            highest_bet_seat_index=next_player.seat_index,
            highest_bet_at_this_round=True,
            highest_bet=0,
        )
        return new_round

    @staticmethod
    def _get_bet_type(round_model: Round, bet_amount):
        """
        Get bet type by last perv operation
        :param round_model:
        :param bet_amount:
        :return:
        """
        last_bet = Bet.objects.filter(
            round_id=round_model.id
        ).order_by('-id').first()
        if not last_bet:
            return PlayerTurnChoice.BET

        params = {
            bet_amount == last_bet.amount: PlayerTurnChoice.CALL,
            bet_amount > last_bet.amount: PlayerTurnChoice.RISE,
        }
        return params.get(True, PlayerTurnChoice.BET)

    @staticmethod
    def _get_user_current_role(player: PlayerGame, round_model: Round):
        """
        Return last role for user in round/game
        :param player:
        :param round_model:
        :return:
        """
        return UserRole.objects.filter(
            user_id=player.user_id,
            game_id=round_model.game_id,
        ).first()
