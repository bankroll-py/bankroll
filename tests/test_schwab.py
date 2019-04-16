from datetime import date
from decimal import Decimal
from itertools import groupby
from model import Cash, Currency, Stock, Bond, Option, OptionType, Position, Trade, TradeFlags
from pathlib import Path

import helpers
import schwab
import unittest


class TestSchwabPositions(unittest.TestCase):
    def setUp(self) -> None:
        self.positions = schwab.parsePositions(
            Path('tests/schwab_positions.CSV'))
        self.positions.sort(key=lambda p: p.instrument.symbol)

    def test_positionValidity(self) -> None:
        self.assertEqual(len(self.positions), 4)

    def test_tBill(self) -> None:
        self.assertEqual(self.positions[0].instrument, Bond('193845XM2'))
        self.assertEqual(self.positions[0].quantity, 10000)
        self.assertEqual(self.positions[0].costBasis,
                         helpers.cashUSD(Decimal('9956.80')))

    def test_bnd(self) -> None:
        self.assertEqual(self.positions[1].instrument, Stock('BND'))
        self.assertEqual(self.positions[1].quantity, Decimal('36.8179'))
        self.assertEqual(self.positions[1].costBasis,
                         helpers.cashUSD(Decimal('1801.19')))

    def test_uvxy(self) -> None:
        self.assertEqual(self.positions[2].instrument, Stock('UVXY'))
        self.assertEqual(self.positions[2].quantity, Decimal('0'))
        self.assertEqual(self.positions[2].costBasis,
                         helpers.cashUSD(Decimal('0')))

    def test_vti(self) -> None:
        self.assertEqual(self.positions[3].instrument, Stock('VTI'))
        self.assertEqual(self.positions[3].quantity, Decimal('48.2304'))
        self.assertEqual(self.positions[3].costBasis,
                         helpers.cashUSD(Decimal('3283.04')))


