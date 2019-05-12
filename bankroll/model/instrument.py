from abc import ABC, abstractmethod
from datetime import date
from enum import Enum, unique
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any, Optional

from .cash import Currency

import re


class Instrument(ABC):
    multiplierQuantization = Decimal('0.1')

    @classmethod
    def quantizeMultiplier(cls, multiplier: Decimal) -> Decimal:
        return multiplier.quantize(cls.multiplierQuantization,
                                   rounding=ROUND_HALF_EVEN)

    @abstractmethod
    def __init__(self, symbol: str, currency: Currency):
        if not symbol:
            raise ValueError('Expected non-empty symbol for instrument')
        if not currency:
            raise ValueError('Expected currency for instrument')

        self._symbol = symbol
        self._currency = currency
        super().__init__()

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def currency(self) -> Currency:
        return self._currency

    @property
    def multiplier(self) -> Decimal:
        return Decimal(1)

    def __eq__(self, other: Any) -> bool:
        # Strict typechecking, because we want different types of Instrument to be inequal.
        if type(self) != type(other):
            return False

        return bool(self.symbol == other.symbol
                    and self.currency == other.currency)

    def __hash__(self) -> int:
        return hash((self.currency, self.symbol))

    def __lt__(self, other: 'Instrument') -> bool:
        return self.symbol < other.symbol

    def __le__(self, other: 'Instrument') -> bool:
        return self.symbol <= other.symbol

    def __gt__(self, other: 'Instrument') -> bool:
        return self.symbol > other.symbol

    def __ge__(self, other: 'Instrument') -> bool:
        return self.symbol >= other.symbol

    def __format__(self, spec: str) -> str:
        return format(self.symbol, spec)

    def __repr__(self) -> str:
        return f'{type(self)!r}(symbol={self.symbol!r}, currency={self.currency!r})'

    def __str__(self) -> str:
        return self._symbol


# Also used for ETFs.
class Stock(Instrument):
    def __init__(self, symbol: str, currency: Currency):
        super().__init__(symbol, currency)


class Bond(Instrument):
    regexCUSIP = r'^[0-9]{3}[0-9A-Z]{5}[0-9]$'

    @classmethod
    def validBondSymbol(cls, symbol: str) -> bool:
        return re.match(cls.regexCUSIP, symbol) is not None

    def __init__(self,
                 symbol: str,
                 currency: Currency,
                 validateSymbol: bool = True):
        if validateSymbol and not self.validBondSymbol(symbol):
            raise ValueError(f'Expected symbol to be a bond CUSIP: {symbol}')

        super().__init__(symbol, currency)


@unique
class OptionType(Enum):
    PUT = 'P'
    CALL = 'C'


class Option(Instrument):
    # Matches the multiplicative factor in OCC options symbology.
    strikeQuantization = Decimal('0.001')

    @classmethod
    def quantizeStrike(cls, strike: Decimal) -> Decimal:
        return strike.quantize(cls.strikeQuantization,
                               rounding=ROUND_HALF_EVEN)

    def __init__(self,
                 underlying: str,
                 currency: Currency,
                 optionType: OptionType,
                 expiration: date,
                 strike: Decimal,
                 multiplier: Decimal = Decimal(100),
                 symbol: Optional[str] = None):
        if not underlying:
            raise ValueError('Expected non-empty underlying symbol for Option')
        if not strike.is_finite() or strike <= 0:
            raise ValueError(f'Expected positive strike price: {strike}')
        if not multiplier.is_finite() or multiplier <= 0:
            raise ValueError(f'Expected positive multiplier: {multiplier}')

        self._underlying = underlying
        self._optionType = optionType
        self._expiration = expiration
        self._strike = self.quantizeStrike(strike)
        self._multiplier = self.quantizeMultiplier(multiplier)

        if symbol is None:
            # https://en.wikipedia.org/wiki/Option_symbol#The_OCC_Option_Symbol
            symbol = f"{underlying:6}{expiration.strftime('%y%m%d')}{optionType.value}{(strike * 1000):08.0f}"

        super().__init__(symbol, currency)

    @property
    def underlying(self) -> str:
        return self._underlying

    @property
    def optionType(self) -> OptionType:
        return self._optionType

    @property
    def expiration(self) -> date:
        return self._expiration

    @property
    def strike(self) -> Decimal:
        return self._strike

    @property
    def multiplier(self) -> Decimal:
        return self._multiplier

    def __repr__(self) -> str:
        return f'{type(self)!r}(underlying={self.underlying!r}, optionType={self.optionType!r}, expiration={self.expiration!r}, strike={self.strike!r}, currency={self.currency!r}, multiplier={self.multiplier!r})'


class FutureOption(Option):
    def __init__(self, symbol: str, underlying: str, currency: Currency,
                 optionType: OptionType, expiration: date, strike: Decimal,
                 multiplier: Decimal):
        super().__init__(underlying=underlying,
                         currency=currency,
                         optionType=optionType,
                         expiration=expiration,
                         strike=strike,
                         multiplier=multiplier,
                         symbol=symbol)


class Future(Instrument):
    def __init__(self, symbol: str, currency: Currency, multiplier: Decimal,
                 expiration: date):
        if not multiplier.is_finite() or multiplier <= 0:
            raise ValueError(f'Expected positive multiplier: {multiplier}')

        self._multiplier = self.quantizeMultiplier(multiplier)
        self._expiration = expiration

        super().__init__(symbol, currency)

    @property
    def multiplier(self) -> Decimal:
        return self._multiplier

    @property
    def expiration(self) -> date:
        return self._expiration

    def __repr__(self) -> str:
        return f'{type(self)!r}(symbol={self.symbol!r}, currency={self.currency!r}, multiplier={self.multiplier!r}, expiration={self.expiration!r})'


class Forex(Instrument):
    def __init__(self, baseCurrency: Currency, quoteCurrency: Currency):
        if baseCurrency == quoteCurrency:
            raise ValueError(
                f'Forex pair must be composed of different currencies, got {baseCurrency!r} and {quoteCurrency!r}'
            )

        self._baseCurrency = baseCurrency
        symbol = f'{baseCurrency.name}{quoteCurrency.name}'
        super().__init__(symbol, quoteCurrency)

    @property
    def quoteCurrency(self) -> Currency:
        return self.currency

    @property
    def baseCurrency(self) -> Currency:
        return self._baseCurrency

    def __repr__(self) -> str:
        return f'{type(self)!r}(baseCurrency={self.baseCurrency!r}, quoteCurrency={self.quoteCurrency!r})'