from datetime import datetime
from decimal import Context, Decimal, DivisionByZero, Overflow, InvalidOperation, localcontext
from enum import IntEnum
from model import Currency, Cash, Instrument, Stock, Bond, Option, OptionType, FutureOption, Future, Forex, Position, TradeFlags, Trade, LiveDataProvider, Quote
from parsetools import lenientParse
from pathlib import Path
from progress.spinner import Spinner
from typing import Awaitable, Callable, Dict, List, NamedTuple, Optional, Type

import ib_insync as IB
import logging
import math
import re


def parseFiniteDecimal(input: str) -> Decimal:
    with localcontext(ctx=Context(traps=[DivisionByZero, Overflow])):
        value = Decimal(input)
        if not value.is_finite():
            raise ValueError(f'Input is not numeric: {input}')

        return value


def parseOption(symbol: str,
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
               strike=parseFiniteDecimal(match['strike']) / 1000)


def parseForex(symbol: str, currency: Currency) -> Forex:
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


def parseFutureOptionContract(contract: IB.Contract,
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
                        expiration=datetime.strptime(
                            contract.lastTradeDateOrContractMonth,
                            '%Y%m%d').date(),
                        strike=parseFiniteDecimal(contract.strike),
                        multiplier=parseFiniteDecimal(contract.multiplier))


def extractPosition(p: IB.Position) -> Position:
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
            instrument = parseOption(symbol=symbol,
                                     currency=currency,
                                     multiplier=parseFiniteDecimal(
                                         p.contract.multiplier))
        elif tag == 'FUT':
            instrument = Future(
                symbol=symbol,
                currency=currency,
                multiplier=parseFiniteDecimal(p.contract.multiplier),
                expiration=datetime.strptime(
                    p.contract.lastTradeDateOrContractMonth, '%Y%m%d').date())
        elif tag == 'FOP':
            instrument = parseFutureOptionContract(p.contract,
                                                   currency=currency)
        elif tag == 'CASH':
            instrument = parseForex(symbol=symbol, currency=currency)
        else:
            raise ValueError(
                f'Unrecognized/unsupported security type in position: {p}')

        qty = parseFiniteDecimal(p.position)
        costBasis = parseFiniteDecimal(p.avgCost) * qty

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
                     transform=extractPosition,
                     lenient=lenient))


class IBTradeConfirm(NamedTuple):
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


def parseFutureOptionTrade(trade: IBTradeConfirm) -> Instrument:
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
                        expiration=datetime.strptime(trade.expiry,
                                                     '%Y%m%d').date(),
                        strike=parseFiniteDecimal(trade.strike),
                        multiplier=parseFiniteDecimal(trade.multiplier))


def parseTradeConfirm(trade: IBTradeConfirm) -> Trade:
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
            instrument = parseOption(symbol=symbol,
                                     currency=currency,
                                     multiplier=parseFiniteDecimal(
                                         trade.multiplier))
        elif tag == 'FUT':
            instrument = Future(
                symbol=symbol,
                currency=currency,
                multiplier=parseFiniteDecimal(trade.multiplier),
                expiration=datetime.strptime(trade.expiry, '%Y%m%d').date())
        elif tag == 'CASH':
            instrument = parseForex(symbol=symbol, currency=currency)
        elif tag == 'FOP':
            instrument = parseFutureOptionTrade(trade)
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

        return Trade(date=datetime.strptime(trade.tradeDate, '%Y%m%d'),
                     instrument=instrument,
                     quantity=parseFiniteDecimal(trade.quantity),
                     amount=Cash(currency=Currency(trade.currency),
                                 quantity=parseFiniteDecimal(trade.proceeds)),
                     fees=Cash(
                         currency=Currency(trade.commissionCurrency),
                         quantity=-(parseFiniteDecimal(trade.commission) +
                                    parseFiniteDecimal(trade.tax))),
                     flags=flags)
    except InvalidOperation:
        raise ValueError(
            f'One of the numeric trade values is out of range: {trade}')


