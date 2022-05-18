class Player:
    def __init__(
            self,
            user_id: int,
            name: str,
            cash: int,
            seat_index: int
    ):
        self._id: int = user_id
        self._name: str = name
        self._cash: int = cash
        self._seat_index: int = seat_index

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def user_cash(self) -> int:
        return self._cash

    @property
    def seat_index(self) -> int:
        return self._seat_index

    def user_info(self):
        return {
            "id": self.id,
            "name": self.name,
            "cash": self._cash,
            "seat_index": self._seat_index
        }

    def take_cash(self, cash: int):
        if cash > self._cash:
            raise ValueError("Player does not have enough money")
        if cash <= 0:
            raise ValueError("Money has to be a positive amount")
        self._cash -= cash

    def add_cash(self, cash: int):
        if cash <= 0.0:
            raise ValueError("Money has to be a positive amount")
        self._cash += cash

    def denote_cash(self, cash: int):
        if cash <= 0:
            raise ValueError("Money has to be a positive amount")
        self._cash -= cash

    def __str__(self):
        return "player {}".format(self._id)
