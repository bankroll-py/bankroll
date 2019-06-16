from datetime import datetime
from decimal import Context, Decimal, DivisionByZero, Overflow, InvalidOperation, localcontext
from enum import Enum, IntEnum, unique
from itertools import chain, count
from bankroll.model import AccountBalance, AccountData, Currency, Cash, Instrument, Stock, Bond, Option, OptionType, FutureOption, Future, Forex, Position, TradeFlags, Trade, MarketDataProvider, Quote, Activity, CashPayment
from bankroll.parsetools import lenientParse
from pathlib import Path
from progress.spinner import Spinner
from random import randint
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, NamedTuple, Optional, Sequence, Tuple, Type, TypeVar, Union, no_type_check
import pandas as pd

import backoff
import bankroll.configuration as configuration
import ib_insync as IB
import logging
import math
import re


@unique
class Settings(configuration.Settings):
    TWS_PORT = 'TWS port'
    FLEX_TOKEN = 'Flex token'
    TRADES = 'Trades'
    ACTIVITY = 'Activity'

    @property
    def help(self) -> str:
        if self == self.TWS_PORT:
            return "The port upon which Interactive Brokers' Trader Workstation (or IB Gateway) is accepting connections. If present, bankroll will attempt to connect to the application in order to retrieve positions and live data."
        elif self == self.FLEX_TOKEN:
            return "A token ID from IB's Flex Web Service, to fetch historical account activity. See README.md for more information."
        elif self == self.TRADES:
            return "A query ID for a Trade Confirmations report from IB's Flex Web Service, or a local path to exported XML from one such Trade Confirmations report."
        elif self == self.ACTIVITY:
            return "A query ID for a Activity report from IB's Flex Web Service, or a local path to exported XML from one such Activity report."
        else:
            return ""

    @classmethod
    def sectionName(cls) -> str:
        return 'IBKR'


def _parseFiniteDecimal(input: str) -> Decimal:
    with localcontext(ctx=Context(traps=[DivisionByZero, Overflow])):
        value = Decimal(input)
        if not value.is_finite():
            raise ValueError(f'Input is not numeric: {input}')

        return value


def _parseOption(symbol: str,
                 currency: Currency,
                 multiplier: Decimal,
                 cls: Type[Option] = Option) -> Option:
    # https://en.wikipedia.org/wiki/Option_symbol#The_OCC_Option_Symbol
    match = re.match(
        r'^(?P<underlying>.{6})(?P<date>\d{6})(?P<putCall>P|C)(?P<strike>\d{8})$',
        symbol)
    if not match:
        raise ValueError(f'Could not parse IB option symbol: {symbol}')

    if match['putCall'] == 'P':
        optionType = OptionType.PUT
    else:
        optionType = OptionType.CALL

    return cls(underlying=match['underlying'].rstrip(),
               currency=currency,
               optionType=optionType,
               expiration=datetime.strptime(match['date'], '%y%m%d').date(),
               strike=_parseFiniteDecimal(match['strike']) / 1000)


def _parseForex(symbol: str, currency: Currency) -> Forex:
    match = re.match(r'^(?P<base>[A-Z]{3})\.(?P<quote>[A-Z]{3})', symbol)
    if not match:
        raise ValueError(f'Could not parse IB cash symbol: {symbol}')

    baseCurrency = Currency[match['base']]
    quoteCurrency = Currency[match['quote']]
    if currency != quoteCurrency:
        raise ValueError(
            f'Expected quote currency {quoteCurrency} to match position currency {currency}'
        )

    return Forex(baseCurrency=baseCurrency, quoteCurrency=quoteCurrency)


def _parseFutureOptionContract(contract: IB.Contract,
                               currency: Currency) -> Instrument:
    if contract.right.startswith('C'):
        optionType = OptionType.CALL
    elif contract.right.startswith('P'):
        optionType = OptionType.PUT
    else:
        raise ValueError(f'Unexpected right in IB contract: {contract}')

    return FutureOption(symbol=contract.localSymbol,
                        currency=currency,
                        underlying=contract.symbol,
                        optionType=optionType,
                        expiration=_parseIBDate(
                            contract.lastTradeDateOrContractMonth).date(),
                        strike=_parseFiniteDecimal(contract.strike),
                        multiplier=_parseFiniteDecimal(contract.multiplier))


