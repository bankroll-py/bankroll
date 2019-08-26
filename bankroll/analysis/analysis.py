import operator
import re
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from functools import reduce
from itertools import groupby
from typing import Dict, Iterable, Optional, Sequence, Tuple

from progress.bar import Bar

from .model import (Activity, Cash, CashPayment, Currency, Forex, Instrument,
                    MarketDataProvider, Option, Position, Quote, Stock, Trade)


# Different brokers represent "identical" symbols differently, and they can all
# be valid. This function normalizes them so they can be compared across time
# and space.
def normalizeSymbol(symbol: str) -> str:
    # These issues mostly show up with separators for multi-class shares (like BRK A and B)
    return re.sub(r'[\.\s/]', '', symbol)


# Performs a similar operation to normalizeSymbol(), but lifted over
# Instruments (where it makes sense).
def normalizeInstrument(instrument: Instrument) -> Instrument:
    if isinstance(instrument, Stock):
        return Stock(symbol=normalizeSymbol(instrument.symbol),
                     currency=instrument.currency,
                     exchange=instrument.exchange)
    elif isinstance(instrument, Option):
        # Handles the FutureOption subclass correctly as well.
        return replace(instrument,
                       underlying=normalizeSymbol(instrument.underlying))
    else:
        return instrument


# Attempts to determine whether the given Activity concerns the provided
# symbol, after normalizing to a form that should permit comparison across
# brokers.
def activityAffectsSymbol(activity: Activity, symbol: str) -> bool:
    normalized = normalizeSymbol(symbol)

    if isinstance(activity, CashPayment):
        return activity.instrument is not None and normalizeSymbol(
            activity.instrument.symbol) == normalized
    elif isinstance(activity, Trade):
        return (isinstance(activity.instrument, Option) and normalizeSymbol(
            activity.instrument.underlying) == normalized) or normalizeSymbol(
                activity.instrument.symbol) == normalized
    else:
        return False


# Calculates the "realized" basis for a particular symbol, given a trade
# history. This refers to the actual amounts paid in and out, including
# dividend payments, as well as money gained or lost on derivatives related to
# that symbol (e.g., short puts, covered calls).
#
# The principle here is that we want to treat dividends and options premium as
# "gains," where cost basis gets reduced over time as proceeds are paid out.
# This is not how the tax accounting works, of course, but it provides a
# different view into the return/profitability of an investment.
def realizedBasisForSymbol(symbol: str,
                           activity: Iterable[Activity]) -> Optional[Cash]:
    def f(basis: Optional[Cash], activity: Activity) -> Optional[Cash]:
        if isinstance(activity, CashPayment):
            return basis - activity.proceeds if basis else -activity.proceeds
        elif isinstance(activity, Trade):
            return basis - activity.proceeds if basis else -activity.proceeds
        else:
            raise ValueError(f'Unexpected type of activity: {activity}')

    return reduce(f, (t for t in activity if activityAffectsSymbol(t, symbol)),
                  None)


@dataclass(frozen=True)
class TimelineEntry:
    date: datetime
    positions: Dict[Instrument, Decimal]
    realizedProfit: Cash

    def __str__(self) -> str:
        strPositions = (
            f'\n\t{instrument:21} {self.positions[instrument].normalize():>14,f}'
            for instrument in sorted(self.positions.keys()))

        return reduce(operator.add, strPositions,
                      f'As of {self.date.date()}: {self.realizedProfit}')


# Traces position sizing and profit/loss of a particular symbol over a period
# of activity. Yields a TimelineEntry corresponding to each action that
# occurred to the given symbol, starting from the oldest and ending with the
# most recent.
def timelineForSymbol(symbol: str,
                      a: Iterable[Activity]) -> Iterable[TimelineEntry]:
    realizedProfit: Optional[Cash] = None
    positions: Dict[Instrument, Decimal] = {}

    for t in sorted((t for t in a if activityAffectsSymbol(t, symbol)),
                    key=lambda t: t.date):
        if isinstance(t, CashPayment) or isinstance(t, Trade):
            proceeds = t.proceeds
        else:
            raise ValueError(f'Unexpected type of activity: {t}')

        if realizedProfit:
            realizedProfit += proceeds
        else:
            realizedProfit = proceeds

        if isinstance(t, Trade):
            instrument = normalizeInstrument(t.instrument)

            newPosition = positions.get(instrument, Decimal(0)) + t.quantity
            if newPosition == Decimal(0):
                del positions[instrument]
            else:
                positions[instrument] = newPosition

        yield TimelineEntry(date=t.date,
                            positions=positions.copy(),
                            realizedProfit=realizedProfit)


