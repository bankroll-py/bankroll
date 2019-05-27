from decimal import Decimal
from functools import reduce
from itertools import groupby
from .model import Activity, Cash, CashPayment, Currency, Trade, Instrument, Option, MarketDataProvider, Quote, Position, Forex
from progress.bar import Bar
from typing import Dict, Iterable, Optional, Sequence, Tuple

import operator
import re


# Different brokers represent "identical" symbols differently, and they can all be valid.
# This function normalizes them so they can be compared across time and space.
def _normalizeSymbol(symbol: str) -> str:
    # These issues mostly show up with separators for multi-class shares (like BRK A and B)
    return re.sub(r'[\.\s/]', '', symbol)


def _activityAffectsSymbol(activity: Activity, symbol: str) -> bool:
    normalized = _normalizeSymbol(symbol)

    if isinstance(activity, CashPayment):
        return _normalizeSymbol(activity.instrument.symbol) == normalized
    elif isinstance(activity, Trade):
        return (isinstance(activity.instrument, Option) and _normalizeSymbol(
            activity.instrument.underlying) == normalized) or _normalizeSymbol(
                activity.instrument.symbol) == normalized
    else:
        return False


# Calculates the "realized" basis for a particular symbol, given a trade history. This refers to the actual amounts paid in and out, including dividend payments, as well as money gained or lost on derivatives related to that symbol (e.g., short puts, covered calls).
#
# The principle here is that we want to treat dividends and options premium as "gains," where cost basis gets reduced over time as proceeds are paid out. This is not how the tax accounting works, of course, but it provides a different view into the return/profitability of an investment.
def realizedBasisForSymbol(symbol: str,
                           activity: Iterable[Activity]) -> Optional[Cash]:
    def f(basis: Optional[Cash], activity: Activity) -> Optional[Cash]:
        if isinstance(activity, CashPayment):
            return basis - activity.proceeds if basis else -activity.proceeds
        elif isinstance(activity, Trade):
            return basis - activity.proceeds if basis else -activity.proceeds
        else:
            raise ValueError(f'Unexpected type of activity: {activity}')

    return reduce(f,
                  (t for t in activity if _activityAffectsSymbol(t, symbol)),
                  None)


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

    # TODO: Check uniqueness of instruments
    positionsByInstrument = {p.instrument: p for p in positions}

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


# Looks up how much the `quoteCurrency` is currently worth in each of the other
# currencies.
#
# Returns each of the other currencies (possibly out-of-order), along with a
# cash price denominated in the `quoteCurrency`. If a quote is not available
# for some reason, it is omitted from the results.
def currencyConversionRates(
        quoteCurrency: Currency,
        otherCurrencies: Iterable[Currency],
        dataProvider: MarketDataProvider,
) -> Iterable[Tuple[Currency, Cash]]:
    currenciesByInstrument: Dict[Instrument, Currency] = {
        Forex(baseCurrency=currency, quoteCurrency=quoteCurrency): currency
        for currency in otherCurrencies
    }

    return ((currenciesByInstrument[instrument], q.market) for instrument, q in
            dataProvider.fetchQuotes(currenciesByInstrument.keys())
            if q.market)


# Converts the given cash values into `quoteCurrency` using forex market quotes.
def convertCashToCurrency(quoteCurrency: Currency, cash: Sequence[Cash],
                          dataProvider: MarketDataProvider) -> Cash:
    currencyRates = dict(
        currencyConversionRates(quoteCurrency=quoteCurrency,
                                otherCurrencies=(c.currency for c in cash
                                                 if c != quoteCurrency),
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