def _extractPosition(p: IB.Position) -> Position:
    tag = p.contract.secType
    symbol = p.contract.localSymbol

    if p.contract.currency not in Currency.__members__:
        raise ValueError(f'Unrecognized currency in position: {p}')

    currency = Currency[p.contract.currency]

    try:
        instrument: Instrument
        if tag == 'STK':
            instrument = Stock(symbol=symbol, currency=currency)
        elif tag == 'BILL' or tag == 'BOND':
            instrument = Bond(symbol=symbol,
                              currency=currency,
                              validateSymbol=False)
        elif tag == 'OPT':
            instrument = _parseOption(symbol=symbol,
                                      currency=currency,
                                      multiplier=_parseFiniteDecimal(
                                          p.contract.multiplier))
        elif tag == 'FUT':
            instrument = Future(
                symbol=symbol,
                currency=currency,
                multiplier=_parseFiniteDecimal(p.contract.multiplier),
                expiration=_parseIBDate(
                    p.contract.lastTradeDateOrContractMonth).date())
        elif tag == 'FOP':
            instrument = _parseFutureOptionContract(p.contract,
                                                    currency=currency)
        elif tag == 'CASH':
            instrument = _parseForex(symbol=symbol, currency=currency)
        else:
            raise ValueError(
                f'Unrecognized/unsupported security type in position: {p}')

        qty = _parseFiniteDecimal(p.position)
        costBasis = _parseFiniteDecimal(p.avgCost) * qty

        return Position(instrument=instrument,
                        quantity=qty,
                        costBasis=Cash(currency=Currency[p.contract.currency],
                                       quantity=costBasis))
    except InvalidOperation:
        raise ValueError(
            f'One of the numeric position or contract values is out of range: {p}'
        )


def _downloadPositions(ib: IB.IB, lenient: bool) -> List[Position]:
    return list(
        lenientParse(ib.positions(),
                     transform=_extractPosition,
                     lenient=lenient))


class _IBTradeConfirm(NamedTuple):
    accountId: str
    acctAlias: str
    model: str
    currency: str
    assetCategory: str
    symbol: str
    description: str
    conid: str
    securityID: str
    securityIDType: str
    cusip: str
    isin: str
    listingExchange: str
    underlyingConid: str
    underlyingSymbol: str
    underlyingSecurityID: str
    underlyingListingExchange: str
    issuer: str
    multiplier: str
    strike: str
    expiry: str
    putCall: str
    principalAdjustFactor: str
    transactionType: str
    tradeID: str
    orderID: str
    execID: str
    brokerageOrderID: str
    orderReference: str
    volatilityOrderLink: str
    clearingFirmID: str
    origTradePrice: str
    origTradeDate: str
    origTradeID: str
    orderTime: str
    dateTime: str
    reportDate: str
    settleDate: str
    tradeDate: str
    exchange: str
    buySell: str
    quantity: str
    price: str
    amount: str
    proceeds: str
    commission: str
    brokerExecutionCommission: str
    brokerClearingCommission: str
    thirdPartyExecutionCommission: str
    thirdPartyClearingCommission: str
    thirdPartyRegulatoryCommission: str
    otherCommission: str
    commissionCurrency: str
    tax: str
    code: str
    orderType: str
    levelOfDetail: str
    traderID: str
    isAPIOrder: str
    allocatedTo: str
    accruedInt: str


class _IBChangeInDividendAccrual(NamedTuple):
    accountId: str
    acctAlias: str
    model: str
    currency: str
    fxRateToBase: str
    assetCategory: str
    symbol: str
    description: str
    conid: str
    securityID: str
    securityIDType: str
    cusip: str
    isin: str
    listingExchange: str
    underlyingConid: str
    underlyingSymbol: str
    underlyingSecurityID: str
    underlyingListingExchange: str
    issuer: str
    multiplier: str
    strike: str
    expiry: str
    putCall: str
    principalAdjustFactor: str
    reportDate: str
    date: str
    exDate: str
    payDate: str
    quantity: str
    tax: str
    fee: str
    grossRate: str
    grossAmount: str
    netAmount: str
    code: str
    fromAcct: str
    toAcct: str


