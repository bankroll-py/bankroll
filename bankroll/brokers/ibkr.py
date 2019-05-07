from datetime import datetime
from decimal import Context, Decimal, DivisionByZero, Overflow, InvalidOperation, localcontext
from enum import IntEnum
from itertools import count
from bankroll.model import Currency, Cash, Instrument, Stock, Bond, Option, OptionType, FutureOption, Future, Forex, Position, TradeFlags, Trade, MarketDataProvider, Quote, Activity, DividendPayment
from bankroll.parsetools import lenientParse
from pathlib import Path
from progress.spinner import Spinner
from typing import Any, Awaitable, Callable, Dict, Iterable, List, NamedTuple, Optional, Tuple, Type, no_type_check

import backoff
import ib_insync as IB
import logging
import math
import re


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


def downloadPositions(ib: IB.IB, lenient: bool) -> List[Position]:
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


def _parseIBDate(datestr: str) -> datetime:
    return datetime.strptime(datestr, '%Y%m%d')


def _parseFutureOptionTrade(trade: _IBTradeConfirm) -> Instrument:
    if trade.putCall == 'C':
        optionType = OptionType.CALL
    elif trade.putCall == 'P':
        optionType = OptionType.PUT
    else:
        raise ValueError(f'Unexpected value for putCall in IB trade: {trade}')

    return FutureOption(symbol=trade.symbol,
                        currency=Currency[trade.currency],
                        underlying=trade.underlyingSymbol,
                        optionType=optionType,
                        expiration=_parseIBDate(trade.expiry).date(),
                        strike=_parseFiniteDecimal(trade.strike),
                        multiplier=_parseFiniteDecimal(trade.multiplier))