class TestSchwabTransactions(unittest.TestCase):
    def setUp(self) -> None:
        self.trades = schwab.parseTransactions(
            Path('tests/schwab_transactions.CSV'))
        self.trades.sort(key=lambda t: t.date)

        self.tradesByDate = {
            d: list(t)
            for d, t in groupby(self.trades, key=lambda t: t.date.date())
        }

    def test_tradeValidity(self) -> None:
        self.assertGreater(len(self.trades), 0)

    def test_buySecurity(self) -> None:
        ts = self.tradesByDate[date(2017, 2, 22)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].instrument, Stock('VOO'))
        self.assertEqual(ts[0].quantity, Decimal('23'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('-4981.11')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('6.95')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)

    def test_reinvestShares(self) -> None:
        ts = self.tradesByDate[date(2017, 3, 29)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].instrument, Stock('VOO'))
        self.assertEqual(ts[0].quantity, Decimal('0.1062'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('-22.95')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal(0)))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN | TradeFlags.DRIP)

    def test_shortSaleAndCover(self) -> None:
        ts = self.tradesByDate[date(2018, 1, 2)]
        self.assertEqual(len(ts), 2)

        self.assertEqual(ts[0].instrument, Stock('HD'))
        self.assertEqual(ts[0].quantity, Decimal('-6'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('1017.3')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('4.96')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)

        self.assertEqual(ts[1].instrument, Stock('HD'))
        self.assertEqual(ts[1].quantity, Decimal('6'))
        self.assertEqual(
            ts[1].amount,
            Cash(currency=Currency.USD, quantity=Decimal('-1033.12')))
        self.assertEqual(ts[1].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('4.95')))
        self.assertEqual(ts[1].flags, TradeFlags.CLOSE)

    def test_buyToOpenOption(self) -> None:
        ts = self.tradesByDate[date(2018, 11, 5)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0].instrument,
            Option(underlying='INTC',
                   optionType=OptionType.PUT,
                   expiration=date(2018, 12, 7),
                   strike=Decimal('48.50')))
        self.assertEqual(ts[0].quantity, Decimal('1'))
        self.assertEqual(ts[0].amount,
                         Cash(currency=Currency.USD, quantity=Decimal('-248')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('5.60')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)

    def test_sellToCloseOption(self) -> None:
        ts = self.tradesByDate[date(2018, 11, 9)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0].instrument,
            Option(underlying='INTC',
                   optionType=OptionType.PUT,
                   expiration=date(2018, 12, 7),
                   strike=Decimal('48.50')))
        self.assertEqual(ts[0].quantity, Decimal('-1'))
        self.assertEqual(ts[0].amount,
                         Cash(currency=Currency.USD, quantity=Decimal('140')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('5.60')))
        self.assertEqual(ts[0].flags, TradeFlags.CLOSE)

    def test_exercisedOption(self) -> None:
        ts = self.tradesByDate[date(2018, 2, 4)]
        self.assertEqual(len(ts), 4)
        self.assertEqual(
            ts[2].instrument,
            Option(underlying='QQQ',
                   optionType=OptionType.CALL,
                   expiration=date(2018, 2, 1),
                   strike=Decimal('155')))
        self.assertEqual(ts[2].quantity, Decimal('-1'))
        self.assertEqual(ts[2].amount,
                         Cash(currency=Currency.USD, quantity=Decimal(0)))
        self.assertEqual(ts[2].fees,
                         Cash(currency=Currency.USD, quantity=Decimal(0)))
        self.assertEqual(ts[2].flags,
                         TradeFlags.CLOSE | TradeFlags.ASSIGNED_OR_EXERCISED)

    def test_assignedOption(self) -> None:
        ts = self.tradesByDate[date(2018, 2, 4)]
        self.assertEqual(len(ts), 4)
        self.assertEqual(
            ts[3].instrument,
            Option(underlying='QQQ',
                   optionType=OptionType.CALL,
                   expiration=date(2018, 2, 1),
                   strike=Decimal('130')))
        self.assertEqual(ts[3].quantity, Decimal('1'))
        self.assertEqual(ts[3].amount,
                         Cash(currency=Currency.USD, quantity=Decimal(0)))
        self.assertEqual(ts[3].fees,
                         Cash(currency=Currency.USD, quantity=Decimal(0)))
        self.assertEqual(ts[3].flags,
                         TradeFlags.CLOSE | TradeFlags.ASSIGNED_OR_EXERCISED)

    def test_expiredShortOption(self) -> None:
        ts = self.tradesByDate[date(2018, 12, 3)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0].instrument,
            Option(underlying='CSCO',
                   optionType=OptionType.PUT,
                   expiration=date(2018, 11, 30),
                   strike=Decimal('44.50')))
        self.assertEqual(ts[0].quantity, Decimal('1'))
        self.assertEqual(ts[0].amount,
                         Cash(currency=Currency.USD, quantity=Decimal(0)))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal(0)))
        self.assertEqual(ts[0].flags, TradeFlags.CLOSE | TradeFlags.EXPIRED)

    def test_buyToCloseOption(self) -> None:
        ts = self.tradesByDate[date(2018, 12, 12)]
        self.assertEqual(len(ts), 2)
        self.assertEqual(
            ts[0].instrument,
            Option(underlying='MAR',
                   optionType=OptionType.CALL,
                   expiration=date(2018, 12, 28),
                   strike=Decimal('116')))
        self.assertEqual(ts[0].quantity, Decimal('1'))
        self.assertEqual(ts[0].amount,
                         Cash(currency=Currency.USD, quantity=Decimal('-70')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('5.60')))
        self.assertEqual(ts[0].flags, TradeFlags.CLOSE)

    def test_sellToOpenOption(self) -> None:
        ts = self.tradesByDate[date(2018, 12, 12)]
        self.assertEqual(len(ts), 2)
        self.assertEqual(
            ts[1].instrument,
            Option(underlying='MAR',
                   optionType=OptionType.CALL,
                   expiration=date(2018, 12, 28),
                   strike=Decimal('112')))
        self.assertEqual(ts[1].quantity, Decimal('-1'))
        self.assertEqual(ts[1].amount,
                         Cash(currency=Currency.USD, quantity=Decimal('190')))
        self.assertEqual(ts[1].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('5.60')))
        self.assertEqual(ts[1].flags, TradeFlags.OPEN)

    def test_securityTransferSale(self) -> None:
        ts = self.tradesByDate[date(2018, 1, 4)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].instrument, Stock('MSFT'))
        self.assertEqual(ts[0].quantity, Decimal('-10'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('920.78')))
        self.assertEqual(
            ts[0].fees, Cash(currency=Currency.USD, quantity=Decimal('13.65')))
        self.assertEqual(ts[0].flags, TradeFlags.CLOSE)


if __name__ == '__main__':
    unittest.main()