class _IBInterestAccrualsCurrency(NamedTuple):
    accountId: str
    acctAlias: str
    model: str
    currency: str
    fromDate: str
    toDate: str
    startingAccrualBalance: str
    interestAccrued: str
    accrualReversal: str
    fxTranslation: str
    endingAccrualBalance: str


class _IBSLBFee(NamedTuple):
    accountId: str
    acctAlias: str
    model: str
    currency: str
    fxRateToBase: str
    assetCategory: str
    symbol: str
    description: str
    conid: str
    securityID: str
    securityIDType: str
    cusip: str
    isin: str
    listingExchange: str
    underlyingConid: str
    underlyingSymbol: str
    underlyingSecurityID: str
    underlyingListingExchange: str
    issuer: str
    multiplier: str
    strike: str
    expiry: str
    putCall: str
    principalAdjustFactor: str
    valueDate: str
    startDate: str
    type: str
    exchange: str
    quantity: str
    collateralAmount: str
    feeRate: str
    fee: str
    carryCharge: str
    ticketCharge: str
    totalCharges: str
    marketFeeRate: str
    grossLendFee: str
    netLendFeeRate: str
    netLendFee: str
    code: str
    fromAcct: str
    toAcct: str


def _parseIBDate(datestr: str) -> datetime:
    return datetime.strptime(datestr, '%Y%m%d')


_instrumentEntryTypes = Union[_IBTradeConfirm, _IBChangeInDividendAccrual,
                              _IBSLBFee]


def _parseFutureOption(entry: _instrumentEntryTypes) -> Instrument:
    if entry.putCall == 'C':
        optionType = OptionType.CALL
    elif entry.putCall == 'P':
        optionType = OptionType.PUT
    else:
        raise ValueError(f'Unexpected value for putCall in IB entry: {entry}')

    return FutureOption(symbol=entry.symbol,
                        currency=Currency[entry.currency],
                        underlying=entry.underlyingSymbol,
                        optionType=optionType,
                        expiration=_parseIBDate(entry.expiry).date(),
                        strike=_parseFiniteDecimal(entry.strike),
                        multiplier=_parseFiniteDecimal(entry.multiplier))


def _parseInstrument(entry: _instrumentEntryTypes) -> Instrument:
    symbol = entry.symbol
    if not symbol:
        raise ValueError(f'Missing symbol in entry: {entry}')

    if entry.currency not in Currency.__members__:
        raise ValueError(f'Unrecognized currency in entry: {entry}')

    currency = Currency[entry.currency]

    tag = entry.assetCategory
    if tag == 'STK':
        return Stock(symbol=symbol, currency=currency)
    elif tag == 'BILL' or tag == 'BOND':
        return Bond(symbol=symbol, currency=currency, validateSymbol=False)
    elif tag == 'OPT':
        return _parseOption(symbol=symbol,
                            currency=currency,
                            multiplier=_parseFiniteDecimal(entry.multiplier))
    elif tag == 'FUT':
        return Future(symbol=symbol,
                      currency=currency,
                      multiplier=_parseFiniteDecimal(entry.multiplier),
                      expiration=_parseIBDate(entry.expiry).date())
    elif tag == 'CASH':
        return _parseForex(symbol=symbol, currency=currency)
    elif tag == 'FOP':
        return _parseFutureOption(entry)
    else:
        raise ValueError(
            f'Unrecognized/unsupported security type in entry: {entry}')


