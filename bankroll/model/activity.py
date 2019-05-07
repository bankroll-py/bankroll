from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from enum import Flag, auto
from typing import Any, Dict

from .cash import Cash
from .instrument import Instrument, Stock
from .position import Position


class Activity(ABC):
    @abstractmethod
    def __init__(self, date: datetime):
        self._date = date
        super().__init__()

    @property
    def date(self) -> datetime:
        return self._date

    @abstractmethod
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Activity):
            return False

        return bool(self.date == other.date)

    @abstractmethod
    def __hash__(self) -> int:
        return hash(self.date)


# Represents dividend activity, whether or not it was cashed out or reinvested.
class DividendPayment(Activity):
    def __init__(self, date: datetime, stock: Stock, proceeds: Cash):
        self._stock = stock
        self._proceeds = proceeds
        super().__init__(date)

    @property
    def stock(self) -> Stock:
        return self._stock

    @property
    def proceeds(self) -> Cash:
        return self._proceeds

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, DividendPayment) or not super().__eq__(other):
            return False

        return bool(self.stock == other.stock
                    and self.proceeds == other.proceeds)

    def __hash__(self) -> int:
        return super().__hash__() ^ hash((self.stock, self.proceeds))

    def __repr__(self) -> str:
        return f'DividendPayment(date={self.date!r}, stock={self.stock!r}, proceeds={self.proceeds!r})'

    def __str__(self) -> str:
        return f'{self.date.date()} Dividend       {self.stock:21} {self.proceeds.paddedString(padding=10)}'


class TradeFlags(Flag):
    NONE = 0
    OPEN = auto()
    CLOSE = auto()

    DRIP = auto()  # Dividend reinvestment

    EXPIRED = auto()
    ASSIGNED_OR_EXERCISED = auto()  # Sign of quantity will indicate which


class Trade(Activity):
    @classmethod
    def quantizeQuantity(cls, quantity: Decimal) -> Decimal:
        return Position.quantizeQuantity(quantity)

    def __init__(self, date: datetime, instrument: Instrument,
                 quantity: Decimal, amount: Cash, fees: Cash,
                 flags: TradeFlags):
        if not quantity.is_finite():
            raise ValueError(
                f'Trade quantity {quantity} is not a finite number')

        if flags not in [
                TradeFlags.OPEN, TradeFlags.CLOSE,
                TradeFlags.OPEN | TradeFlags.DRIP,
                TradeFlags.OPEN | TradeFlags.ASSIGNED_OR_EXERCISED,
                TradeFlags.CLOSE | TradeFlags.EXPIRED,
                TradeFlags.CLOSE | TradeFlags.ASSIGNED_OR_EXERCISED
        ]:
            raise ValueError(f'Invalid combination of flags: {flags}')

        self._instrument = instrument
        self._quantity = self.quantizeQuantity(quantity)
        self._amount = amount
        self._fees = fees
        self._flags = flags
        super().__init__(date)

    @property
    def instrument(self) -> Instrument:
        return self._instrument

    @property
    def quantity(self) -> Decimal:
        return self._quantity

    @property
    def amount(self) -> Cash:
        return self._amount

    @property
    def fees(self) -> Cash:
        return self._fees

    @property
    def price(self) -> Cash:
        if self.quantity >= 0:
            return -self.amount / self.instrument.multiplier
        else:
            return self.amount / self.instrument.multiplier

    @property
    def flags(self) -> TradeFlags:
        return self._flags

    @property
    def proceeds(self) -> Cash:
        return self.amount - self.fees

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Trade) or not super().__eq__(other):
            return False

        return bool(self.instrument == other.instrument
                    and self.quantity == other.quantity
                    and self.amount == other.amount and self.fees == other.fees
                    and self.flags == other.flags)

    def __hash__(self) -> int:
        return super().__hash__() ^ hash((self.instrument, self.quantity,
                                          self.amount, self.fees, self.flags))

    def __repr__(self) -> str:
        return f'Trade(date={self.date!r}, instrument={self.instrument!r}, quantity={self.quantity!r}, amount={self.amount!r}, fees={self.fees!r}, flags={self.flags!r})'

    def __str__(self) -> str:
        if self.quantity > 0:
            action = 'Buy '
        else:
            action = 'Sell'
        return f'{self.date.date()} {action} {abs(self.quantity):>9} {self.instrument:21} {self.amount.paddedString(padding=10)} (before {self.fees.paddedString(padding=5)} in fees)'

    def _replace(self, **kwargs: Any) -> 'Trade':
        vals: Dict[str, Any] = {
            k.lstrip('_'): v
            for k, v in self.__dict__.items()
        }
        vals.update(kwargs)

        return Trade(**vals)