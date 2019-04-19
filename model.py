from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_EVEN
from enum import Enum, Flag, auto, unique
from itertools import permutations
from typing import Any, Dict, Iterable, NamedTuple, Optional, TypeVar, Union

import re


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
        if quantity < 0:
            return '({})'.format(self.format(abs(quantity)))

        if self == Currency.USD:
            return '${:,.2f}'.format(quantity)
        elif self == Currency.GBP:
            return '£{:,.2f}'.format(quantity)
        elif self == Currency.AUD:
            return 'AU${:,.2f}'.format(quantity)
        elif self == Currency.EUR:
            return '€{:,.2f}'.format(quantity)
        elif self == Currency.JPY:
            return '¥{:,.0f}'.format(quantity)
        elif self == Currency.CAD:
            return 'C${:,.2f}'.format(quantity)
        elif self == Currency.NZD:
            return 'NZ${:,.2f}'.format(quantity)
        else:
            return '{} {:,}'.format(self.value, quantity)


T = TypeVar('T', Decimal, int)


class Cash:
    quantization = Decimal('0.0001')

    @classmethod
    def quantize(cls, d: Decimal) -> Decimal:
        return d.quantize(cls.quantization, rounding=ROUND_HALF_EVEN)

    def __init__(self, currency: Currency, quantity: Decimal):
        assert quantity.is_finite(
        ), 'Cash quantity {} is not a finite number'.format(quantity)

        self._currency = currency
        self._quantity = self.quantize(quantity)
        super().__init__()

    @property
    def currency(self) -> Currency:
        return self._currency

    @property
    def quantity(self) -> Decimal:
        return self._quantity

    def __repr__(self) -> str:
        return 'Cash(currency={}, quantity={})'.format(repr(self.currency),
                                                       repr(self.quantity))

    def __str__(self) -> str:
        return self.currency.format(self.quantity)

    def __add__(self, other: Any) -> 'Cash':
        if isinstance(other, Cash):
            assert self.currency == other.currency, 'Currency of {} must match {} for addition'.format(
                self, other)

            return Cash(currency=self.currency,
                        quantity=self.quantity + other.quantity)
        else:
            return Cash(currency=self.currency, quantity=self.quantity + other)

    def __sub__(self, other: Any) -> 'Cash':
        if isinstance(other, Cash):
            assert self.currency == other.currency, 'Currency of {} does not match {} for subtraction'.format(
                self, other)

            return Cash(currency=self.currency,
                        quantity=self.quantity - other.quantity)
        else:
            return Cash(currency=self.currency, quantity=self.quantity - other)

    def __mul__(self, other: T) -> 'Cash':
        return Cash(currency=self.currency, quantity=self.quantity * other)

    def __truediv__(self, other: T) -> 'Cash':
        return Cash(currency=self.currency, quantity=self.quantity / other)

    def __neg__(self) -> 'Cash':
        return Cash(currency=self.currency, quantity=-self.quantity)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Cash):
            # Make mypy happy
            b: bool = self.quantity == other
            return b

        return self.currency == other.currency and self.quantity == other.quantity

    def __lt__(self, other: 'Cash') -> bool:
        assert self.currency == other.currency, 'Currency of {} must match {} for comparison'.format(
            self, other)
        return self.quantity < other.quantity

    def __le__(self, other: 'Cash') -> bool:
        assert self.currency == other.currency, 'Currency of {} must match {} for comparison'.format(
            self, other)
        return self.quantity <= other.quantity

    def __gt__(self, other: 'Cash') -> bool:
        assert self.currency == other.currency, 'Currency of {} must match {} for comparison'.format(
            self, other)
        return self.quantity > other.quantity

    def __ge__(self, other: 'Cash') -> bool:
        assert self.currency == other.currency, 'Currency of {} must match {} for comparison'.format(
            self, other)
        return self.quantity >= other.quantity

    def __hash__(self) -> int:
        return hash((self.currency, self.quantity))


