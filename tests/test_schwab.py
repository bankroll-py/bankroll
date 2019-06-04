from bankroll import AccountBalance, Cash, Currency, Stock, Bond, Option, OptionType, Position, CashPayment, Trade, TradeFlags
from bankroll.brokers import schwab
from datetime import date
from decimal import Decimal
from itertools import groupby
from pathlib import Path

from tests import helpers
import unittest


class TestSchwabPositions(unittest.TestCase):
    def setUp(self) -> None:
        self.positions = list(
            schwab.SchwabAccount(
                positions=Path('tests/schwab_positions.CSV')).positions())
        self.positions.sort(key=lambda p: p.instrument.symbol)

    def test_positionValidity(self) -> None:
        self.assertEqual(len(self.positions), 4)

    def test_tBill(self) -> None:
        self.assertEqual(self.positions[0].instrument,
                         Bond('193845XM2', Currency.USD))
        self.assertEqual(self.positions[0].quantity, 10000)
        self.assertEqual(self.positions[0].costBasis,
                         helpers.cashUSD(Decimal('9956.80')))

    def test_bnd(self) -> None:
        self.assertEqual(self.positions[1].instrument,
                         Stock('BND', Currency.USD))
        self.assertEqual(self.positions[1].quantity, Decimal('36.8179'))
        self.assertEqual(self.positions[1].costBasis,
                         helpers.cashUSD(Decimal('1801.19')))

    def test_uvxy(self) -> None:
        self.assertEqual(self.positions[2].instrument,
                         Stock('UVXY', Currency.USD))
        self.assertEqual(self.positions[2].quantity, Decimal('0'))
        self.assertEqual(self.positions[2].costBasis,
                         helpers.cashUSD(Decimal('0')))

    def test_vti(self) -> None:
        self.assertEqual(self.positions[3].instrument,
                         Stock('VTI', Currency.USD))
        self.assertEqual(self.positions[3].quantity, Decimal('48.2304'))
        self.assertEqual(self.positions[3].costBasis,
                         helpers.cashUSD(Decimal('3283.04')))


