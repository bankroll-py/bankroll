from abc import ABC, abstractmethod
from dataclasses import dataclass, InitVar
from datetime import date
from enum import Enum, unique
from decimal import Decimal, ROUND_HALF_EVEN
from functools import total_ordering
from typing import Any, ClassVar, Optional

from .cash import Currency

import re


@dataclass(unsafe_hash=True)
@total_ordering
class Instrument(ABC):
    multiplierQuantization: ClassVar[Decimal] = Decimal('0.1')

    symbol: str
    currency: Currency
    multiplier: Decimal
    exchange: Optional[str]

    @classmethod
    def quantizeMultiplier(cls, multiplier: Decimal) -> Decimal:
        return multiplier.quantize(cls.multiplierQuantization,
                                   rounding=ROUND_HALF_EVEN)

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError('Expected non-empty symbol for instrument')
        if not self.currency:
            raise ValueError('Expected currency for instrument')
        if not self.multiplier.is_finite() or self.multiplier <= 0:
            raise ValueError(
                f'Expected positive multiplier: {self.multiplier}')
        if self.exchange is not None and len(self.exchange) == 0:
            raise ValueError(
                f'If an exchange string is provided, it should be non-empty')

        self.multiplier = self.quantizeMultiplier(self.multiplier)

    def __lt__(self, other: 'Instrument') -> bool:
        return self.symbol < other.symbol

    def __format__(self, spec: str) -> str:
        return format(self.symbol, spec)

    def __str__(self) -> str:
        return self.symbol


# Also used for ETFs.
@dataclass(unsafe_hash=True, init=False)
class Stock(Instrument):
    def __init__(self,
                 symbol: str,
                 currency: Currency,
                 exchange: Optional[str] = None):
        super().__init__(symbol=symbol,
                         currency=currency,
                         multiplier=Decimal(1),
                         exchange=exchange)


@dataclass(unsafe_hash=True, init=False)
class Bond(Instrument):
    regexCUSIP: ClassVar[str] = r'^[0-9]{3}[0-9A-Z]{5}[0-9]$'

    @classmethod
    def validBondSymbol(cls, symbol: str) -> bool:
        return re.match(cls.regexCUSIP, symbol) is not None

    def __init__(self,
                 symbol: str,
                 currency: Currency,
                 exchange: Optional[str] = None,
                 validateSymbol: bool = True):
        if validateSymbol and not self.validBondSymbol(symbol):
            raise ValueError(f'Expected symbol to be a bond CUSIP: {symbol}')

        super().__init__(symbol=symbol,
                         currency=currency,
                         multiplier=Decimal(1),
                         exchange=exchange)


@unique
class OptionType(Enum):
    PUT = 'P'
    CALL = 'C'


@dataclass(unsafe_hash=True, init=False)
class Option(Instrument):
    # Matches the multiplicative factor in OCC options symbology.
    strikeQuantization: ClassVar[Decimal] = Decimal('0.001')

    underlying: str
    currency: Currency
    optionType: OptionType
    expiration: date
    strike: Decimal

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
                 exchange: Optional[str] = None,
                 symbol: Optional[str] = None):
        if not underlying:
            raise ValueError('Expected non-empty underlying symbol for Option')
        if not strike.is_finite() or strike <= 0:
            raise ValueError(f'Expected positive strike price: {strike}')
        if not multiplier.is_finite() or multiplier <= 0:
            raise ValueError(f'Expected positive multiplier: {multiplier}')

        self.underlying = underlying
        self.optionType = optionType
        self.expiration = expiration
        self.strike = self.quantizeStrike(strike)

        if symbol is None:
            # https://en.wikipedia.org/wiki/Option_symbol#The_OCC_Option_Symbol
            symbol = f"{underlying:6}{expiration.strftime('%y%m%d')}{optionType.value}{(strike * 1000):08.0f}"

        super().__init__(symbol=symbol,
                         currency=currency,
                         multiplier=multiplier,
                         exchange=exchange)


@dataclass(unsafe_hash=True, init=False)
class FutureOption(Option):
    def __init__(self,
                 symbol: str,
                 underlying: str,
                 currency: Currency,
                 optionType: OptionType,
                 expiration: date,
                 strike: Decimal,
                 multiplier: Decimal,
                 exchange: Optional[str] = None):
        super().__init__(underlying=underlying,
                         currency=currency,
                         optionType=optionType,
                         expiration=expiration,
                         strike=strike,
                         multiplier=multiplier,
                         symbol=symbol,
                         exchange=exchange)


@dataclass(unsafe_hash=True, init=False)
class Future(Instrument):
    expiration: date

    def __init__(self,
                 symbol: str,
                 currency: Currency,
                 multiplier: Decimal,
                 expiration: date,
                 exchange: Optional[str] = None):
        self.expiration = expiration

        super().__init__(symbol=symbol,
                         currency=currency,
                         multiplier=multiplier,
                         exchange=exchange)


@dataclass(unsafe_hash=True, init=False)
class Forex(Instrument):
    baseCurrency: Currency

    def __init__(self,
                 baseCurrency: Currency,
                 quoteCurrency: Currency,
                 exchange: Optional[str] = None):
        if baseCurrency == quoteCurrency:
            raise ValueError(
                f'Forex pair must be composed of different currencies, got {baseCurrency!r} and {quoteCurrency!r}'
            )

        self.baseCurrency = baseCurrency

        symbol = f'{baseCurrency.name}{quoteCurrency.name}'
        super().__init__(symbol=symbol,
                         currency=quoteCurrency,
                         multiplier=Decimal(1),
                         exchange=exchange)

    @property
    def quoteCurrency(self) -> Currency:
        return self.currency
