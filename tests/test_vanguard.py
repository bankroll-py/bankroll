from datetime import date
from decimal import Decimal
from itertools import groupby
from model import Bond, Cash, Currency, Instrument, Position, Stock, Trade, TradeFlags
from pathlib import Path

import helpers
import unittest
import vanguard


class TestVanguardPositions(unittest.TestCase):
    def setUp(self) -> None:
        self.positions = vanguard.parsePositionsAndTrades(
            Path('tests/vanguard_positions_and_transactions.csv')).positions
        self.positions.sort(key=lambda p: p.instrument.symbol)

    def test_positionValidity(self) -> None:
        self.assertEqual(len(self.positions), 6)

    def test_tBill(self) -> None:
        self.assertEqual(
            self.positions[0].instrument,
            Bond(
                "U S TREASURY BILL CPN  0.00000 % MTD 2017-04-10 DTD 2017-08-14",
                validateSymbol=False))
        self.assertEqual(self.positions[0].quantity, 5000)
        # TODO: Validate cost basis

    def test_vmfxx(self) -> None:
        self.assertEqual(self.positions[1].instrument, Stock("VMFXX"))
        self.assertEqual(self.positions[1].quantity, Decimal('543.21'))
        # TODO: Validate cost basis

    def test_voo(self) -> None:
        self.assertEqual(self.positions[2].instrument, Stock("VOO"))
        self.assertEqual(self.positions[2].quantity, Decimal('100.1'))
        # TODO: Validate cost basis

    def test_vt(self) -> None:
        self.assertEqual(self.positions[3].instrument, Stock("VT"))
        self.assertEqual(self.positions[3].quantity, Decimal('10'))
        # TODO: Validate cost basis

    def test_vti(self) -> None:
        self.assertEqual(self.positions[4].instrument, Stock("VTI"))
        self.assertEqual(self.positions[4].quantity, Decimal('50.5'))
        # TODO: Validate cost basis

    def test_vbr(self) -> None:
        self.assertEqual(self.positions[5].instrument, Stock("VWO"))
        self.assertEqual(self.positions[5].quantity, 20)
        # TODO: Validate cost basis


class TestVanguardTransactions(unittest.TestCase):
    def setUp(self) -> None:
        self.trades = vanguard.parsePositionsAndTrades(
            Path('tests/vanguard_positions_and_transactions.csv')).trades
        self.trades.sort(key=lambda t: t.date)

        self.tradesByDate = {
            d: list(t)
            for d, t in groupby(self.trades, key=lambda t: t.date.date())
        }

    def test_tradeValidity(self) -> None:
        self.assertGreater(len(self.trades), 0)

    def test_buySecurity(self) -> None:
        ts = self.tradesByDate[date(2016, 4, 20)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].instrument, Stock('VTI'))
        self.assertEqual(ts[0].quantity, Decimal('12'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('-3456.78')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('0.00')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)

    def test_sellSecurity(self) -> None:
        ts = self.tradesByDate[date(2016, 10, 13)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].instrument, Stock('VWO'))
        self.assertEqual(ts[0].quantity, Decimal('-4'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('1234.56')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('0.00')))
        self.assertEqual(ts[0].flags, TradeFlags.CLOSE)

    def test_redeemTBill(self) -> None:
        ts = self.tradesByDate[date(2017, 9, 23)]
        self.assertEqual(len(ts), 1)
        # TODO: Validate instrument
        self.assertEqual(ts[0].quantity, Decimal('-10000'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('9987.65')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('0.00')))
        self.assertEqual(ts[0].flags, TradeFlags.CLOSE)

    def test_reinvestShares(self) -> None:
        ts = self.tradesByDate[date(2017, 2, 4)]
        self.assertEqual(len(ts), 2)

        self.assertEqual(ts[0].instrument, Stock('VWO'))
        self.assertEqual(ts[0].quantity, Decimal('0.123'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('-20.15')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('0.00')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN | TradeFlags.DRIP)

        self.assertEqual(ts[1].instrument, Stock('VOO'))
        self.assertEqual(ts[1].quantity, Decimal('0.321'))
        self.assertEqual(
            ts[1].amount,
            Cash(currency=Currency.USD, quantity=Decimal('-17.48')))
        self.assertEqual(ts[1].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('0.00')))
        self.assertEqual(ts[1].flags, TradeFlags.OPEN | TradeFlags.DRIP)

    def test_shortSaleAndCover(self) -> None:
        # TODO: Test short sale and cover trades
        pass

    def test_buyToOpenOption(self) -> None:
        # TODO: Test buy to open trades
        pass

    def test_sellToCloseOption(self) -> None:
        # TODO: Test sell to close trades
        pass

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

    def test_securityOutgoingTransfer(self) -> None:
        ts = self.tradesByDate[date(2017, 9, 12)]
        self.assertEqual(len(ts), 1)
        # TODO: Validate instrument
        self.assertEqual(ts[0].quantity, Decimal('-10000'))
        self.assertEqual(ts[0].amount,
                         Cash(currency=Currency.USD, quantity=Decimal('0.00')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('0.00')))
        self.assertEqual(ts[0].flags, TradeFlags.CLOSE)


if __name__ == '__main__':
    unittest.main()
