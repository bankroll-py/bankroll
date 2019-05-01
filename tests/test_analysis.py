from analysis import normalizeSymbol, realizedBasisForSymbol, liveValuesForPositions, deduplicatePositions
from datetime import datetime, date
from decimal import Decimal
from hypothesis import given, reproduce_failure, seed, settings, HealthCheck
from hypothesis.strategies import builds, composite, dates, datetimes, decimals, from_type, iterables, just, lists, one_of, sampled_from, text, tuples, SearchStrategy
from itertools import chain
from model import Cash, Currency, Instrument, Stock, Option, OptionType, Quote, Trade, TradeFlags, LiveDataProvider, Position
from typing import Any, Dict, Iterable, List, Tuple, no_type_check

import helpers
import unittest


@composite
def tradesForAmounts(draw: Any, symbol: str,
                     amounts: Iterable[Decimal]) -> Iterable[Trade]:
    cx = draw(from_type(Currency))
    instruments = one_of(
        builds(Stock, symbol=just(symbol)),
        builds(Option,
               underlying=just(symbol),
               optionType=from_type(OptionType),
               expiration=dates(),
               strike=decimals(allow_nan=False,
                               allow_infinity=False,
                               min_value=Decimal('1'),
                               max_value=Decimal('100000'))))

    return (Trade(
        date=draw(datetimes()),
        instrument=draw(instruments),
        quantity=draw(helpers.positionQuantities()),
        amount=Cash(currency=cx, quantity=x),
        fees=Cash(currency=cx, quantity=Decimal(0)),
        flags=draw(from_type(TradeFlags)),
    ) for x in amounts)


@no_type_check
def positionAndQuote(
        instrument: SearchStrategy[Instrument] = helpers.instruments()
) -> SearchStrategy[Tuple[Position, Quote]]:
    return instrument.flatmap(lambda i: tuples(
        helpers.positions(instrument=just(i),
                          costBasis=helpers.cash(currency=just(i.currency))),
        helpers.uniformCurrencyQuotes(currency=just(i.currency))))


class StubDataProvider(LiveDataProvider):
    def __init__(self, quotes: Dict[Instrument, Quote]):
        self._quotes = quotes
        super().__init__()

    def fetchQuote(self, instrument: Instrument) -> Quote:
        return self._quotes[instrument]