def liveValuesForPositions(
        positions: Iterable[Position],
        dataProvider: MarketDataProvider,
        progressBar: Optional[Bar] = None,
) -> Dict[Position, Cash]:
    def priceFromQuote(q: Quote, p: Position) -> Optional[Cash]:
        # For a long position, the value should be what the market is willing to pay right now.
        # For a short position, the value should be what the market is asking to be paid right now.
        if p.quantity < 0:
            return q.ask or q.last or q.bid or q.close
        else:
            return q.bid or q.last or q.ask or q.close

    result = {}

    positionsByInstrument: Dict[Instrument, Position] = {}
    for p in positions:
        if p.instrument in positionsByInstrument:
            raise ValueError(
                f'Expected unique instruments (i.e., deduplicated positions), but saw {p.instrument} multiple times'
            )

        positionsByInstrument[p.instrument] = p

    quotes = dataProvider.fetchQuotes(positionsByInstrument.keys())
    it = progressBar.iter(quotes) if progressBar else quotes

    for (instrument, quote) in it:
        position = positionsByInstrument[instrument]
        price = priceFromQuote(quote, position)
        if not price:
            continue

        result[position] = price * position.quantity * instrument.multiplier

    return result


def deduplicatePositions(positions: Iterable[Position]) -> Iterable[Position]:
    return (reduce(operator.add, ps)
            for i, ps in groupby(sorted(positions, key=lambda p: p.instrument),
                                 key=lambda p: p.instrument))


# Looks up how much each of the `otherCurrencies` cost in terms of
# `quoteCurrency`.
#
# Returns each of the other currencies (possibly out-of-order), along with a
# cash price denominated in the `quoteCurrency`. If a quote is not available
# for some reason, it is omitted from the results.
def currencyConversionRates(
        quoteCurrency: Currency,
        otherCurrencies: Iterable[Currency],
        dataProvider: MarketDataProvider,
) -> Iterable[Tuple[Currency, Cash]]:
    instruments = (Forex(baseCurrency=min(currency, quoteCurrency),
                         quoteCurrency=max(currency, quoteCurrency))
                   for currency in otherCurrencies)

    return (
        (instrument.baseCurrency,
         quote.market) if instrument.quoteCurrency == quoteCurrency else
        (
            instrument.quoteCurrency,
            Cash(
                currency=instrument.baseCurrency,
                # FIXME: This unfortunately does not retain much precision when
                # dividing by JPY in particular (where the integral portion can
                # be quite large).
                # See https://github.com/jspahrsummers/bankroll/issues/37.
                quantity=Decimal(1) / quote.market.quantity))
        for instrument, quote in dataProvider.fetchQuotes(instruments)
        if quote.market and isinstance(instrument, Forex))


# Converts the given cash values into `quoteCurrency` using forex market quotes.
def convertCashToCurrency(quoteCurrency: Currency, cash: Sequence[Cash],
                          dataProvider: MarketDataProvider) -> Cash:
    currencyRates = dict(
        currencyConversionRates(
            quoteCurrency=quoteCurrency,
            otherCurrencies=(c.currency for c in cash
                             if c.currency != quoteCurrency),
            dataProvider=dataProvider))
    currencyRates[quoteCurrency] = Cash(currency=quoteCurrency,
                                        quantity=Decimal(1))

    for c in cash:
        if not c.currency in currencyRates:
            raise RuntimeError(
                f'Unable to fetch currency rate for {c.currency} to convert {c}'
            )

    return reduce(
        operator.add,
        (Cash(currency=quoteCurrency,
              quantity=c.quantity * currencyRates[c.currency].quantity)
         for c in cash), Cash(currency=quoteCurrency, quantity=Decimal(0)))