def _parseTradeConfirm(trade: _IBTradeConfirm) -> Trade:
    tag = trade.assetCategory
    symbol = trade.symbol
    if not symbol:
        raise ValueError(f'Missing symbol in trade: {trade}')

    if trade.currency not in Currency.__members__:
        raise ValueError(f'Unrecognized currency in trade: {trade}')

    currency = Currency[trade.currency]

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
                                          trade.multiplier))
        elif tag == 'FUT':
            instrument = Future(symbol=symbol,
                                currency=currency,
                                multiplier=_parseFiniteDecimal(
                                    trade.multiplier),
                                expiration=_parseIBDate(trade.expiry).date())
        elif tag == 'CASH':
            instrument = _parseForex(symbol=symbol, currency=currency)
        elif tag == 'FOP':
            instrument = _parseFutureOptionTrade(trade)
        else:
            raise ValueError(
                f'Unrecognized/unsupported security type in trade: {trade}')

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

        return Trade(date=_parseIBDate(trade.tradeDate),
                     instrument=instrument,
                     quantity=_parseFiniteDecimal(trade.quantity),
                     amount=Cash(currency=Currency(trade.currency),
                                 quantity=_parseFiniteDecimal(trade.proceeds)),
                     fees=Cash(
                         currency=Currency(trade.commissionCurrency),
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


def parseTrades(path: Path, lenient: bool = False) -> List[Trade]:
    return _tradesFromReport(IB.FlexReport(path=path), lenient=lenient)


def _parseChangeInDividendAccrual(entry: _IBChangeInDividendAccrual
                                  ) -> Optional[Activity]:
    codes = entry.code.split(';')
    if 'Re' not in codes:
        return None

    if entry.assetCategory != 'STK':
        raise ValueError(
            f'Expected to see dividend accrual for a stock, not {entry.assetCategory}: {entry}'
        )

    # IB "reverses" dividend postings when they're paid out, so they all appear as debits.
    proceeds = Cash(currency=Currency(entry.currency),
                    quantity=-Decimal(entry.netAmount))

    return DividendPayment(date=_parseIBDate(entry.payDate),
                           stock=Stock(entry.symbol,
                                       currency=Currency(entry.currency)),
                           proceeds=proceeds)


def _activityFromReport(report: IB.FlexReport,
                        lenient: bool) -> List[Activity]:
    return list(
        filter(
            None,
            lenientParse((_IBChangeInDividendAccrual(**x.__dict__)
                          for x in report.extract('ChangeInDividendAccrual',
                                                  parseNumbers=False)),
                         transform=_parseChangeInDividendAccrual,
                         lenient=lenient)))


# TODO: This should eventually be unified with trade parsing.
# See https://github.com/jspahrsummers/bankroll/issues/36.
def parseNonTradeActivity(path: Path, lenient: bool = False) -> List[Activity]:
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
        logger.addHandler(handler)

        try:
            spinner.next()
            return IB.FlexReport(token=token, queryId=queryID)
        finally:
            logger.removeHandler(handler)


def downloadTrades(token: str, queryID: int,
                   lenient: bool = False) -> List[Trade]:
    return _tradesFromReport(_downloadFlexReport(name='Trades',
                                                 token=token,
                                                 queryID=queryID),
                             lenient=lenient)


# TODO: This should eventually be unified with trade parsing.
# See https://github.com/jspahrsummers/bankroll/issues/36.
def downloadNonTradeActivity(token: str, queryID: int,
                             lenient: bool = False) -> List[Activity]:
    return _activityFromReport(_downloadFlexReport(name='Activity',
                                                   token=token,
                                                   queryID=queryID),
                               lenient=lenient)


def _stockContract(stock: Stock) -> IB.Contract:
    return IB.Stock(symbol=stock.symbol,
                    exchange='SMART',
                    currency=stock.currency.value)


def _bondContract(bond: Bond) -> IB.Contract:
    return IB.Bond(symbol=bond.symbol,
                   exchange='SMART',
                   currency=bond.currency.value)


def _optionContract(option: Option,
                    cls: Type[IB.Contract] = IB.Option) -> IB.Contract:
    lastTradeDate = option.expiration.strftime('%Y%m%d')

    return cls(localSymbol=option.symbol,
               exchange='SMART',
               currency=option.currency.value,
               lastTradeDateOrContractMonth=lastTradeDate,
               right=option.optionType.value,
               strike=float(option.strike),
               multiplier=str(option.multiplier))


def _futuresContract(future: Future) -> IB.Contract:
    lastTradeDate = future.expiration.strftime('%Y%m%d')

    return IB.Future(symbol=future.symbol,
                     exchange='SMART',
                     currency=future.currency.value,
                     multiplier=str(future.multiplier),
                     lastTradeDateOrContractMonth=lastTradeDate)


def _forexContract(forex: Forex) -> IB.Contract:
    return IB.Forex(pair=forex.symbol, currency=forex.currency.value)


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

    def fetchQuotes(self,
                    instruments: Iterable[Instrument],
                    dataType: _MarketDataType = _MarketDataType.DELAYED_FROZEN
                    ) -> Iterable[Tuple[Instrument, Quote]]:
        self._client.reqMarketDataType(dataType.value)

        # IB.Contract is not guaranteed to be hashable, so we orient the table this way, albeit less useful.
        # TODO: Check uniqueness of instruments
        contractsByInstrument: Dict[Instrument, IB.Contract] = {
            i: _contract(i)
            for i in instruments
        }

        self._client.qualifyContracts(*contractsByInstrument.values())

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

            if (ticker.bid
                    and math.isfinite(ticker.bid)) and not ticker.bidSize == 0:
                bid = Cash(currency=instrument.currency,
                           quantity=Decimal(ticker.bid))
            if (ticker.ask
                    and math.isfinite(ticker.ask)) and not ticker.askSize == 0:
                ask = Cash(currency=instrument.currency,
                           quantity=Decimal(ticker.ask))
            if (ticker.last and math.isfinite(
                    ticker.last)) and not ticker.lastSize == 0:
                last = Cash(currency=instrument.currency,
                            quantity=Decimal(ticker.last))
            if ticker.close and math.isfinite(ticker.close):
                close = Cash(currency=instrument.currency,
                             quantity=Decimal(ticker.close))

            yield (instrument, Quote(bid=bid, ask=ask, last=last, close=close))