def tradesFromReport(report: IB.FlexReport, lenient: bool) -> List[Trade]:
    return list(
        lenientParse(
            (IBTradeConfirm(**t.__dict__)
             for t in report.extract('TradeConfirm', parseNumbers=False)),
            transform=parseTradeConfirm,
            lenient=lenient))


def parseTrades(path: Path, lenient: bool = False) -> List[Trade]:
    return tradesFromReport(IB.FlexReport(path=path), lenient=lenient)


class SpinnerOnLogHandler(logging.Handler):
    def __init__(self, spinner: Spinner):
        self._spinner = spinner
        super().__init__()

    def handle(self, record: logging.LogRecord) -> None:
        self._spinner.next()


def downloadTrades(token: str, queryID: int,
                   lenient: bool = False) -> List[Trade]:
    with Spinner('Downloading trade report ') as spinner:
        handler = SpinnerOnLogHandler(spinner)
        logger = logging.getLogger('ib_insync.flexreport')
        logger.addHandler(handler)

        try:
            spinner.next()
            report = IB.FlexReport(token=token, queryId=queryID)
        finally:
            logger.removeHandler(handler)

    return tradesFromReport(report, lenient=lenient)


def stockContract(stock: Stock) -> IB.Contract:
    return IB.Stock(symbol=stock.symbol,
                    exchange='SMART',
                    currency=stock.currency.value)


def bondContract(bond: Bond) -> IB.Contract:
    return IB.Bond(symbol=bond.symbol,
                   exchange='SMART',
                   currency=bond.currency.value)


def optionContract(option: Option,
                   cls: Type[IB.Contract] = IB.Option) -> IB.Contract:
    lastTradeDate = option.expiration.strftime('%Y%m%d')

    return cls(localSymbol=option.symbol,
               exchange='SMART',
               currency=option.currency.value,
               lastTradeDateOrContractMonth=lastTradeDate,
               right=option.optionType.value,
               strike=float(option.strike),
               multiplier=str(option.multiplier))


def futuresContract(future: Future) -> IB.Contract:
    lastTradeDate = future.expiration.strftime('%Y%m%d')

    return IB.Future(symbol=future.symbol,
                     exchange='SMART',
                     currency=future.currency.value,
                     multiplier=str(future.multiplier),
                     lastTradeDateOrContractMonth=lastTradeDate)


def forexContract(forex: Forex) -> IB.Contract:
    return IB.Forex(pair=forex.symbol, currency=forex.currency.value)


def contract(instrument: Instrument) -> IB.Contract:
    if isinstance(instrument, Stock):
        return stockContract(instrument)
    elif isinstance(instrument, Bond):
        return bondContract(instrument)
    elif isinstance(instrument, FutureOption):
        return optionContract(instrument, cls=IB.FuturesOption)
    elif isinstance(instrument, Option):
        return optionContract(instrument)
    elif isinstance(instrument, Future):
        return futuresContract(instrument)
    elif isinstance(instrument, Forex):
        return forexContract(instrument)
    else:
        raise ValueError(f'Unexpected type of instrument: {instrument!r}')


# https://interactivebrokers.github.io/tws-api/market_data_type.html
class MarketDataType(IntEnum):
    LIVE = 1
    FROZEN = 2
    DELAYED = 3
    DELAYED_FROZEN = 4


class IBDataProvider(LiveDataProvider):
    def __init__(self, client: IB.IB):
        self._client = client
        super().__init__()

    def fetchQuote(self,
                   instrument: Instrument,
                   dataType: MarketDataType = MarketDataType.DELAYED_FROZEN
                   ) -> Quote:
        self._client.reqMarketDataType(dataType.value)

        con = contract(instrument)
        self._client.qualifyContracts(con)

        ticker = self._client.reqTickers(con)[0]
        logging.info(f'Received ticker: {ticker!r}')

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
        if (ticker.last
                and math.isfinite(ticker.last)) and not ticker.lastSize == 0:
            last = Cash(currency=instrument.currency,
                        quantity=Decimal(ticker.last))
        if ticker.close and math.isfinite(ticker.close):
            close = Cash(currency=instrument.currency,
                         quantity=Decimal(ticker.close))

        return Quote(bid=bid, ask=ask, last=last, close=close)
