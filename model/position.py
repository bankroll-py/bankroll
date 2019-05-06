from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

from .cash import Cash
from .instrument import Instrument


class Position:
    quantityQuantization = Decimal('0.0001')

    @classmethod
    def quantizeQuantity(cls, quantity: Decimal) -> Decimal:
        return quantity.quantize(cls.quantityQuantization,
                                 rounding=ROUND_HALF_EVEN)

    def __init__(self, instrument: Instrument, quantity: Decimal,
                 costBasis: Cash):
        if instrument.currency != costBasis.currency:
            raise ValueError(
                f'Cost basis {costBasis} should be in same currency as instrument {instrument}'
            )

        if not quantity.is_finite():
            raise ValueError(
                f'Position quantity {quantity} is not a finite number')

        quantity = self.quantizeQuantity(quantity)

        if quantity == 0 and costBasis != 0:
            raise ValueError(
                f'Cost basis {costBasis!r} should be zero if quantity is zero')

        self._instrument = instrument
        self._quantity = quantity
        self._costBasis = costBasis
        super().__init__()

    def combine(self, other: 'Position') -> 'Position':
        if self.instrument != other.instrument:
            raise ValueError(
                f'Cannot combine positions in two different instruments: {self.instrument} and {other.instrument}'
            )

        return Position(instrument=self.instrument,
                        quantity=self.quantity + other.quantity,
                        costBasis=self.costBasis + other.costBasis)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Position):
            return False

        return self.instrument == other.instrument and self.quantity == other.quantity and self.averagePrice == other.averagePrice

    def __hash__(self) -> int:
        return hash((self.instrument, self.quantity, self.averagePrice))

    @property
    def instrument(self) -> Instrument:
        return self._instrument

    @property
    def quantity(self) -> Decimal:
        return self._quantity

    @property
    def averagePrice(self) -> Cash:
        if self.quantity == 0:
            assert self.costBasis == 0
            return self.costBasis

        return self.costBasis / self.quantity / self.instrument.multiplier

    @property
    def costBasis(self) -> Cash:
        return self._costBasis

    def __repr__(self) -> str:
        return f'Position(instrument={self.instrument!r}, quantity={self.quantity!r}, costBasis={self.costBasis!r})'

    def __str__(self) -> str:
        return f'{self.instrument:21} {self.quantity.normalize():>14,f} @ {self.averagePrice}'