from datetime import date
from decimal import Decimal
from hypothesis import given
from hypothesis.strategies import from_type
from itertools import groupby
from model import Cash, Currency, Stock, Bond, Option, OptionType, Forex, Future, FutureOption, Trade, TradeFlags
from pathlib import Path

import helpers
import ib_insync as IB
import ibkr
import logging
import unittest


class TestIBKRTrades(unittest.TestCase):
    def setUp(self) -> None:
        self.trades = ibkr.parseTrades(Path('tests/ibkr_trades.xml'))
        self.trades.sort(key=lambda t: t.instrument.symbol)

        self.tradesBySymbol = {
            s: list(t)
            for s, t in groupby(self.trades, key=lambda t: t.instrument.symbol)
        }

    def test_tradeValidity(self) -> None:
        self.assertGreater(len(self.trades), 0)

    def test_buyGBPStock(self) -> None:
        symbol = 'GAW'
        ts = self.tradesBySymbol[symbol]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].date.date(), date(2019, 2, 12))
        self.assertEqual(ts[0].instrument, Stock(symbol, Currency.GBP))
        self.assertEqual(ts[0].quantity, Decimal('100'))
        self.assertEqual(
            ts[0].amount, Cash(currency=Currency.GBP,
                               quantity=Decimal('-3050')))
        self.assertEqual(
            ts[0].fees, Cash(currency=Currency.GBP, quantity=Decimal('21.25')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)

    def test_buyUSDStock(self) -> None:
        symbol = 'AAPL'
        ts = self.tradesBySymbol[symbol]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].date.date(), date(2019, 2, 12))
        self.assertEqual(ts[0].instrument, Stock(symbol, Currency.USD))
        self.assertEqual(ts[0].quantity, Decimal('17'))
        self.assertEqual(
            ts[0].amount, Cash(currency=Currency.USD,
                               quantity=Decimal('-2890')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('1')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)

    def test_buyBond(self) -> None:
        # IB doesn't export the CUSIP unless the data is paid for.
        symbol = 'ALLY 3 3/4 11/18/19'
        ts = self.tradesBySymbol[symbol]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].date.date(), date(2019, 3, 19))
        self.assertEqual(ts[0].instrument,
                         Bond(symbol, Currency.USD, validateSymbol=False))
        self.assertEqual(ts[0].quantity, Decimal('2000'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('-2009.50')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('2')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)

    def test_buyOption(self) -> None:
        symbol = 'HYG   191115P00087000'
        ts = self.tradesBySymbol[symbol]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].date.date(), date(2019, 2, 12))
        self.assertEqual(
            ts[0].instrument,
            Option(underlying='HYG',
                   currency=Currency.USD,
                   optionType=OptionType.PUT,
                   expiration=date(2019, 11, 15),
                   strike=Decimal('87')))
        self.assertEqual(ts[0].quantity, Decimal('1'))
        self.assertEqual(ts[0].amount,
                         Cash(currency=Currency.USD, quantity=Decimal('-565')))
        self.assertEqual(
            ts[0].fees, Cash(currency=Currency.USD,
                             quantity=Decimal('0.7182')))
        self.assertEqual(ts[0].price,
                         Cash(currency=Currency.USD, quantity=Decimal('5.65')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)

    def test_sellOption(self) -> None:
        symbol = 'MTCH  190215P00045000'
        ts = self.tradesBySymbol[symbol]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].date.date(), date(2019, 2, 4))
        self.assertEqual(
            ts[0].instrument,
            Option(underlying='MTCH',
                   currency=Currency.USD,
                   optionType=OptionType.PUT,
                   expiration=date(2019, 2, 15),
                   strike=Decimal('45')))
        self.assertEqual(ts[0].quantity, Decimal('-1'))
        self.assertEqual(ts[0].amount,
                         Cash(currency=Currency.USD, quantity=Decimal('55')))
        self.assertEqual(
            ts[0].fees,
            Cash(currency=Currency.USD, quantity=Decimal('1.320915')))
        self.assertEqual(ts[0].price,
                         Cash(currency=Currency.USD, quantity=Decimal('0.55')))
        self.assertEqual(ts[0].flags, TradeFlags.CLOSE)

    def test_buyForex(self) -> None:
        symbol = 'GBPUSD'
        ts = self.tradesBySymbol[symbol]
        self.assertEqual(len(ts), 2)
        self.assertEqual(ts[0].date.date(), date(2019, 2, 12))
        self.assertEqual(
            ts[0].instrument,
            Forex(baseCurrency=Currency.GBP, quoteCurrency=Currency.USD))
        self.assertEqual(ts[0].quantity, Decimal('3060'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.USD, quantity=Decimal('-3936.231')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('2')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)
        self.assertEqual(
            ts[1].instrument,
            Forex(baseCurrency=Currency.GBP, quoteCurrency=Currency.USD))
        self.assertEqual(ts[1].quantity, Decimal('50'))
        self.assertEqual(
            ts[1].amount,
            Cash(currency=Currency.USD, quantity=Decimal('-64.36')))
        self.assertEqual(ts[1].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('2')))
        self.assertEqual(ts[1].flags, TradeFlags.OPEN)

    def test_buyForexCross(self) -> None:
        symbol = 'GBPAUD'
        ts = self.tradesBySymbol[symbol]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].date.date(), date(2019, 3, 25))
        self.assertEqual(
            ts[0].instrument,
            Forex(baseCurrency=Currency.GBP, quoteCurrency=Currency.AUD))
        self.assertEqual(ts[0].quantity, Decimal('5000'))
        self.assertEqual(
            ts[0].amount,
            Cash(currency=Currency.AUD, quantity=Decimal('-9329.25')))
        self.assertEqual(ts[0].fees,
                         Cash(currency=Currency.USD, quantity=Decimal('2')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)

    def test_buyFuture(self) -> None:
        symbol = 'ESH9'
        ts = self.tradesBySymbol[symbol]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].date.date(), date(2019, 2, 26))
        self.assertEqual(
            ts[0].instrument,
            Future(symbol=symbol,
                   currency=Currency.USD,
                   multiplier=Decimal(50)))
        self.assertEqual(ts[0].quantity, Decimal('1'))
        self.assertEqual(ts[0].amount, helpers.cashUSD(Decimal('-139687.5')))
        self.assertEqual(ts[0].fees, helpers.cashUSD(Decimal('2.05')))
        self.assertEqual(
            ts[0].price,
            Cash(currency=Currency.USD, quantity=Decimal('2793.75')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)

    def test_buyFutureOption(self) -> None:
        symbol = 'GBUJ9 C1335'
        ts = self.tradesBySymbol[symbol]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].date.date(), date(2019, 3, 4))
        self.assertEqual(
            ts[0].instrument,
            FutureOption(symbol=symbol,
                         currency=Currency.USD,
                         underlying='GBUJ9',
                         optionType=OptionType.CALL,
                         expiration=date(2019, 4, 5),
                         strike=Decimal('1.335'),
                         multiplier=Decimal(62500)))
        self.assertEqual(ts[0].quantity, Decimal('1'))
        self.assertEqual(ts[0].amount, helpers.cashUSD(Decimal('-918.75')))
        self.assertEqual(ts[0].fees, helpers.cashUSD(Decimal('2.47')))
        self.assertEqual(
            ts[0].price, Cash(currency=Currency.USD,
                              quantity=Decimal('0.0147')))
        self.assertEqual(ts[0].flags, TradeFlags.OPEN)


class TestIBKRFuzzParsing(unittest.TestCase):
    @given(from_type(ibkr.IBTradeConfirm))
    def test_parseTradeConfirm(self,
                               tradeConfirm: ibkr.IBTradeConfirm) -> None:
        try:
            trade = ibkr.parseTradeConfirm(tradeConfirm)
        except ValueError as err:
            logging.info(
                'TradeConfirm {} failed to parse with error: {}'.format(
                    tradeConfirm, err))
            return

        contract = ibkr.contract(trade.instrument)
        self.assertEqual(contract.secType, tradeConfirm.assetCategory)
        self.assertEqual(contract.strike, tradeConfirm.strike)
        self.assertEqual(contract.multiplier, tradeConfirm.multiplier)
        self.assertEqual(contract.currency, tradeConfirm.currency)
        self.assertEqual(contract.right, tradeConfirm.putCall)
        self.assertEqual(contract.lastTradeDateOrContractMonth,
                         tradeConfirm.expiry)


if __name__ == '__main__':
    unittest.main()
