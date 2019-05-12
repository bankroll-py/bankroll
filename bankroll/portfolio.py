import math
import pandas as pd
import numpy as np
import pyfolio as pf
from typing import Optional, List, Dict, Iterable, Tuple
from decimal import Decimal
from .model import *
from dataclasses import asdict
from ib_insync import util
import ib_insync as ibapi


def etf(portfolio: pd.DataFrame, timezone: str) -> pd.Series:
    """
    Returns a time series representing the investment of $1 in a basket of instruments weighted proportionally by the given weights.

    @param portfolio: A DataFrame of instruments containing open, close, and weight data indexed by Date.
    """
    index = portfolio.index.levels[1].tz_localize(timezone)
    # Initialize a zero'd out T-sized array where T is the length of the date range.
    etf = np.zeros(portfolio.loc['open'].shape[0])
    etf[0] = Decimal(1)  # Initial AUM for this instrument is $1.

    # Initialize an I x T array of holdings over time so we can keep track of how we've divided our AUM
    # across the given instruments over time.
    holds = np.zeros(portfolio.loc['open'].shape)

    for t in range(1, etf.shape[0]):
        portfolio_sum: Decimal = Decimal(0)

        for i in portfolio.columns:
            # Calculate the absolute change of asset i from time t to t - 1.
            change = delta(portfolio, i, t)

            # TODO: Figure out where to get dividend information if it's not calculated into the price.
            dividend = Decimal(0)
            exchange_rate = Decimal(1)

            # Calculate the holdings of instrument i at t - 1 and store it in our holds matrix.
            holdings_t_minus_1 = holdings(portfolio, holds, i, t - 1,
                                          Decimal(etf[t - 1]))
            holds[t - 1][portfolio.columns.get_loc(i)] = holdings_t_minus_1

            portfolio_sum += holdings_t_minus_1 * exchange_rate * (change +
                                                                   dividend)

        # The AUM of the etf at time t is the AUM of the etf at t - 1 plus
        # the sum of the changes in the instruments from t-1 to t accounting
        # for exchange rates, transaction costs, and dividends.
        etf[t] = Decimal(etf[t - 1]) + portfolio_sum

    return pd.Series(etf, index=index)


def portfolio_to_returns(portfolio: pd.DataFrame, timezone: str) -> pd.Series:
    prices = etf(portfolio, timezone)
    return prices_to_daily_returns(prices)


def prices_to_daily_returns(prices: pd.Series) -> pd.Series:
    """
    Calculates daily returns for a Series of prices.
    Note: drops the first value of the given Series.
    """
    return (prices / prices.shift(1) - 1)[1:]


def positions_to_dataframe(positions: Iterable[Position]
                           ) -> pd.DataFrame:
    """
    Returns a dataframe of positions with an additional `value` and `allocation` columns
    calculated from the averagePrice and quantity.
    """
    is_stock = lambda position: type(position.instrument) == Stock
    stocks = []
    for p in filter(is_stock, positions):
        stock = asdict(p)
        avgPrice = p.averagePrice
        stock['averagePrice'] = avgPrice.quantity
        stock['currency'] = avgPrice.currency
        stocks.append(stock)

    frame = pd.DataFrame.from_dict(stocks)
    frame["value"] = frame["averagePrice"] * frame["quantity"]
    frame["allocation"] = frame["value"] / frame["value"].sum()
    return frame


def positions_to_returns(provider: MarketDataProvider,
                         positions: Iterable[Position],
                         timezone: str) -> pd.Series:
    frame = positions_to_dataframe(positions)
    positions, frame, history = positions_to_history(provider, positions, frame)
    return positions_and_history_to_returns(frame, history, timezone)


def positions_and_history_to_returns(frame: pd.DataFrame,
                                     historical_data: List[pd.DataFrame],
                                     timezone: str) -> pd.Series:
    """
    Returns a Series of returns calculated by allocating $1 to the given historical data assets by the allocations specified in a positions frame.
    The timezones of the returns series are localized to the given timezone.
    """
    portfolio = positions_to_portfolio(frame, historical_data, timezone)
    return portfolio_to_returns(portfolio, timezone)