class Instrument(ABC):
    multiplierQuantization = Decimal('0.1')

    @classmethod
    def quantizeMultiplier(cls, multiplier: Decimal) -> Decimal:
        return multiplier.quantize(cls.multiplierQuantization,
                                   rounding=ROUND_HALF_EVEN)

    @abstractmethod
    def __init__(self, symbol: str, currency: Currency):
        assert symbol, 'Expected non-empty symbol for instrument'
        assert currency, 'Expected currency for instrument'

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
        return '{}(symbol={}, currency={})'.format(repr(type(self)),
                                                   repr(self.symbol),
                                                   repr(self.currency))

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
        assert not validateSymbol or self.validBondSymbol(
            symbol), 'Expected symbol to be a bond CUSIP: {}'.format(symbol)

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
        assert underlying, 'Expected non-empty underlying symbol for Option'
        assert strike.is_finite(
        ) and strike > 0, 'Expected positive strike price: {}'.format(strike)
        assert multiplier.is_finite(
        ) and multiplier > 0, 'Expected positive multiplier: {}'.format(
            multiplier)

        self._underlying = underlying
        self._optionType = optionType
        self._expiration = expiration
        self._strike = self.quantizeStrike(strike)
        self._multiplier = self.quantizeMultiplier(multiplier)

        if symbol is None:
            # https://en.wikipedia.org/wiki/Option_symbol#The_OCC_Option_Symbol
            symbol = '{:6}{}{}{:08.0f}'.format(underlying,
                                               expiration.strftime('%y%m%d'),
                                               optionType.value, strike * 1000)

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
        return '{}(underlying={}, optionType={}, expiration={}, strike={}, currency={}, multiplier={})'.format(
            repr(type(self)), repr(self.underlying), repr(self.optionType),
            repr(self.expiration), repr(self.strike), repr(self.currency),
            repr(self.multiplier))


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
    def __init__(self, symbol: str, currency: Currency, multiplier: Decimal):
        assert multiplier.is_finite(
        ) and multiplier > 0, 'Expected positive multiplier: {}'.format(
            multiplier)

        self._multiplier = self.quantizeMultiplier(multiplier)

        super().__init__(symbol, currency)

    @property
    def multiplier(self) -> Decimal:
        return self._multiplier


class Forex(Instrument):
    def __init__(self, baseCurrency: Currency, quoteCurrency: Currency):
        assert baseCurrency != quoteCurrency, 'Forex pair must be composed of different currencies, got {} and {}'.format(
            repr(baseCurrency), repr(quoteCurrency))
        self._baseCurrency = baseCurrency

        symbol = '{}{}'.format(baseCurrency.name, quoteCurrency.name)
        super().__init__(symbol, quoteCurrency)

    @property
    def quoteCurrency(self) -> Currency:
        return self.currency

    @property
    def baseCurrency(self) -> Currency:
        return self._baseCurrency

    def __repr__(self) -> str:
        return '{}(baseCurrency={}, quoteCurrency={})'.format(
            repr(type(self)), repr(self.baseCurrency),
            repr(self.quoteCurrency))


Item = TypeVar('Item')


def allEqual(i: Iterable[Item]) -> bool:
    for (a, b) in permutations(i, 2):
        if a != b:
            return False

    return True


class Quote:
    def __init__(self,
                 bid: Optional[Cash] = None,
                 ask: Optional[Cash] = None,
                 last: Optional[Cash] = None,
                 close: Optional[Cash] = None):
        if bid and ask:
            assert ask >= bid, 'Expected ask {} to be at least bid {}'.format(
                ask, bid)

        assert allEqual((price.currency for price in [bid, ask, last, close]
                         if price is not None
                         )), 'Currencies in a quote should match: {}'.format(
                             [bid, ask, last, close])

        self._bid = bid
        self._ask = ask
        self._last = last
        self._close = close
        super().__init__()

    @property
    def bid(self) -> Optional[Cash]:
        return self._bid

    @property
    def ask(self) -> Optional[Cash]:
        return self._ask

    @property
    def last(self) -> Optional[Cash]:
        return self._last

    @property
    def close(self) -> Optional[Cash]:
        return self._close

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Quote):
            return False

        return self.bid == other.bid and self.ask == other.ask and self.last == other.last and self.close == other.close

    def __hash__(self) -> int:
        return hash((self.bid, self.ask, self.last, self.close))


