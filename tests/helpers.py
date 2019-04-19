from datetime import date, datetime
from decimal import Decimal
from hypothesis.strategies import builds, dates, datetimes, decimals, from_regex, from_type, just, lists, integers, none, one_of, register_type_strategy, sampled_from, text, SearchStrategy
from model import Cash, Currency, Instrument, Stock, Bond, Option, OptionType, FutureOption, Future, Forex, Position, Trade, TradeFlags, Quote
from typing import List, Optional, TypeVar

T = TypeVar('T')


def optionals(inner: SearchStrategy[T]) -> SearchStrategy[Optional[T]]:
    return one_of(inner, none())


decimalCashAmounts = decimals(allow_nan=False,
                              allow_infinity=False,
                              min_value=Decimal('-1000000000'),
                              max_value=Decimal('1000000000')).map(
                                  Cash.quantize)

decimalPositionQuantities = decimals(
    allow_nan=False,
    allow_infinity=False,
    min_value=Decimal('-1000000000'),
    max_value=Decimal('1000000000')).map(
        Position.quantizeQuantity).filter(lambda x: x != 0)

decimalMultipliers = decimals(allow_nan=False,
                              allow_infinity=False,
                              min_value=Decimal('1'),
                              max_value=Decimal('10000')).map(
                                  Instrument.quantizeMultiplier)


def cash(currency: SearchStrategy[Currency] = from_type(Currency),
         quantity: SearchStrategy[Decimal] = decimalCashAmounts
         ) -> SearchStrategy[Cash]:
    return builds(Cash, currency=currency, quantity=quantity)


def bonds(symbol: SearchStrategy[str] = from_regex(Bond.regexCUSIP),
          currency: SearchStrategy[Currency] = from_type(Currency)
          ) -> SearchStrategy[Bond]:
    return builds(Bond, symbol=symbol, currency=currency)


def stocks(symbol: SearchStrategy[str] = text(min_size=1),
           currency: SearchStrategy[Currency] = from_type(Currency)
           ) -> SearchStrategy[Stock]:
    return builds(Stock, symbol=symbol, currency=currency)


def options(underlying: SearchStrategy[str] = text(min_size=1),
            currency: SearchStrategy[Currency] = from_type(Currency),
            optionType: SearchStrategy[OptionType] = from_type(OptionType),
            expiration: SearchStrategy[date] = dates(),
            strike: SearchStrategy[Decimal] = decimals(
                allow_nan=False,
                allow_infinity=False,
                min_value=Decimal('1'),
                max_value=Decimal('100000')),
            multiplier: SearchStrategy[Decimal] = decimalMultipliers
            ) -> SearchStrategy[Option]:
    return builds(Option,
                  underlying=underlying,
                  currency=currency,
                  optionType=optionType,
                  expiration=expiration,
                  strike=strike,
                  multiplier=multiplier)


def futuresOptions(
        symbol: SearchStrategy[str] = text(min_size=1),
        underlying: SearchStrategy[str] = text(min_size=1),
        currency: SearchStrategy[Currency] = from_type(Currency),
        optionType: SearchStrategy[OptionType] = from_type(OptionType),
        expiration: SearchStrategy[date] = dates(),
        strike: SearchStrategy[Decimal] = decimals(
            allow_nan=False,
            allow_infinity=False,
            min_value=Decimal('1'),
            max_value=Decimal('100000')),
        multiplier: SearchStrategy[Decimal] = decimalMultipliers
) -> SearchStrategy[FutureOption]:
    return builds(FutureOption,
                  symbol=symbol,
                  underlying=underlying,
                  currency=currency,
                  optionType=optionType,
                  expiration=expiration,
                  strike=strike,
                  multiplier=multiplier)


def futures(symbol: SearchStrategy[str] = text(min_size=1),
            currency: SearchStrategy[Currency] = from_type(Currency),
            multiplier: SearchStrategy[Decimal] = decimalMultipliers
            ) -> SearchStrategy[Future]:
    return builds(Future,
                  symbol=symbol,
                  currency=currency,
                  multiplier=multiplier)


def forex(baseCurrency: SearchStrategy[Currency] = from_type(Currency),
          quoteCurrency: SearchStrategy[Currency] = from_type(Currency)
          ) -> SearchStrategy[Forex]:
    return builds(Forex,
                  baseCurrency=baseCurrency,
                  quoteCurrency=quoteCurrency)