class TestAnalysis(unittest.TestCase):
    def test_realizedBasis(self) -> None:
        trades = [
            Trade(date=datetime.now(),
                  instrument=Stock('SPY', Currency.USD),
                  quantity=Decimal('5'),
                  amount=helpers.cashUSD(Decimal('-999')),
                  fees=helpers.cashUSD(Decimal('1')),
                  flags=TradeFlags.OPEN),
            Trade(date=datetime.now(),
                  instrument=Option(underlying='SPY',
                                    currency=Currency.USD,
                                    optionType=OptionType.CALL,
                                    expiration=date.today(),
                                    strike=Decimal('123')),
                  quantity=Decimal('1'),
                  amount=helpers.cashUSD(Decimal('101')),
                  fees=helpers.cashUSD(Decimal('1')),
                  flags=TradeFlags.OPEN),
        ]

        basis = realizedBasisForSymbol('SPY', trades=trades)
        self.assertEqual(basis, helpers.cashUSD(Decimal('900')))

    separatedSymbols = ['BRK.B', 'BRKB', 'BRK B', 'BRK/B']

    @given(sampled_from(separatedSymbols))
    def test_normalizeSymbol(self, symbol: str) -> None:
        self.assertEqual(normalizeSymbol(symbol), 'BRKB')

    @given(lists(sampled_from(separatedSymbols), min_size=3, max_size=3))
    def test_realizedBasisWithSeparatedSymbol(self,
                                              symbols: List[str]) -> None:
        trades = [
            Trade(date=datetime.now(),
                  instrument=Stock(symbols[0], Currency.USD),
                  quantity=Decimal('5'),
                  amount=helpers.cashUSD(Decimal('-999')),
                  fees=helpers.cashUSD(Decimal('1')),
                  flags=TradeFlags.OPEN),
            Trade(date=datetime.now(),
                  instrument=Option(underlying=symbols[1],
                                    currency=Currency.USD,
                                    optionType=OptionType.CALL,
                                    expiration=date.today(),
                                    strike=Decimal('123')),
                  quantity=Decimal('1'),
                  amount=helpers.cashUSD(Decimal('101')),
                  fees=helpers.cashUSD(Decimal('1')),
                  flags=TradeFlags.OPEN),
        ]

        basis = realizedBasisForSymbol(symbols[2], trades=trades)
        self.assertEqual(basis, helpers.cashUSD(Decimal('900')))

    @no_type_check
    @given(
        iterables(from_type(
            Trade).filter(lambda t: not t.instrument.symbol.startswith('SPY')),
                  max_size=100))
    @settings(suppress_health_check=[HealthCheck.too_slow])
    def test_realizedBasisMissing(self, trades: Iterable[Trade]) -> None:
        self.assertIsNone(realizedBasisForSymbol('SPY', trades))

    @given(from_type(Trade))
    def test_realizedBasisOfOneTradeEqualsCostBasis(self, t: Trade) -> None:
        costBasis = -t.proceeds
        realizedBasis = realizedBasisForSymbol(t.instrument.symbol, [t])
        self.assertEqual(realizedBasis, costBasis)

    # pylint: disable=no-value-for-parameter
    @given(
        lists(helpers.cashAmounts(), min_size=1,
              max_size=20).flatmap(lambda ds: tradesForAmounts(
                  amounts=ds, symbol='SPY').map(lambda ts: (ds, ts))))
    def test_realizedBasisAddsUp(self,
                                 args: Tuple[List[Decimal], Iterable[Trade]]
                                 ) -> None:
        amounts = args[0]
        trades = list(args[1])

        summed = sum(amounts)
        realizedBasis = realizedBasisForSymbol('SPY', trades)
        self.assertIsNotNone(realizedBasis)

        if realizedBasis:
            self.assertEqual(realizedBasis.quantity, -summed)

    @given(lists(positionAndQuote(), min_size=1, max_size=3))
    def test_liveValuesForPositions(self,
                                    i: List[Tuple[Position, Quote]]) -> None:
        quotesByInstrument = {p.instrument: q for (p, q) in i}
        self.assertGreater(len(quotesByInstrument), 0)

        dataProvider = StubDataProvider(quotesByInstrument)
        positions = [p for (p, _) in i]
        self.assertGreater(len(positions), 0)

        valuesByPosition = liveValuesForPositions(positions, dataProvider)
        for position in positions:
            quote = quotesByInstrument[position.instrument]
            prices = [quote.bid, quote.ask, quote.last, quote.close]
            if all([p is None for p in prices]):
                self.assertFalse(position in valuesByPosition)
                continue

            value = valuesByPosition[position]

            valuesPerPrice = [
                p * position.quantity * position.instrument.multiplier
                for p in prices if p is not None
            ]

            lowest = min(valuesPerPrice, default=None)
            if lowest is not None:
                self.assertGreaterEqual(value, lowest)

            highest = max(valuesPerPrice, default=None)
            if highest is not None:
                self.assertLessEqual(value, highest)

    @given(lists(from_type(Position), max_size=10),
           lists(from_type(Position), max_size=10))
    def test_deduplicatePositions(self, a: List[Position],
                                  b: List[Position]) -> None:
        c = chain(a, b)
        instruments = (p.instrument for p in c)
        result = deduplicatePositions(c)

        for i in instruments:
            posA = next((p.quantity for p in a if p.instrument == i),
                        Decimal(0))
            posB = next((p.quantity for p in b if p.instrument == i),
                        Decimal(0))
            posC = next((p.quantity for p in result if p.instrument == i))
            self.assertEqual(posC, Position.quantizeQuantity(posA + posB))