class LiveDataProvider(ABC):
    @abstractmethod
    def fetchQuote(self, instrument: Instrument) -> Quote:
        pass


class Position:
    quantityQuantization = Decimal('0.0001')

    @classmethod
    def quantizeQuantity(cls, quantity: Decimal) -> Decimal:
        return quantity.quantize(cls.quantityQuantization,
                                 rounding=ROUND_HALF_EVEN)

    def __init__(self, instrument: Instrument, quantity: Decimal,
                 costBasis: Cash):
        assert instrument.currency == costBasis.currency, 'Cost basis {} should be in same currency as instrument {}'.format(
            costBasis, instrument)
        assert quantity.is_finite()
        quantity = self.quantizeQuantity(quantity)

        assert quantity != 0 or costBasis == 0, 'Cost basis {} should be zero if quantity is zero'.format(
            repr(costBasis))

        self._instrument = instrument
        self._quantity = quantity
        self._costBasis = costBasis
        super().__init__()

    def combine(self, other: 'Position') -> 'Position':
        assert self.instrument == other.instrument, 'Cannot combine positions in two different instruments: {} and {}'.format(
            self.instrument, other.instrument)

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
        return 'Position(instrument={}, quantity={}, costBasis={})'.format(
            repr(self.instrument), repr(self.quantity), repr(self.costBasis))

    def __str__(self) -> str:
        return '{:21} {:>14,f} @ {}'.format(self.instrument,
                                            self.quantity.normalize(),
                                            self.averagePrice)


class TradeFlags(Flag):
    NONE = 0
    OPEN = auto()
    CLOSE = auto()

    DRIP = auto()  # Dividend reinvestment

    EXPIRED = auto()
    ASSIGNED_OR_EXERCISED = auto()  # Sign of quantity will indicate which


class Trade:
    @classmethod
    def quantizeQuantity(cls, quantity: Decimal) -> Decimal:
        return Position.quantizeQuantity(quantity)

    def __init__(self, date: datetime, instrument: Instrument,
                 quantity: Decimal, amount: Cash, fees: Cash,
                 flags: TradeFlags):
        assert quantity.is_finite()
        assert flags in [
            TradeFlags.OPEN, TradeFlags.CLOSE,
            TradeFlags.OPEN | TradeFlags.DRIP,
            TradeFlags.OPEN | TradeFlags.ASSIGNED_OR_EXERCISED,
            TradeFlags.CLOSE | TradeFlags.EXPIRED,
            TradeFlags.CLOSE | TradeFlags.ASSIGNED_OR_EXERCISED
        ], 'Invalid combination of flags: {}'.format(flags)

        self._date = date
        self._instrument = instrument
        self._quantity = self.quantizeQuantity(quantity)
        self._amount = amount
        self._fees = fees
        self._flags = flags
        super().__init__()

    @property
    def date(self) -> datetime:
        return self._date

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
        if not isinstance(other, Trade):
            return False

        return bool(self.date == other.date
                    and self.instrument == other.instrument
                    and self.quantity == other.quantity
                    and self.amount == other.amount and self.fees == other.fees
                    and self.flags == other.flags)

    def __hash__(self) -> int:
        return hash((self.date, self.instrument, self.quantity, self.amount,
                     self.fees, self.flags))

    def __repr__(self) -> str:
        return 'Trade(date={}, instrument={}, quantity={}, amount={}, fees={}, flags={})'.format(
            repr(self.date), repr(self.instrument), repr(self.quantity),
            repr(self.amount), repr(self.fees), repr(self.flags))

    def __str__(self) -> str:
        if self.quantity > 0:
            action = 'Buy'
        else:
            action = 'Sell'

        return '{} {} {} {}: {} (before {} in fees)'.format(
            self.date.date(), action, abs(self.quantity), self.instrument,
            self.amount, self.fees)

    def _replace(self, **kwargs: Any) -> 'Trade':
        vals: Dict[str, Any] = {
            k.lstrip('_'): v
            for k, v in self.__dict__.items()
        }
        vals.update(kwargs)

        return Trade(**vals)