def _parseTradeConfirm(trade: _IBTradeConfirm) -> Trade:
    try:
        instrument = _parseInstrument(trade)

        flagsByCode = {
            'O': TradeFlags.OPEN,
            'C': TradeFlags.CLOSE,
            'A': TradeFlags.ASSIGNED_OR_EXERCISED,
            'Ex': TradeFlags.ASSIGNED_OR_EXERCISED,
            'Ep': TradeFlags.EXPIRED,
            'R': TradeFlags.DRIP,

            # Partial execution
            'P': TradeFlags.NONE,

            # Unknown code, spotted on a complex futures trade
            'D': TradeFlags.NONE,
        }

        codes = trade.code.split(';')
        flags = TradeFlags.NONE
        for c in codes:
            if c == '':
                continue

            if c not in flagsByCode:
                raise ValueError(f'Unrecognized code {c} in trade: {trade}')

            flags |= flagsByCode[c]

        # Codes are not always populated with open/close, not sure why
        if flags & (TradeFlags.OPEN | TradeFlags.CLOSE) == TradeFlags.NONE:
            if trade.buySell == 'BUY':
                flags |= TradeFlags.OPEN
            else:
                flags |= TradeFlags.CLOSE

        if trade.commissionCurrency not in Currency.__members__:
            raise ValueError(f'Unrecognized currency in trade: {trade}')

        # We could choose to account for accrued interest payments as part of
        # the trade price or as a separate cash payment; the former seems
        # marginally cleaner and more sensible for a trade log.
        proceeds = Cash(currency=Currency[trade.currency],
                        quantity=_parseFiniteDecimal(trade.proceeds) +
                        _parseFiniteDecimal(trade.accruedInt))

        return Trade(date=_parseIBDate(trade.tradeDate),
                     instrument=instrument,
                     quantity=_parseFiniteDecimal(trade.quantity),
                     amount=proceeds,
                     fees=Cash(
                         currency=Currency[trade.commissionCurrency],
                         quantity=-(_parseFiniteDecimal(trade.commission) +
                                    _parseFiniteDecimal(trade.tax))),
                     flags=flags)
    except InvalidOperation:
        raise ValueError(
            f'One of the numeric trade values is out of range: {trade}')


def _tradesFromReport(report: IB.FlexReport, lenient: bool) -> List[Trade]:
    return list(
        lenientParse(
            (_IBTradeConfirm(**t.__dict__)
             for t in report.extract('TradeConfirm', parseNumbers=False)),
            transform=_parseTradeConfirm,
            lenient=lenient))


def _parseTrades(path: Path, lenient: bool = False) -> List[Trade]:
    return _tradesFromReport(IB.FlexReport(path=path), lenient=lenient)


def _parseChangeInDividendAccrual(entry: _IBChangeInDividendAccrual
                                  ) -> Optional[Activity]:
    codes = entry.code.split(';')
    if 'Re' not in codes:
        return None

    # IB "reverses" dividend postings when they're paid out, so they all appear as debits.
    proceeds = Cash(currency=Currency[entry.currency],
                    quantity=-Decimal(entry.netAmount))

    return CashPayment(date=_parseIBDate(entry.payDate),
                       instrument=_parseInstrument(entry),
                       proceeds=proceeds)


def _parseCurrencyInterestAccrual(entry: _IBInterestAccrualsCurrency
                                  ) -> Optional[Activity]:
    # This entry includes forex translation, which we don't want.
    if entry.currency == 'BASE_SUMMARY':
        return None

    # An accrual gets "reversed" when it is credited/debited. Because the
    # reversal refers to the balance of interest, accrual reversal > 0 means
    # that the cash account was debited, while accrual reversal < 0 means the
    # cash account was credited with the interest.
    proceeds = Cash(currency=Currency[entry.currency],
                    quantity=-Decimal(entry.accrualReversal))

    # Using `toDate` here since there are no dates attached to the actual
    # accruals.
    return CashPayment(date=_parseIBDate(entry.toDate),
                       instrument=None,
                       proceeds=proceeds)


def _parseStockLoanFee(entry: _IBSLBFee) -> Optional[Activity]:
    # We don't see accrual reversals here, because it rolls up into total interest accounting, so use the accrual postings instead.
    codes = entry.code.split(';')
    if 'Po' not in codes:
        return None

    proceeds = Cash(currency=Currency[entry.currency],
                    quantity=Decimal(entry.netLendFee))

    return CashPayment(date=_parseIBDate(entry.valueDate),
                       instrument=_parseInstrument(entry),
                       proceeds=proceeds)


_NT = TypeVar('_NT', _IBChangeInDividendAccrual, _IBSLBFee,
              _IBInterestAccrualsCurrency)


