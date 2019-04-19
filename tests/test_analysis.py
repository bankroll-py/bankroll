from analysis import realizedBasisForSymbol
from datetime import datetime, date
from decimal import Decimal
from hypothesis import given, reproduce_failure
from hypothesis.strategies import builds, composite, dates, datetimes, decimals, from_type, iterables, just, lists, one_of, text
from model import Cash, Currency, Instrument, Stock, Option, OptionType, Trade, TradeFlags
from typing import Any, Iterable, List, Tuple, no_type_check

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

    @no_type_check
    @given(
        iterables(
            from_type(Trade).filter(lambda t: not t.instrument.symbol.
                                    startswith('SPY'))))
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
