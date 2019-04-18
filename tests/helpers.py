from decimal import Decimal
from hypothesis.strategies import builds, dates, datetimes, decimals, from_regex, from_type, just, integers, one_of, register_type_strategy, sampled_from, text
from model import Cash, Currency, Instrument, Stock, Bond, Option, OptionType, FutureOption, Future, Forex, Position, Trade, TradeFlags, Quote
from typing import List

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

register_type_strategy(
    Cash,
    builds(Cash, currency=from_type(Currency), quantity=decimalCashAmounts))

register_type_strategy(Bond, builds(Bond, symbol=from_regex(Bond.regexCUSIP)))
register_type_strategy(Stock, builds(Stock, symbol=text(min_size=1)))
register_type_strategy(
    Option,
    builds(Option,
           underlying=text(min_size=1),
           optionType=from_type(OptionType),
           expiration=dates(),
           strike=decimals(allow_nan=False,
                           allow_infinity=False,
                           min_value=Decimal('1'),
                           max_value=Decimal('100000'))))
register_type_strategy(
    FutureOption,
    builds(FutureOption,
           symbol=text(min_size=1),
           underlying=text(min_size=1),
           optionType=from_type(OptionType),
           expiration=dates(),
           strike=decimals(allow_nan=False,
                           allow_infinity=False,
                           min_value=Decimal('1'),
                           max_value=Decimal('100000'))))
register_type_strategy(Future, builds(Future, symbol=text(min_size=1)))
register_type_strategy(Forex, builds(Forex, symbol=text(min_size=1)))

register_type_strategy(
    Instrument,
    one_of(from_type(Bond), from_type(Stock), from_type(Option),
           from_type(FutureOption), from_type(Future), from_type(Forex)))

register_type_strategy(
    Position,
    builds(Position,
           instrument=from_type(Instrument),
           quantity=decimalPositionQuantities,
           costBasis=from_type(Cash)))

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
    from_type(Currency).flatmap(lambda cx: builds(
        Trade,
        date=datetimes(),
        instrument=from_type(Instrument),
        quantity=decimalPositionQuantities,
        amount=builds(Cash, currency=just(cx), quantity=decimalCashAmounts),
        fees=builds(Cash,
                    currency=just(cx),
                    quantity=decimals(allow_nan=False,
                                      allow_infinity=False,
                                      min_value=Decimal('0'),
                                      max_value=Decimal('10000'))),
        flags=from_type(TradeFlags))))

register_type_strategy(
    Quote,
    from_type(Cash).flatmap(lambda bid: 
    builds(Quote,
           bid=just(bid),
           ask=builds(Cash, currency=just(bid.currency), quantity=decimalCashAmounts.map(lambda c: bid.quantity + abs(c))),
           last=builds(Cash, currency=just(bid.currency), quantity=decimalCashAmounts))))


def cashUSD(amount: Decimal) -> Cash:
    return Cash(currency=Currency.USD, quantity=amount)


def splitAndStripCSVString(s: str) -> List[str]:
    return list(elem.strip() for elem in s.split(","))