def _parseActivityType(report: IB.FlexReport, name: str, t: Type[_NT],
                       transform: Callable[[_NT], Optional[Activity]],
                       lenient: bool) -> Iterable[Activity]:
    return filter(
        None,
        lenientParse((t(**x.__dict__)
                      for x in report.extract(name, parseNumbers=False)),
                     transform=transform,
                     lenient=lenient))


def _activityFromReport(report: IB.FlexReport,
                        lenient: bool) -> List[Activity]:
    return list(
        chain(
            _parseActivityType(report,
                               'ChangeInDividendAccrual',
                               _IBChangeInDividendAccrual,
                               transform=_parseChangeInDividendAccrual,
                               lenient=lenient),
            _parseActivityType(report,
                               'SLBFee',
                               _IBSLBFee,
                               transform=_parseStockLoanFee,
                               lenient=lenient),
            _parseActivityType(report,
                               'InterestAccrualsCurrency',
                               _IBInterestAccrualsCurrency,
                               transform=_parseCurrencyInterestAccrual,
                               lenient=lenient)))


# TODO: This should eventually be unified with trade parsing.
# See https://github.com/jspahrsummers/bankroll/issues/36.
def _parseNonTradeActivity(path: Path,
                           lenient: bool = False) -> List[Activity]:
    return _activityFromReport(IB.FlexReport(path=path), lenient=lenient)


class _SpinnerOnLogHandler(logging.Handler):
    def __init__(self, spinner: Spinner):
        self._spinner = spinner
        super().__init__()

    def handle(self, record: logging.LogRecord) -> None:
        self._spinner.next()


def _backoffFlexReport(details: Dict[str, Any]) -> None:
    wait: float = details['wait']
    logging.warn(f'Backing off {wait:.0f} seconds before retrying…')


def _flexErrorIsFatal(exception: IB.FlexError) -> bool:
    # https://www.interactivebrokers.co.uk/en/software/am/am/reports/version_3_error_codes.htm
    return 'Please try again shortly.' not in str(exception)


@no_type_check
@backoff.on_exception(backoff.constant,
                      IB.FlexError,
                      interval=count(start=3, step=3),
                      max_tries=5,
                      giveup=_flexErrorIsFatal,
                      on_backoff=_backoffFlexReport)
def _downloadFlexReport(name: str, token: str, queryID: int) -> IB.FlexReport:
    with Spinner(f'Downloading {name} report ') as spinner:
        handler = _SpinnerOnLogHandler(spinner)
        logger = logging.getLogger('ib_insync.flexreport')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        try:
            spinner.next()
            return IB.FlexReport(token=token, queryId=queryID)
        finally:
            logger.removeHandler(handler)


def _downloadTrades(token: str, queryID: int,
                    lenient: bool = False) -> List[Trade]:
    return _tradesFromReport(_downloadFlexReport(name='Trades',
                                                 token=token,
                                                 queryID=queryID),
                             lenient=lenient)


# TODO: This should eventually be unified with trade parsing.
# See https://github.com/jspahrsummers/bankroll/issues/36.
def _downloadNonTradeActivity(token: str, queryID: int,
                              lenient: bool = False) -> List[Activity]:
    return _activityFromReport(_downloadFlexReport(name='Activity',
                                                   token=token,
                                                   queryID=queryID),
                               lenient=lenient)


def _extractCash(val: IB.AccountValue) -> Cash:
    if val.currency not in Currency.__members__:
        raise ValueError(f'Unrecognized currency in account value: {val}')

    return Cash(currency=Currency[val.currency],
                quantity=_parseFiniteDecimal(val.value))


def _downloadBalance(ib: IB.IB, lenient: bool) -> AccountBalance:
    accountValues = (val for val in ib.accountSummary()
                     if val.account == 'All' and val.tag == 'TotalCashBalance'
                     and val.currency != 'BASE')

    cashByCurrency: Dict[Currency, Cash] = {}

    for cash in lenientParse(accountValues,
                             transform=_extractCash,
                             lenient=lenient):
        cashByCurrency[cash.currency] = cashByCurrency.get(
            cash.currency, Cash(currency=cash.currency,
                                quantity=Decimal(0))) + cash

    return AccountBalance(cash=cashByCurrency)


