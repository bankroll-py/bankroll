from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

from .cash import Cash
from .instrument import Instrument
from dataclasses import dataclass


@dataclass(unsafe_hash=True)
class Position:
    quantityQuantization = Decimal('0.0001')
    instrument: Instrument
    quantity: Decimal
    costBasis: Cash

    @classmethod
    def quantizeQuantity(cls, quantity: Decimal) -> Decimal:
        return quantity.quantize(cls.quantityQuantization,
                                 rounding=ROUND_HALF_EVEN)

    @property
    def averagePrice(self) -> Cash:
        if self.quantity == 0:
            assert self.costBasis == 0
            return self.costBasis

        return self.costBasis / self.quantity / self.instrument.multiplier

    def __post_init__(self) -> None:
        if self.instrument.currency != self.costBasis.currency:
            raise ValueError(
                f'Cost basis {self.costBasis} should be in same currency as instrument {self.instrument}'
            )

        if not self.quantity.is_finite():
            raise ValueError(
                f'Position quantity {self.quantity} is not a finite number')

        self.quantity = self.quantizeQuantity(self.quantity)

        if self.quantity == 0 and self.costBasis != 0:
            raise ValueError(
                f'Cost basis {self.costBasis!r} should be zero if quantity is zero'
            )

    def combine(self, other: 'Position') -> 'Position':
        if self.instrument != other.instrument:
            raise ValueError(
                f'Cannot combine positions in two different instruments: {self.instrument} and {other.instrument}'
            )

        return Position(instrument=self.instrument,
                        quantity=self.quantity + other.quantity,
                        costBasis=self.costBasis + other.costBasis)

    def __str__(self) -> str:
        return f'{self.instrument:21} {self.quantity.normalize():>14,f} @ {self.averagePrice}'
