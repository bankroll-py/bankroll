from bankroll import Cash, Currency, Position, Instrument, Stock, Bond, Option, OptionType, Forex, Future, FutureOption, Trade, TradeFlags, CashPayment
from bankroll.brokers import ibkr
from datetime import date
from decimal import Decimal
from hypothesis import given, reproduce_failure, settings, Verbosity
from hypothesis.strategies import builds, dates, decimals, from_regex, from_type, lists, one_of, sampled_from, text
from itertools import groupby
from pathlib import Path

from tests import helpers
import ib_insync as IB
import logging
import unittest


class TestIBKRTrades(unittest.TestCase):
    def setUp(self) -> None:
        self.trades = [
            t for t in ibkr.IBAccount(
                trades=Path('tests/ibkr_trades.xml')).activity()
            if isinstance(t, Trade)
        ]
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
            Cash(currency=Currency.USD, quantity=Decimal('-2035.13')))
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
                   multiplier=Decimal(50),
                   expiration=date(2019, 3, 15)))
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
                         underlying='BPM9',
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


class TestIBKRActivity(unittest.TestCase):
    def setUp(self) -> None:
        self.activity = list(
            ibkr.IBAccount(
                activity=Path('tests/ibkr_activity.xml')).activity())
        self.activity.sort(key=lambda t: t.date)

        self.activityByDate = {
            d: list(t)
            for d, t in groupby(self.activity, key=lambda t: t.date.date())
        }

    def test_activityValidity(self) -> None:
        self.assertGreater(len(self.activity), 0)

    def test_postedAndPaid(self) -> None:
        ts = self.activityByDate[date(2019, 2, 14)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            CashPayment(date=ts[0].date,
                        instrument=Stock('AAPL', Currency.USD),
                        proceeds=helpers.cashUSD(Decimal('23.36'))))

        self.assertNotIn(date(2019, 2, 7), self.activityByDate)
        self.assertNotIn(date(2019, 2, 8), self.activityByDate)

    def test_postedUnpaid(self) -> None:
        self.assertNotIn(date(2018, 12, 19), self.activityByDate)
        self.assertNotIn(date(2018, 12, 20), self.activityByDate)
        self.assertNotIn(date(2019, 1, 25), self.activityByDate)

    def test_bondInterest(self) -> None:
        ts = self.activityByDate[date(2019, 1, 17)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            CashPayment(date=ts[0].date,
                        instrument=Bond('BA 3 3/4 02/17/19',
                                        Currency.USD,
                                        validateSymbol=False),
                        proceeds=helpers.cashUSD(Decimal('18.75'))))

        self.assertNotIn(date(2019, 1, 15), self.activityByDate)
        self.assertNotIn(date(2019, 1, 14), self.activityByDate)

    def test_currencyInterest(self) -> None:
        # IBKR interest accruals don't have dates associated with them, so
        # they'll be tagged with the last day in the period being looked at.
        ts = self.activityByDate[date(2019, 3, 1)]

        # BASE_SUMMARY should be excluded
        self.assertEqual(len(ts), 2)

        self.assertEqual(
            ts[0],
            CashPayment(date=ts[0].date,
                        instrument=None,
                        proceeds=Cash(currency=Currency.AUD,
                                      quantity=Decimal('-4.29'))))

        self.assertEqual(
            ts[1],
            CashPayment(date=ts[1].date,
                        instrument=None,
                        proceeds=Cash(currency=Currency.USD,
                                      quantity=Decimal('2.26'))))

    def test_stockLoanInterest(self) -> None:
        ts = self.activityByDate[date(2019, 1, 1)]
        self.assertEqual(len(ts), 1)
        self.assertEqual(
            ts[0],
            CashPayment(date=ts[0].date,
                        instrument=Stock('TSLA', Currency.USD),
                        proceeds=helpers.cashUSD(Decimal('0.01'))))


