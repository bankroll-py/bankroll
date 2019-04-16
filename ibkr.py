from datetime import datetime
from decimal import Decimal
from model import Currency, Cash, Instrument, Stock, Bond, Option, OptionType, FutureOption, Future, Forex, Position, TradeFlags, Trade
from parsetools import lenientParse
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Type

import ib_insync as IB
import re


def parseOption(symbol: str, cls: Type[Option] = Option) -> Option:
    # https://en.wikipedia.org/wiki/Option_symbol#The_OCC_Option_Symbol
    match = re.match(
        r'^(?P<underlying>.{6})(?P<date>\d{6})(?P<putCall>P|C)(?P<strike>\d{8})$',
        symbol)
    if not match:
        raise ValueError('Could not parse IB option symbol: {}'.format(symbol))

    if match['putCall'] == 'P':
        optionType = OptionType.PUT
    else:
        optionType = OptionType.CALL

    return cls(underlying=match['underlying'].rstrip(),
               optionType=optionType,
               expiration=datetime.strptime(match['date'], '%y%m%d').date(),
               strike=Decimal(match['strike']) / 1000)


def extractPosition(p: IB.Position) -> Position:
    instrumentsByTag: Dict[str, Callable[[str], Instrument]] = {
        "STK": Stock,
        "BOND": lambda s: Bond(s, validateSymbol=False),
        "OPT": parseOption,
        "FUT": Future,
        "CASH": Forex,
        # TODO: FOP
    }

    qty = Decimal(p.position)
    costBasis = Decimal(p.avgCost) * qty

    return Position(instrument=instrumentsByTag[p.contract.secType](
        p.contract.localSymbol),
                    quantity=qty,
                    costBasis=Cash(currency=Currency[p.contract.currency],
                                   quantity=costBasis))


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
        raise ValueError(
            'Unexpected value for putCall in IB trade: {}'.format(trade))

    return FutureOption(symbol=trade.symbol,
                        underlying=trade.underlyingSymbol,
                        optionType=optionType,
                        expiration=datetime.strptime(trade.expiry,
                                                     '%Y%m%d').date(),
                        strike=Decimal(trade.strike))


def parseTradeConfirm(trade: IBTradeConfirm) -> Trade:
    instrumentsByTag: Dict[str, Callable[[IBTradeConfirm], Instrument]] = {
        'STK': lambda t: Stock(t.symbol),
        'BOND': lambda t: Bond(t.symbol, validateSymbol=False),
        'OPT': lambda t: parseOption(t.symbol),
        'FUT': lambda t: Future(t.symbol),
        'CASH': lambda t: Forex(t.symbol),
        'FOP': parseFutureOptionTrade,
    }

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

        flags |= flagsByCode[c]

    # Codes are not always populated with open/close, not sure why
    if flags & (TradeFlags.OPEN | TradeFlags.CLOSE) == TradeFlags.NONE:
        if trade.buySell == 'BUY':
            flags |= TradeFlags.OPEN
        else:
            flags |= TradeFlags.CLOSE

    return Trade(
        date=datetime.strptime(trade.tradeDate, '%Y%m%d'),
        instrument=instrumentsByTag[trade.assetCategory](trade),
        quantity=Decimal(trade.quantity),
        amount=Cash(currency=Currency(trade.currency),
                    quantity=Decimal(trade.proceeds)),
        fees=Cash(currency=Currency(trade.commissionCurrency),
                  quantity=-(Decimal(trade.commission) + Decimal(trade.tax))),
        flags=flags)


def tradesFromReport(report: IB.FlexReport, lenient: bool) -> List[Trade]:
    return list(
        lenientParse(
            (IBTradeConfirm(**t.__dict__)
             for t in report.extract('TradeConfirm', parseNumbers=False)),
            transform=parseTradeConfirm,
            lenient=lenient))


def parseTrades(path: Path, lenient: bool = False) -> List[Trade]:
    return tradesFromReport(IB.FlexReport(path=path), lenient=lenient)


def downloadTrades(token: str, queryID: int,
                   lenient: bool = False) -> List[Trade]:
    return tradesFromReport(IB.FlexReport(token=token, queryId=queryID),
                            lenient=lenient)
