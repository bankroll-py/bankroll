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
            Path('tests/vanguard_positions_and_transactions.csv'),
            Path('tests/vanguard_activity.pdf')).positions
        self.positions.sort(key=lambda p: p.instrument.symbol)

    def test_positionValidity(self) -> None:
        self.assertEqual(len(self.positions), 7)

    def test_vb(self) -> None:
        self.assertEqual(self.positions[0].instrument,
                         Stock("VB", Currency.USD))
        self.assertEqual(self.positions[0].quantity, Decimal('10'))
        # TODO: Validate cost basis

    def test_vgt(self) -> None:
        self.assertEqual(self.positions[1].instrument,
                         Stock("VGT", Currency.USD))
        self.assertEqual(self.positions[1].quantity, 20)
        # TODO: Validate cost basis

    def test_vmmxx(self) -> None:
        self.assertEqual(self.positions[2].instrument,
                         Stock("VMMXX", Currency.USD))
        self.assertEqual(self.positions[2].quantity, Decimal('543.21'))
        # TODO: Validate cost basis

    def test_vnq(self) -> None:
        self.assertEqual(self.positions[3].instrument,
                         Stock("VNQ", Currency.USD))
        self.assertEqual(self.positions[3].quantity, Decimal('100.1'))
        # TODO: Validate cost basis

    def test_voo(self) -> None:
        self.assertEqual(self.positions[4].instrument,
                         Stock("VOO", Currency.USD))
        self.assertEqual(self.positions[4].quantity, Decimal('45.5'))
        # TODO: Validate cost basis

    def test_vwo(self) -> None:
        self.assertEqual(self.positions[5].instrument,
                         Stock("VWO", Currency.USD))
        self.assertEqual(self.positions[5].quantity, Decimal('52.5'))
        # TODO: Validate cost basis

    def test_vymi(self) -> None:
        self.assertEqual(self.positions[6].instrument,
                         Stock("VYMI", Currency.USD))
        self.assertEqual(self.positions[6].quantity, Decimal('50.5'))
        # TODO: Validate cost basis


class TestVanguardParseActivityPDFRows(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = vanguard.parseActivityPDFRows(
            Path('tests/vanguard_activity.pdf'))

    def test_totalRows(self) -> None:
        self.assertEqual(len(self.rows), 20)

    def test_rowValues(self) -> None:
        self.assertEqual(
            self.rows[0],
            helpers.splitAndStripCSVString(
                "01/04/2015,01/04/2015,VMMXX,Prime Money Mkt Fund,Buy,,1000.0000,1.00,Free,-1000.00"
            ))

        self.assertEqual(
            self.rows[10],
            helpers.splitAndStripCSVString(
                "11/12/2015,11/12/2015,BND,VANGUARD TOTAL BOND MARKET ETF,Capital gain (LT),Cash,—,—,—,0.45"
            ))

        self.assertEqual(
            self.rows[11],
            helpers.splitAndStripCSVString(
                "01/01/2018,01/01/2018,—,FROM: HSBC NORTH AMERICA HOLDINGS INC,Funds Received,Cash,—,—,—,2000.00"
            ))

        self.assertEqual(
            self.rows[19],
            helpers.splitAndStripCSVString(
                "12/31/2018,12/31/2018,—,U S TREASURY BILL CPN 0.00000 % MTD 2018-06-30 DTD 2018-12-31,Corp Action (Redemption),Cash,10000.0000,—,—,9987.65"
            ))


class TestVanguardTransactions(unittest.TestCase):
    def setUp(self) -> None:
        self.trades = vanguard.parsePositionsAndTrades(
            Path('tests/vanguard_positions_and_transactions.csv'),
            Path('tests/vanguard_activity_converted.csv')).trades
        self.trades.sort(key=lambda t: (t.date, t.instrument.symbol))

        self.tradesByDate = {
            d: list(t)
            for d, t in groupby(self.trades, key=lambda t: t.date.date())
        }

    def test_tradeValidity(self) -> None:
        self.assertGreater(len(self.trades), 0)

    def test_buyMoneyMarketFund(self) -> None:
        ts = self.tradesByDate[date(2015, 1, 4)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].instrument, Stock('VMMXX', Currency.USD))
        self.assertEqual(ts[0].quantity, Decimal('1000.00'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('-1000.00')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('0.00')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)

    def test_reinvestment(self) -> None:
        ts = self.tradesByDate[date(2015, 1, 12)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].instrument, Stock('VB', Currency.USD))
        self.assertEqual(ts[0].quantity, Decimal('0.1234'))
        self.assertEqual(
            ts[0].amount, Cash(currency=Currency.USD,
                               quantity=Decimal('-2.10')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('0.00')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN | TradeFlags.DRIP)

    def test_redeemTBill(self) -> None:
        ts = self.tradesByDate[date(2018, 12, 31)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0].instrument,
            Bond(
                'U S TREASURY BILL CPN 0.00000 % MTD 2018-06-30 DTD 2018-12-31',
                Currency.USD,
                validateSymbol=False))
        self.assertEqual(ts[0].quantity, Decimal('10000'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('9987.65')))

    def test_buySecurity(self) -> None:
        ts = self.tradesByDate[date(2018, 1, 31)]
        self.assertEqual(len(ts), 2)

        self.assertEqual(ts[0].instrument, Stock('VWO', Currency.USD))
        self.assertEqual(ts[0].quantity, Decimal('20'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('-1975.20')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('0.00')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)

        self.assertEqual(ts[1].instrument, Stock('VYMI', Currency.USD))
        self.assertEqual(ts[1].quantity, Decimal('100'))
        self.assertEqual(
            ts[1].amount,
            Cash(currency=Currency.USD, quantity=Decimal('-12300')))
        self.assertEqual(ts[1].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('0.00')))
        self.assertEqual(ts[1].flags, TradeFlags.OPEN)

    def test_sellSecurity(self) -> None:
        ts = self.tradesByDate[date(2018, 10, 29)]
        self.assertEqual(len(ts), 1)

        self.assertEqual(ts[0].instrument, Stock(
            'TLT',
            Currency.USD,
        ))
        self.assertEqual(ts[0].quantity, Decimal('-9'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('211.45')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('7.05')))
        self.assertEqual(ts[0].flags, TradeFlags.CLOSE)

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
            # TODO: Test sell to open option trades
            pass


if __name__ == '__main__':
    unittest.main()