def positions_to_portfolio(frame: pd.DataFrame,
                           historical_data: List[pd.DataFrame],
                           timezone: str) -> pd.DataFrame:
    """
    Returns a DataFrame of position histories with weights and allocation columns.
    """
    weights = {}
    components = {}
    for i, row in frame.reset_index().iterrows():
        weights[row['instrument'].symbol] = row['allocation']
        components[row['instrument'].symbol] = historical_data[i]

    return stocks_to_portfolio(components, weights)


def positions_to_history(provider: MarketDataProvider,
                         positions: Iterable[Position],
                         frame: pd.DataFrame
                         ) -> Tuple[List[Position], pd.DataFrame, List[pd.DataFrame]]:
    """
    Returns 1 year of daily historical data for a dataframe of positions.
    """
    is_stock = lambda position: type(position.instrument) == Stock
    bars = []
    new_positions = []
    for position in filter(is_stock, positions):
        try:
            barList = provider.fetchHistoricalData(position.instrument)
        except ValueError:
            print("something bad happened")
            continue
        except:
            print("caught an exception")
            continue

        if barList is not None:
            new_positions.append(position)
        bars.append(barList)

    indices = [i for i, x in enumerate(bars) if x is not None]
    return (new_positions, frame.loc[indices], list(filter(lambda x: x is not None, bars)))


def holdings(val: pd.DataFrame, holds: np.ndarray, i: pd.DataFrame, t: int,
             aum_t: Decimal) -> Decimal:
    open_price = Decimal(val[i].loc['open'][t])

    # If the open price is NaN, this instrument's open wasn't recorded at time t.
    # So let's use the previous day's calculation.
    if not open_price.is_finite():
        prev_day: Decimal = holds[t - 1][val.columns.get_loc(i)]
        return prev_day
    else:
        # TODO: make the exchange rate flexible. This should generally be the dollar value of 1 point of instrument i.
        exchange_rate = Decimal(1)
        # The purpose of the (weights_i_t * sum_of_weights ^ -1) in the holdings calculation is to de-lever the allocations.
        sum_of_weights: Decimal = val.loc['weight'].iloc[t].abs().sum()

        # If today was t + 1, one way to calculate today's holdings would be by using the opening price, since for a future
        # we may not know the closing price of a new contract at roll time.
        # If open prices are unavailable, then the last close price at t will work too.
        next_open = Decimal(val[i].loc['close'][t])
        if not next_open.is_finite():
            last_close_price: Decimal = holds[t - 1][val.columns.get_loc(i)]
            return last_close_price

        weighted_holding: Decimal = Decimal(
            val[i].loc['weight'][t]) * aum_t / Decimal(
                next_open) * exchange_rate * Decimal(sum_of_weights)
        return weighted_holding


def delta(val: pd.DataFrame, i: str, t: int) -> Decimal:
    """
    This function measures the change in market value from t - 1 to t.
    """
    before: Decimal = Decimal(val[i].loc["close"][t - 1])
    after: Decimal = Decimal(val[i].loc["close"][t])
    if (math.isnan(before) or math.isnan(after)):
        return Decimal(0)

    return after - before


def stocks_to_portfolio(components: Dict[str, pd.DataFrame],
                        weights: Dict[str, float]) -> pd.DataFrame:
    instruments = []
    for key, val in components.items():
        arrays = [[
            'date', 'open', 'high', 'low', 'close', 'volume', 'barCount',
            'average'
        ],
                  pd.DatetimeIndex(val['date'])]
        index = pd.MultiIndex.from_product(arrays, names=['field', 'date'])
        df = pd.DataFrame(val.unstack().values, index=index)
        df.columns = [key]
        arrays = [[
            'date', 'open', 'high', 'low', 'close', 'volume', 'barCount',
            'average', 'weight'
        ],
                  pd.DatetimeIndex(val['date'])]
        df = df.reindex(
            pd.MultiIndex.from_product(arrays, names=['field', 'date']))
        df[key].loc['weight'] = np.repeat(weights[key],
                                          df[key].loc['weight'].index.shape[0])
        instruments.append(df)
    return pd.concat(instruments, join='inner', sort=False,
                     axis=1).sort_index()
