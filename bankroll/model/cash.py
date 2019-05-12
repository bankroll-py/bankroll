from decimal import Decimal, ROUND_HALF_EVEN
from enum import Enum, unique
from typing import Any, TypeVar


@unique
class Currency(Enum):
    USD = "USD"
    GBP = "GBP"
    AUD = "AUD"
    EUR = "EUR"
    JPY = "JPY"
    CAD = "CAD"
    CHF = "CHF"
    NZD = "NZD"

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


_T = TypeVar('_T', Decimal, int)


class Cash:
    quantization = Decimal('0.0001')

    @classmethod
    def quantize(cls, d: Decimal) -> Decimal:
        return d.quantize(cls.quantization, rounding=ROUND_HALF_EVEN)

    def __init__(self, currency: Currency, quantity: Decimal):
        if not quantity.is_finite():
            raise ValueError(
                f'Cash quantity {quantity} is not a finite number')

        self._currency = currency
        self._quantity = self.quantize(quantity)
        super().__init__()

    @property
    def currency(self) -> Currency:
        return self._currency

    @property
    def quantity(self) -> Decimal:
        return self._quantity

    def paddedString(self, padding: int = 0) -> str:
        return self.currency.formatWithPadding(self.quantity, padding)

    def __repr__(self) -> str:
        return f'Cash(currency={self.currency!r}, quantity={self.quantity!r})'

    def __str__(self) -> str:
        return self.currency.format(self.quantity)

    def __add__(self, other: Any) -> 'Cash':
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for arithmetic')

            return Cash(currency=self.currency,
                        quantity=self.quantity + other.quantity)
        else:
            return Cash(currency=self.currency, quantity=self.quantity + other)

    def __sub__(self, other: Any) -> 'Cash':
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for arithmetic')

            return Cash(currency=self.currency,
                        quantity=self.quantity - other.quantity)
        else:
            return Cash(currency=self.currency, quantity=self.quantity - other)

    def __mul__(self, other: _T) -> 'Cash':
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for arithmetic')

            return self.quantity * other.quantity
        else:
            return Cash(currency=self.currency, quantity=self.quantity * other)

    def __truediv__(self, other: _T) -> 'Cash':
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for arithmetic')

            return self.quantity / other.quantity
        else:
            return Cash(currency=self.currency, quantity=self.quantity / other)

    def __neg__(self) -> 'Cash':
        return Cash(currency=self.currency, quantity=-self.quantity)

    def __abs__(self) -> 'Cash':
        return Cash(currency=self.currency, quantity=abs(self.quantity))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Cash):
            # Make mypy happy
            b: bool = self.quantity == other
            return b

        return self.currency == other.currency and self.quantity == other.quantity

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for comparison')

            return self.quantity < other.quantity
        else:
            return bool(self.quantity < other)

    def __le__(self, other: Any) -> bool:
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for comparison')

            return self.quantity <= other.quantity
        else:
            return bool(self.quantity <= other)

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for comparison')

            return self.quantity > other.quantity
        else:
            return bool(self.quantity > other)

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, Cash):
            if self.currency != other.currency:
                raise ValueError(
                    f'Currency of {self} must match {other} for comparison')

            return self.quantity >= other.quantity
        else:
            return bool(self.quantity >= other)

    def __hash__(self) -> int:
        return hash((self.currency, self.quantity))