class TestSchwabTransactions(unittest.TestCase):
    def setUp(self) -> None:
        self.activity = list(
            schwab.SchwabAccount(
                transactions=Path('tests/schwab_transactions.CSV')).activity())
        self.activity.sort(key=lambda t: t.date)

        self.activityByDate = {
            d: list(t)
            for d, t in groupby(self.activity, key=lambda t: t.date.date())
        }

    def test_activityValidity(self) -> None:
        self.assertGreater(len(self.activity), 0)

    def test_buyBond(self) -> None:
        ts = self.activityByDate[date(2018, 3, 25)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            Trade(date=ts[0].date,
                  instrument=Bond(symbol='912586AC5', currency=Currency.USD),
                  quantity=Decimal('10000'),
                  amount=Cash(currency=Currency.USD,
                              quantity=Decimal('-9956.80')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal(0)),
                  flags=TradeFlags.OPEN))

    def test_redeemBond(self) -> None:
        ts = self.activityByDate[date(2018, 6, 2)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            Trade(date=ts[0].date,
                  instrument=Bond(symbol='912586AC5', currency=Currency.USD),
                  quantity=Decimal('-10000'),
                  amount=Cash(currency=Currency.USD,
                              quantity=Decimal('10000')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal(0)),
                  flags=TradeFlags.CLOSE | TradeFlags.EXPIRED))

    def test_buyStock(self) -> None:
        ts = self.activityByDate[date(2017, 2, 22)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            Trade(date=ts[0].date,
                  instrument=Stock('VOO', Currency.USD),
                  quantity=Decimal('23'),
                  amount=Cash(currency=Currency.USD,
                              quantity=Decimal('-4981.11')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal('6.95')),
                  flags=TradeFlags.OPEN))

    def test_dividendReinvested(self) -> None:
        ts = self.activityByDate[date(2017, 3, 28)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            CashPayment(date=ts[0].date,
                        instrument=Stock('VOO', Currency.USD),
                        proceeds=helpers.cashUSD(Decimal('22.95'))))

    def test_cashDividend(self) -> None:
        ts = self.activityByDate[date(2018, 3, 6)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            CashPayment(date=ts[0].date,
                        instrument=Stock('VGLT', Currency.USD),
                        proceeds=helpers.cashUSD(Decimal('12.85'))))

    def test_reinvestShares(self) -> None:
        ts = self.activityByDate[date(2017, 3, 29)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            Trade(date=ts[0].date,
                  instrument=Stock('VOO', Currency.USD),
                  quantity=Decimal('0.1062'),
                  amount=Cash(currency=Currency.USD,
                              quantity=Decimal('-22.95')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal(0)),
                  flags=TradeFlags.OPEN | TradeFlags.DRIP))

    def test_shortSaleAndCover(self) -> None:
        ts = self.activityByDate[date(2018, 1, 2)]
        self.assertEqual(len(ts), 2)

        self.assertEqual(
            ts[0],
            Trade(date=ts[0].date,
                  instrument=Stock('HD', Currency.USD),
                  quantity=Decimal('-6'),
                  amount=Cash(currency=Currency.USD,
                              quantity=Decimal('1017.3')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal('4.96')),
                  flags=TradeFlags.OPEN))

        self.assertEqual(
            ts[1],
            Trade(date=ts[1].date,
                  instrument=Stock('HD', Currency.USD),
                  quantity=Decimal('6'),
                  amount=Cash(currency=Currency.USD,
                              quantity=Decimal('-1033.12')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal('4.95')),
                  flags=TradeFlags.CLOSE))

    def test_buyToOpenOption(self) -> None:
        ts = self.activityByDate[date(2018, 11, 5)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            Trade(date=ts[0].date,
                  instrument=Option(underlying='INTC',
                                    currency=Currency.USD,
                                    optionType=OptionType.PUT,
                                    expiration=date(2018, 12, 7),
                                    strike=Decimal('48.50')),
                  quantity=Decimal('1'),
                  amount=Cash(currency=Currency.USD, quantity=Decimal('-248')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal('5.60')),
                  flags=TradeFlags.OPEN))

    def test_sellToCloseOption(self) -> None:
        ts = self.activityByDate[date(2018, 11, 9)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            Trade(date=ts[0].date,
                  instrument=Option(underlying='INTC',
                                    currency=Currency.USD,
                                    optionType=OptionType.PUT,
                                    expiration=date(2018, 12, 7),
                                    strike=Decimal('48.50')),
                  quantity=Decimal('-1'),
                  amount=Cash(currency=Currency.USD, quantity=Decimal('140')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal('5.60')),
                  flags=TradeFlags.CLOSE))

    def test_exercisedOption(self) -> None:
        ts = self.activityByDate[date(2018, 2, 4)]
        self.assertEqual(len(ts), 4)
        self.assertEqual(
            ts[2],
            Trade(date=ts[2].date,
                  instrument=Option(underlying='QQQ',
                                    currency=Currency.USD,
                                    optionType=OptionType.CALL,
                                    expiration=date(2018, 2, 1),
                                    strike=Decimal('155')),
                  quantity=Decimal('-1'),
                  amount=Cash(currency=Currency.USD, quantity=Decimal(0)),
                  fees=Cash(currency=Currency.USD, quantity=Decimal(0)),
                  flags=TradeFlags.CLOSE | TradeFlags.ASSIGNED_OR_EXERCISED))

    def test_assignedOption(self) -> None:
        ts = self.activityByDate[date(2018, 2, 4)]
        self.assertEqual(len(ts), 4)
        self.assertEqual(
            ts[3],
            Trade(date=ts[3].date,
                  instrument=Option(underlying='QQQ',
                                    currency=Currency.USD,
                                    optionType=OptionType.CALL,
                                    expiration=date(2018, 2, 1),
                                    strike=Decimal('130')),
                  quantity=Decimal('1'),
                  amount=Cash(currency=Currency.USD, quantity=Decimal(0)),
                  fees=Cash(currency=Currency.USD, quantity=Decimal(0)),
                  flags=TradeFlags.CLOSE | TradeFlags.ASSIGNED_OR_EXERCISED))

    def test_expiredShortOption(self) -> None:
        ts = self.activityByDate[date(2018, 12, 3)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            Trade(date=ts[0].date,
                  instrument=Option(underlying='CSCO',
                                    currency=Currency.USD,
                                    optionType=OptionType.PUT,
                                    expiration=date(2018, 11, 30),
                                    strike=Decimal('44.50')),
                  quantity=Decimal('1'),
                  amount=Cash(currency=Currency.USD, quantity=Decimal(0)),
                  fees=Cash(currency=Currency.USD, quantity=Decimal(0)),
                  flags=TradeFlags.CLOSE | TradeFlags.EXPIRED))

    def test_buyToCloseOption(self) -> None:
        ts = self.activityByDate[date(2018, 12, 12)]
        self.assertEqual(len(ts), 2)
        self.assertEqual(
            ts[0],
            Trade(date=ts[0].date,
                  instrument=Option(underlying='MAR',
                                    currency=Currency.USD,
                                    optionType=OptionType.CALL,
                                    expiration=date(2018, 12, 28),
                                    strike=Decimal('116')),
                  quantity=Decimal('1'),
                  amount=Cash(currency=Currency.USD, quantity=Decimal('-70')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal('5.60')),
                  flags=TradeFlags.CLOSE))

    def test_sellToOpenOption(self) -> None:
        ts = self.activityByDate[date(2018, 12, 12)]
        self.assertEqual(len(ts), 2)
        self.assertEqual(
            ts[1],
            Trade(date=ts[1].date,
                  instrument=Option(underlying='MAR',
                                    currency=Currency.USD,
                                    optionType=OptionType.CALL,
                                    expiration=date(2018, 12, 28),
                                    strike=Decimal('112')),
                  quantity=Decimal('-1'),
                  amount=Cash(currency=Currency.USD, quantity=Decimal('190')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal('5.60')),
                  flags=TradeFlags.OPEN))

    def test_securityTransferSale(self) -> None:
        ts = self.activityByDate[date(2018, 1, 4)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            Trade(date=ts[0].date,
                  instrument=Stock('MSFT', Currency.USD),
                  quantity=Decimal('-10'),
                  amount=Cash(currency=Currency.USD,
                              quantity=Decimal('920.78')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal('13.65')),
                  flags=TradeFlags.CLOSE))


class TestSchwabBalance(unittest.TestCase):
    def setUp(self) -> None:
        self.balance = schwab.SchwabAccount(
            positions=Path('tests/schwab_positions.CSV')).balance()

    def testUSDBalance(self) -> None:
        self.assertEqual(self.balance.cash,
                         {Currency.USD: helpers.cashUSD(Decimal('500.21'))})


if __name__ == '__main__':
    unittest.main()