class TestIBKRParsing(unittest.TestCase):
    validSymbols = text(min_size=1)
    validCurrencies = from_type(Currency).map(lambda c: c.name)
    validAssetCategories = sampled_from(
        ['STK', 'BILL', 'BOND', 'OPT', 'FUT', 'CASH', 'FOP'])
    allAssetCategories = one_of(
        validAssetCategories,
        sampled_from(
            ['IND', 'CFD', 'FUND', 'CMDTY', 'IOPT', 'BAG', 'NEWS', 'WAR']))

    # For some reason, %Y wasn't zero-padding the year to 4 digits on CI, so provide our own century
    validDates = dates().map(lambda d: d.strftime('20%y%m%d'))
    validQuantities = helpers.positionQuantities().map(str)
    validCodes = lists(sampled_from(['O', 'C', 'A', 'Ep', 'Ex', 'R', 'P',
                                     'D']),
                       max_size=3,
                       unique=True).map(lambda l: ';'.join(l))
    allCodes = one_of(validCodes,
                      from_regex(r'([A-Z][A-Za-z]*(;[A-Z][A-Za-z]*)*)?'))
    validMultipliers = helpers.multipliers().map(str)
    validCashAmounts = helpers.cashAmounts().map(str)
    validStrikes = helpers.strikes().map(str)
    validPutCalls = sampled_from(['P', 'C'])

    validTradeConfirms = builds(ibkr._IBTradeConfirm,
                                symbol=validSymbols,
                                underlyingSymbol=validSymbols,
                                currency=validCurrencies,
                                commissionCurrency=validCurrencies,
                                assetCategory=validAssetCategories,
                                tradeDate=validDates,
                                expiry=validDates,
                                quantity=validQuantities,
                                multiplier=validMultipliers,
                                proceeds=validCashAmounts,
                                tax=validCashAmounts,
                                commission=validCashAmounts,
                                strike=validStrikes,
                                putCall=validPutCalls,
                                code=validCodes)

    allTradeConfirms = builds(ibkr._IBTradeConfirm,
                              symbol=one_of(validSymbols, text()),
                              underlyingSymbol=one_of(validSymbols, text()),
                              currency=one_of(validCurrencies, text()),
                              commissionCurrency=one_of(
                                  validCurrencies, text()),
                              assetCategory=one_of(allAssetCategories, text()),
                              tradeDate=one_of(validDates, text()),
                              expiry=one_of(validDates, text()),
                              quantity=one_of(validQuantities,
                                              decimals().map(str), text()),
                              multiplier=one_of(validMultipliers,
                                                decimals().map(str), text()),
                              proceeds=one_of(validCashAmounts,
                                              decimals().map(str), text()),
                              tax=one_of(validCashAmounts,
                                         decimals().map(str), text()),
                              commission=one_of(validCashAmounts,
                                                decimals().map(str), text()),
                              strike=one_of(validStrikes,
                                            decimals().map(str), text()),
                              putCall=one_of(validPutCalls, text()),
                              code=one_of(allCodes, text()))

    validContracts = builds(
        IB.Contract,
        symbol=validSymbols,
        secType=validAssetCategories,
        lastTradeDateOrContractMonth=validDates,
        strike=validStrikes,
        right=validPutCalls,
        multiplier=validMultipliers,
        currency=validCurrencies,
        localSymbol=validSymbols,
    )

    validPositions = builds(IB.Position,
                            account=text(),
                            avgCost=validCashAmounts,
                            contract=validContracts,
                            position=validQuantities)

    allContracts = builds(
        IB.Contract,
        symbol=one_of(validSymbols, text()),
        secType=one_of(validAssetCategories, text()),
        lastTradeDateOrContractMonth=one_of(validDates, text()),
        strike=one_of(validStrikes,
                      decimals().map(str), text()),
        right=one_of(validPutCalls, text()),
        multiplier=one_of(validMultipliers,
                          decimals().map(str), text()),
        currency=one_of(validCurrencies, text()),
        localSymbol=one_of(validSymbols, text()),
    )

    allPositions = builds(IB.Position,
                          account=text(),
                          avgCost=one_of(validCashAmounts,
                                         decimals().map(str), text()),
                          contract=allContracts,
                          position=one_of(validQuantities,
                                          decimals().map(str), text()))

    def validateTradeContract(self, tradeConfirm: ibkr._IBTradeConfirm,
                              instrument: Instrument) -> None:
        contract = ibkr._contract(instrument)
        if tradeConfirm.assetCategory == 'BILL':
            self.assertEqual(contract.secType, 'BOND')
        else:
            self.assertEqual(contract.secType, tradeConfirm.assetCategory)
        self.assertEqual(contract.currency, tradeConfirm.currency)

        if isinstance(instrument, Option):
            self.assertEqual(
                Option.quantizeStrike(Decimal(contract.strike)),
                Option.quantizeStrike(Decimal(tradeConfirm.strike)))
            self.assertEqual(contract.right, tradeConfirm.putCall)

        if isinstance(instrument, Option) or isinstance(instrument, Future):
            self.assertEqual(
                Instrument.quantizeMultiplier(Decimal(contract.multiplier)),
                Instrument.quantizeMultiplier(Decimal(
                    tradeConfirm.multiplier)))
            self.assertEqual(contract.lastTradeDateOrContractMonth,
                             tradeConfirm.expiry)

    @given(allTradeConfirms)
    def test_fuzzTradeConfirm(self,
                              tradeConfirm: ibkr._IBTradeConfirm) -> None:
        try:
            trade = ibkr._parseTradeConfirm(tradeConfirm)
        except ValueError:
            return

        self.validateTradeContract(tradeConfirm, trade.instrument)

    @unittest.skip('Exists to validate test data only')
    @given(validTradeConfirms)
    def test_parsedTradeConfirmConvertsToContract(
            self, tradeConfirm: ibkr._IBTradeConfirm) -> None:
        trade = ibkr._parseTradeConfirm(tradeConfirm)
        self.validateTradeContract(tradeConfirm, trade.instrument)

    def validatePositionContract(self, position: IB.Position,
                                 instrument: Instrument) -> None:
        contract = ibkr._contract(instrument)
        if position.contract.secType == 'BILL':
            self.assertEqual(contract.secType, 'BOND')
        else:
            self.assertEqual(contract.secType, position.contract.secType)
        self.assertEqual(contract.currency, position.contract.currency)

        if isinstance(instrument, Option):
            self.assertEqual(
                Option.quantizeStrike(Decimal(contract.strike)),
                Option.quantizeStrike(Decimal(position.contract.strike)))
            self.assertEqual(contract.right, position.contract.right)

        if isinstance(instrument, Option) or isinstance(instrument, Future):
            self.assertEqual(
                Instrument.quantizeMultiplier(Decimal(contract.multiplier)),
                Instrument.quantizeMultiplier(
                    Decimal(position.contract.multiplier)))
            self.assertEqual(contract.lastTradeDateOrContractMonth,
                             position.contract.lastTradeDateOrContractMonth)

    @given(allPositions)
    def test_fuzzPosition(self, position: IB.Position) -> None:
        try:
            parsedPosition = ibkr._extractPosition(position)
        except ValueError:
            return

        self.assertEqual(parsedPosition.quantity,
                         Position.quantizeQuantity(Decimal(position.position)))
        self.validatePositionContract(position, parsedPosition.instrument)

    @unittest.skip('Exists to validate test data only')
    @given(validPositions)
    def test_parsedPositionConvertsToContract(self,
                                              position: IB.Position) -> None:
        parsedPosition = ibkr._extractPosition(position)
        self.assertEqual(parsedPosition.quantity,
                         Position.quantizeQuantity(Decimal(position.position)))
        self.validatePositionContract(position, parsedPosition.instrument)


if __name__ == '__main__':
    unittest.main()