def instruments(currency: SearchStrategy[Currency] = from_type(Currency)
                ) -> SearchStrategy[Instrument]:
    return one_of(
        bonds(currency=currency), stocks(currency=currency),
        options(currency=currency), futuresOptions(currency=currency),
        futures(currency=currency),
        currency.flatmap(lambda cur: forex(baseCurrency=from_type(Currency).
                                           filter(lambda cur2: cur2 != cur),
                                           quoteCurrency=just(cur))))


def positions(instrument: SearchStrategy[Instrument] = instruments(),
              quantity: SearchStrategy[Decimal] = decimalPositionQuantities,
              costBasis: SearchStrategy[Cash] = cash()
              ) -> SearchStrategy[Position]:
    return builds(Position,
                  instrument=instrument,
                  quantity=quantity,
                  costBasis=costBasis)


def trades(date: SearchStrategy[datetime] = datetimes(),
           instrument: SearchStrategy[Instrument] = instruments(),
           quantity: SearchStrategy[Decimal] = decimalPositionQuantities,
           amount: SearchStrategy[Cash] = cash(),
           fees: SearchStrategy[Cash] = cash(
               quantity=decimals(allow_nan=False,
                                 allow_infinity=False,
                                 min_value=Decimal('0'),
                                 max_value=Decimal('10000'))),
           flags: SearchStrategy[TradeFlags] = from_type(TradeFlags)
           ) -> SearchStrategy[Trade]:
    return builds(Trade,
                  date=date,
                  instrument=instrument,
                  quantity=quantity,
                  amount=amount,
                  fees=fees,
                  flags=flags)


def quotes(bid: SearchStrategy[Optional[Cash]] = optionals(cash()),
           ask: SearchStrategy[Optional[Cash]] = optionals(cash()),
           last: SearchStrategy[Optional[Cash]] = optionals(cash()),
           close: SearchStrategy[Optional[Cash]] = optionals(cash())
           ) -> SearchStrategy[Quote]:
    return builds(Quote, bid=bid, ask=ask, last=last, close=close)


register_type_strategy(Cash, cash())
register_type_strategy(Bond, bonds())
register_type_strategy(Stock, stocks())
register_type_strategy(Option, options())
register_type_strategy(FutureOption, futuresOptions())
register_type_strategy(Future, futures())

register_type_strategy(
    Forex,
    lists(from_type(Currency), min_size=2, max_size=2,
          unique=True).flatmap(lambda cx: forex(baseCurrency=just(cx[0]),
                                                quoteCurrency=just(cx[1]))))

register_type_strategy(Instrument, instruments())

register_type_strategy(
    Position,
    from_type(Instrument).flatmap(lambda i: positions(
        instrument=just(i), costBasis=cash(currency=just(i.currency)))))

register_type_strategy(
    TradeFlags,
    sampled_from([
        TradeFlags.OPEN, TradeFlags.CLOSE, TradeFlags.OPEN | TradeFlags.DRIP,
        TradeFlags.OPEN | TradeFlags.ASSIGNED_OR_EXERCISED,
        TradeFlags.CLOSE | TradeFlags.EXPIRED,
        TradeFlags.CLOSE | TradeFlags.ASSIGNED_OR_EXERCISED
    ]))

register_type_strategy(
    Trade,
    from_type(Instrument).flatmap(lambda i: trades(
        instrument=just(i),
        amount=cash(currency=just(i.currency)),
        fees=cash(currency=just(i.currency),
                  quantity=decimals(allow_nan=False,
                                    allow_infinity=False,
                                    min_value=Decimal('0'),
                                    max_value=Decimal('10000'))))))

register_type_strategy(
    Quote,
    from_type(Cash).flatmap(lambda bid: quotes(
        bid=optionals(just(bid)),
        ask=optionals(
            cash(currency=just(bid.currency),
                 quantity=decimalCashAmounts.map(lambda c: bid.quantity + abs(
                     c)))),
        last=optionals(cash(currency=just(bid.currency))),
        close=optionals(cash(currency=just(bid.currency))))))


def cashUSD(amount: Decimal) -> Cash:
    return Cash(currency=Currency.USD, quantity=amount)


def splitAndStripCSVString(s: str) -> List[str]:
    return list(elem.strip() for elem in s.split(","))
