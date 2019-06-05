from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from enum import Enum, unique
from functools import total_ordering
from numbers import Number
from typing import Any, ClassVar, TypeVar, Union, overload


@unique
@total_ordering
class Currency(Enum):
    EUR = 1
    GBP = 2
    AUD = 3
    NZD = 4
    USD = 5
    CAD = 6
    CHF = 7
    JPY = 8

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Currency):
            return bool(self.value < other.value)
        else:
            return NotImplemented

    def format(self, quantity: Decimal) -> str:
        return self.formatWithPadding(quantity, 0)

    def formatWithPadding(self, quantity: Decimal, padding: int) -> str:
        symbol: str
        if self == Currency.USD:
            symbol = '$'
        elif self == Currency.GBP:
            symbol = '£'
        elif self == Currency.AUD:
            symbol = 'AU$'
        elif self == Currency.EUR:
            symbol = '€'
        elif self == Currency.JPY:
            symbol = '¥'
        elif self == Currency.CAD:
            symbol = 'C$'
        elif self == Currency.NZD:
            symbol = 'NZ$'
        else:
            symbol = ''

        if padding > 0:
            assert len(symbol) <= 3
            symbol = symbol.rjust(3)

        return f'{symbol}{quantity:{padding},.2f}'


@dataclass(frozen=True)
@total_ordering
class Cash:
    quantization: ClassVar[Decimal] = Decimal('0.0001')

    currency: Currency
    quantity: Decimal

    @classmethod
    def quantize(cls, d: Decimal) -> Decimal:
        return d.quantize(cls.quantization, rounding=ROUND_HALF_EVEN)

    def __post_init__(self) -> None:
        if not self.quantity.is_finite():
            raise ValueError(
                f'Cash quantity {self.quantity} is not a finite number')

        super().__setattr__('quantity', self.quantize(self.quantity))

    def paddedString(self, padding: int = 0) -> str:
        return self.currency.formatWithPadding(self.quantity, padding)

    def __str__(self) -> str:
        return self.currency.format(self.quantity)

    def __add__(self, other: Union['Cash', Decimal, int]) -> 'Cash':
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for arithmetic')

            return Cash(currency=self.currency,
                        quantity=self.quantity + other.quantity)
        elif isinstance(other, Decimal) or isinstance(other, int):
            return Cash(currency=self.currency, quantity=self.quantity + other)
        else:
            return NotImplemented

    __radd__ = __add__

    def __sub__(self, other: Union['Cash', Decimal, int]) -> 'Cash':
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for arithmetic')

            return Cash(currency=self.currency,
                        quantity=self.quantity - other.quantity)
        elif isinstance(other, Decimal) or isinstance(other, int):
            return Cash(currency=self.currency, quantity=self.quantity - other)
        else:
            return NotImplemented

    @overload
    def __mul__(self, other: 'Cash') -> Decimal:
        pass

    @overload
    def __mul__(self, other: Union[Decimal, int]) -> 'Cash':
        pass

    def __mul__(self,
                other: Union['Cash', Decimal, int]) -> Union[Decimal, 'Cash']:
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for arithmetic')

            return self.quantity * other.quantity
        elif isinstance(other, Decimal) or isinstance(other, int):
            return Cash(currency=self.currency, quantity=self.quantity * other)
        else:
            return NotImplemented

    __rmul__ = __mul__

    @overload
    def __truediv__(self, other: 'Cash') -> Decimal:
        pass

    @overload
    def __truediv__(self, other: Union[Decimal, int]) -> 'Cash':
        pass

    def __truediv__(self, other: Union['Cash', Decimal, int]
                    ) -> Union[Decimal, 'Cash']:
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for arithmetic')

            return self.quantity / other.quantity
        elif isinstance(other, Decimal) or isinstance(other, int):
            return Cash(currency=self.currency, quantity=self.quantity / other)
        else:
            return NotImplemented

    def __rtruediv__(self, other: Union[Decimal, int]) -> 'Cash':
        if isinstance(other, Decimal) or isinstance(other, int):
            return Cash(currency=self.currency, quantity=other / self.quantity)
        else:
            return NotImplemented

    def __neg__(self) -> 'Cash':
        return Cash(currency=self.currency, quantity=-self.quantity)

    def __abs__(self) -> 'Cash':
        return Cash(currency=self.currency, quantity=abs(self.quantity))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Cash):
            return self.currency == other.currency and self.quantity == other.quantity
        elif isinstance(other, Decimal) or isinstance(other, int):
            return self.quantity == other
        else:
            return NotImplemented

    def __lt__(self, other: Union['Cash', Decimal, int]) -> bool:
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for comparison')

            return self.quantity < other.quantity
        elif isinstance(other, Decimal) or isinstance(other, int):
            return self.quantity < other
        else:
            return NotImplemented