def _stockContract(stock: Stock) -> IB.Contract:
    return IB.Stock(symbol=stock.symbol,
                    exchange='SMART',
                    currency=stock.currency.name)


def _bondContract(bond: Bond) -> IB.Contract:
    return IB.Bond(symbol=bond.symbol,
                   exchange='SMART',
                   currency=bond.currency.name)


def _optionContract(option: Option,
                    cls: Type[IB.Contract] = IB.Option) -> IB.Contract:
    lastTradeDate = option.expiration.strftime('%Y%m%d')

    return cls(localSymbol=option.symbol,
               exchange='SMART',
               currency=option.currency.name,
               lastTradeDateOrContractMonth=lastTradeDate,
               right=option.optionType.value,
               strike=float(option.strike),
               multiplier=str(option.multiplier))


def _futuresContract(future: Future) -> IB.Contract:
    lastTradeDate = future.expiration.strftime('%Y%m%d')

    return IB.Future(symbol=future.symbol,
                     exchange='SMART',
                     currency=future.currency.name,
                     multiplier=str(future.multiplier),
                     lastTradeDateOrContractMonth=lastTradeDate)


def _forexContract(forex: Forex) -> IB.Contract:
    return IB.Forex(pair=forex.symbol, currency=forex.currency.name)


def _contract(instrument: Instrument) -> IB.Contract:
    if isinstance(instrument, Stock):
        return _stockContract(instrument)
    elif isinstance(instrument, Bond):
        return _bondContract(instrument)
    elif isinstance(instrument, FutureOption):
        return _optionContract(instrument, cls=IB.FuturesOption)
    elif isinstance(instrument, Option):
        return _optionContract(instrument)
    elif isinstance(instrument, Future):
        return _futuresContract(instrument)
    elif isinstance(instrument, Forex):
        return _forexContract(instrument)
    else:
        raise ValueError(f'Unexpected type of instrument: {instrument!r}')


# https://interactivebrokers.github.io/tws-api/market_data_type.html
class _MarketDataType(IntEnum):
    LIVE = 1
    FROZEN = 2
    DELAYED = 3
    DELAYED_FROZEN = 4


class IBDataProvider(MarketDataProvider):
    def __init__(self, client: IB.IB):
        self._client = client
        super().__init__()

    def qualifyContracts(self, instruments: Iterable[Instrument]
                         ) -> Dict[Instrument, IB.Contract]:
        # IB.Contract is not guaranteed to be hashable, so we orient the table this way, albeit less useful.
        # TODO: Check uniqueness of instruments
        contractsByInstrument: Dict[Instrument, IB.Contract] = {
            i: _contract(i)
            for i in instruments
        }

        self._client.qualifyContracts(*contractsByInstrument.values())

        return contractsByInstrument

    def fetchHistoricalData(self, instrument: Instrument) -> pd.DataFrame:
        contractsByInstrument = self.qualifyContracts([instrument])
        data = self._client.reqHistoricalData(
            contractsByInstrument[instrument],
            endDateTime='',
            durationStr='10 Y',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1)
        return IB.util.df(data)

    def fetchQuotes(self,
                    instruments: Iterable[Instrument],
                    dataType: _MarketDataType = _MarketDataType.DELAYED_FROZEN
                    ) -> Iterable[Tuple[Instrument, Quote]]:
        self._client.reqMarketDataType(dataType.value)

        contractsByInstrument = self.qualifyContracts(instruments)

        # Note: this blocks until all tickers come back. When we want this to be async, we'll need to use reqMktData().
        # See https://github.com/jspahrsummers/bankroll/issues/13.
        tickers = self._client.reqTickers(*contractsByInstrument.values())

        for ticker in tickers:
            instrument = next((i for (i, c) in contractsByInstrument.items()
                               if c == ticker.contract))

            bid: Optional[Cash] = None
            ask: Optional[Cash] = None
            last: Optional[Cash] = None
            close: Optional[Cash] = None

            factor = 1

            # Tickers are quoted in GBX despite all the other data being in GBP.
            if instrument.currency == Currency.GBP:
                factor = 100

            if (ticker.bid
                    and math.isfinite(ticker.bid)) and not ticker.bidSize == 0:
                bid = Cash(currency=instrument.currency,
                           quantity=Decimal(ticker.bid) / factor)
            if (ticker.ask
                    and math.isfinite(ticker.ask)) and not ticker.askSize == 0:
                ask = Cash(currency=instrument.currency,
                           quantity=Decimal(ticker.ask) / factor)
            if (ticker.last and math.isfinite(
                    ticker.last)) and not ticker.lastSize == 0:
                last = Cash(currency=instrument.currency,
                            quantity=Decimal(ticker.last) / factor)
            if ticker.close and math.isfinite(ticker.close):
                close = Cash(currency=instrument.currency,
                             quantity=Decimal(ticker.close) / factor)

            yield (instrument, Quote(bid=bid, ask=ask, last=last, close=close))


