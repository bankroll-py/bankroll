from bankroll import AccountBalance, Cash, Currency, Stock, Bond, Option, OptionType, Position, CashPayment, Trade, TradeFlags
from bankroll.brokers import fidelity
from datetime import date
from decimal import Decimal
from itertools import groupby
from pathlib import Path

from tests import helpers
import unittest


class TestFidelityPositions(unittest.TestCase):
    def setUp(self) -> None:
        self.positions = list(
            fidelity.FidelityAccount(
                positions=Path('tests/fidelity_positions.csv')).positions())
        self.positions.sort(key=lambda p: p.instrument)

    def test_positionValidity(self) -> None:
        self.assertEqual(len(self.positions), 6)

    def test_tBill(self) -> None:
        self.assertEqual(self.positions[0].instrument,
                         Bond('942792RU5', Currency.USD))
        self.assertEqual(self.positions[0].quantity, 10000)
        self.assertEqual(self.positions[0].costBasis,
                         Cash(currency=Currency.USD, quantity=Decimal('9800')))

    def test_aapl(self) -> None:
        self.assertEqual(self.positions[1].instrument,
                         Stock('AAPL', Currency.USD))
        self.assertEqual(self.positions[1].quantity, Decimal('100'))
        self.assertEqual(
            self.positions[1].costBasis,
            Cash(currency=Currency.USD, quantity=Decimal('14000')))

    def test_robo(self) -> None:
        self.assertEqual(self.positions[2].instrument,
                         Stock('ROBO', Currency.USD))
        self.assertEqual(self.positions[2].quantity, Decimal('10'))
        self.assertEqual(self.positions[2].costBasis,
                         Cash(currency=Currency.USD, quantity=Decimal('300')))

    def test_spyCall(self) -> None:
        self.assertEqual(
            self.positions[3].instrument,
            Option(underlying='SPY',
                   currency=Currency.USD,
                   optionType=OptionType.CALL,
                   expiration=date(2019, 1, 25),
                   strike=Decimal('265')))
        self.assertEqual(self.positions[3].quantity, Decimal('1'))
        self.assertEqual(
            self.positions[3].costBasis,
            Cash(currency=Currency.USD, quantity=Decimal('3456.78')))

    def test_spyPut(self) -> None:
        self.assertEqual(
            self.positions[4].instrument,
            Option(underlying='SPY',
                   currency=Currency.USD,
                   optionType=OptionType.PUT,
                   expiration=date(2019, 3, 22),
                   strike=Decimal('189')))
        self.assertEqual(self.positions[4].quantity, Decimal('10'))
        self.assertEqual(
            self.positions[4].costBasis,
            Cash(currency=Currency.USD, quantity=Decimal('5432.78')))

    def test_v(self) -> None:
        self.assertEqual(self.positions[5].instrument,
                         Stock('V', Currency.USD))
        self.assertEqual(self.positions[5].quantity, Decimal('20'))
        self.assertEqual(self.positions[5].costBasis,
                         Cash(currency=Currency.USD, quantity=Decimal('2600')))


class TestFidelityTransactions(unittest.TestCase):
    def setUp(self) -> None:
        self.activity = list(
            fidelity.FidelityAccount(transactions=Path(
                'tests/fidelity_transactions.csv')).activity())
        self.activity.sort(key=lambda t: t.date)

        self.activityByDate = {
            d: list(t)
            for d, t in groupby(self.activity, key=lambda t: t.date.date())
        }

    def test_activityValidity(self) -> None:
        self.assertGreater(len(self.activity), 0)

    def test_buySecurity(self) -> None:
        ts = self.activityByDate[date(2017, 9, 23)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            Trade(date=ts[0].date,
                  instrument=Stock('USFD', Currency.USD),
                  quantity=Decimal('178'),
                  amount=Cash(currency=Currency.USD,
                              quantity=Decimal('-5427.15')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal('4.95')),
                  flags=TradeFlags.OPEN))

    def test_dividendPayment(self) -> None:
        ts = self.activityByDate[date(2017, 11, 9)]
        self.assertEqual(len(ts), 4)
        self.assertEqual(
            ts[1],
            CashPayment(date=ts[1].date,
                        instrument=Stock('ROBO', Currency.USD),
                        proceeds=helpers.cashUSD(Decimal('6.78'))))

    def test_reinvestShares(self) -> None:
        ts = self.activityByDate[date(2017, 11, 9)]
        self.assertEqual(
            ts[2],
            Trade(date=ts[2].date,
                  instrument=Stock('ROBO', Currency.USD),
                  quantity=Decimal('0.234'),
                  amount=Cash(currency=Currency.USD,
                              quantity=Decimal('-6.78')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal('0.00')),
                  flags=TradeFlags.OPEN | TradeFlags.DRIP))

    def test_shortSaleAndCover(self) -> None:
        # TODO: Test short sale and cover trades
        pass

    def test_buyToOpenOption(self) -> None:
        ts = self.activityByDate[date(2017, 8, 26)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            Trade(date=ts[0].date,
                  instrument=Option(underlying='SPY',
                                    currency=Currency.USD,
                                    optionType=OptionType.PUT,
                                    expiration=date(2018, 3, 22),
                                    strike=Decimal('198')),
                  quantity=Decimal('32'),
                  amount=Cash(currency=Currency.USD,
                              quantity=Decimal('-3185.67')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal('25.31')),
                  flags=TradeFlags.OPEN))

    def test_sellToCloseOption(self) -> None:
        ts = self.activityByDate[date(2017, 11, 9)]
        self.assertEqual(
            ts[3],
            Trade(date=ts[3].date,
                  instrument=Option(underlying='SPY',
                                    currency=Currency.USD,
                                    optionType=OptionType.CALL,
                                    expiration=date(2018, 1, 25),
                                    strike=Decimal('260')),
                  quantity=Decimal('-4'),
                  amount=Cash(currency=Currency.USD,
                              quantity=Decimal('94.04')),
                  fees=Cash(currency=Currency.USD, quantity=Decimal('5.03')),
                  flags=TradeFlags.CLOSE))

    def test_exercisedOption(self) -> None:
        # TODO: Test exercised option trades
        pass

    def test_assignedOption(self) -> None:
        # TODO: Test assigned option trades
        pass

    def test_expiredShortOption(self) -> None:
        # TODO: Test expired short option trades
        pass

    def test_buyToCloseOption(self) -> None:
        # TODO: Test buy to close option trades
        pass

    def test_sellToOpenOption(self) -> None:
        # TODO: Test sell to open option trades
        pass

    def test_securityTransferSale(self) -> None:
        # TODO: Test security transfer trades
        pass


class TestFidelityBalance(unittest.TestCase):
    def setUp(self) -> None:
        self.balance = fidelity.FidelityAccount(
            positions=Path('tests/fidelity_positions.csv')).balance()

    def testUSDBalance(self) -> None:
        self.assertEqual(self.balance.cash,
                         {Currency.USD: helpers.cashUSD(Decimal('15678.89'))})


if __name__ == '__main__':
    unittest.main()
