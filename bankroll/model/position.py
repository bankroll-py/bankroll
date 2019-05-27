from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, ClassVar

from .cash import Cash
from .instrument import Instrument


@dataclass(frozen=True)
class Position:
    quantityQuantization: ClassVar[Decimal] = Decimal('0.0001')

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

        super().__setattr__('quantity', self.quantizeQuantity(self.quantity))

        if self.quantity == 0 and self.costBasis != 0:
            raise ValueError(
                f'Cost basis {self.costBasis!r} should be zero if quantity is zero'
            )

    def __add__(self, other: Any) -> 'Position':
        if isinstance(other, Position):
            if self.instrument != other.instrument:
                raise ValueError(
                    f'Cannot combine positions in two different instruments: {self.instrument} and {other.instrument}'
                )

            return Position(instrument=self.instrument,
                            quantity=self.quantity + other.quantity,
                            costBasis=self.costBasis + other.costBasis)
        else:
            return NotImplemented

    __radd__ = __add__

    def __str__(self) -> str:
        return f'{self.instrument:21} {self.quantity.normalize():>14,f} @ {self.averagePrice}'