class IBAccount(AccountData):
    _cachedActivity: Optional[Sequence[Activity]] = None
    _client: Optional[IB.IB] = None

    @classmethod
    def fromSettings(cls, settings: Mapping[configuration.Settings, str],
                     lenient: bool) -> 'IBAccount':
        port = settings.get(Settings.TWS_PORT)

        tradesSetting = settings.get(Settings.TRADES)
        trades: Union[Path, int, None]
        if tradesSetting:
            path = Path(tradesSetting)
            if path.is_file():
                trades = path
            else:
                trades = int(tradesSetting)

        activitySetting = settings.get(Settings.ACTIVITY)
        activity: Union[Path, int, None]
        if activitySetting:
            path = Path(activitySetting)
            if path.is_file():
                activity = path
            else:
                activity = int(activitySetting)

        return cls(twsPort=int(port) if port else None,
                   flexToken=settings.get(Settings.FLEX_TOKEN),
                   trades=trades,
                   activity=activity,
                   lenient=lenient)

    def __init__(self,
                 twsPort: Optional[int] = None,
                 flexToken: Optional[str] = None,
                 trades: Union[Path, int, None] = None,
                 activity: Union[Path, int, None] = None,
                 lenient: bool = False):
        self._twsPort = twsPort
        self._flexToken = flexToken
        self._trades = trades
        self._activity = activity
        self._lenient = lenient
        super().__init__()

    @property
    def client(self) -> Optional[IB.IB]:
        if not self._twsPort:
            return None

        if not self._client:
            self._client = IB.IB()
            self._client.connect(
                '127.0.0.1',
                port=self._twsPort,
                # Random client ID to minimize chances of conflict
                clientId=randint(1, 1000000),
                readonly=True)

        return self._client

    def positions(self) -> Iterable[Position]:
        if not self.client:
            return []

        return _downloadPositions(self.client, self._lenient)

    def activity(self) -> Iterable[Activity]:
        if self._cachedActivity:
            return self._cachedActivity

        self._cachedActivity = []

        if isinstance(self._trades, Path):
            self._cachedActivity += _parseTrades(self._trades,
                                                 lenient=self._lenient)
        elif self._trades:
            if not self._flexToken:
                raise ValueError(
                    f'Trades "{self._trades}"" must exist as local path, or a Flex token must be provided to run as a query'
                )

            self._cachedActivity += _downloadTrades(token=self._flexToken,
                                                    queryID=self._trades,
                                                    lenient=self._lenient)

        if isinstance(self._activity, Path):
            self._cachedActivity += _parseNonTradeActivity(
                self._activity, lenient=self._lenient)
        elif self._activity:
            if not self._flexToken:
                raise ValueError(
                    f'Activity "{self._activity}"" must exist as local path, or a Flex token must be provided to run as a query'
                )

            self._cachedActivity += _downloadNonTradeActivity(
                token=self._flexToken,
                queryID=self._activity,
                lenient=self._lenient)

        return self._cachedActivity

    def balance(self) -> AccountBalance:
        if not self.client:
            return AccountBalance(cash={})

        return _downloadBalance(self.client, self._lenient)

    @property
    def marketDataProvider(self) -> Optional[MarketDataProvider]:
        return IBDataProvider(client=self.client)
