import math
import pandas as pd
import numpy as np
import pyfolio as pf
from typing import Optional, List, Dict


def etf(portfolio: pd.DataFrame) -> pd.Series:
    """
    Returns a time series representing the investment of $1 in a basket of instruments weighted proportionally by the given weights.

    @param val: A DataFrame of instruments containing Open, Close, and Weight data indexed by Date.
    """
    # Initialize a zero'd out T-sized array where T is the length of the date range.
    etf = np.zeros(portfolio.loc['Open'].shape[0])
    etf[0] = 1  # Initial AUM for this instrument is $1.

    # Initialize an I x T array of holdings over time so we can keep track of how we've divided our AUM
    # across the given instruments over time.
    hodls = np.zeros(portfolio.loc['Open'].shape)

    for t in range(1, etf.shape[0]):
        portfolio_sum: float = 0

        for i in portfolio.columns:
            # Calculate the absolute change of asset i from time t to t - 1.
            change = delta(portfolio, i, t)

            # TODO: Figure out where to get dividend information if it's not calculated into the price.
            dividend = 0
            exchange_rate = 1

            # Calculate the holdings of instrument i at t - 1 and store it in our hodls matrix.
            holdings_t_minus_1 = holdings(portfolio, hodls, i, t - 1,
                                          etf[t - 1])
            hodls[t - 1][portfolio.columns.get_loc(i)] = holdings_t_minus_1

            portfolio_sum += holdings_t_minus_1 * exchange_rate * (change +
                                                                   dividend)

        # The AUM of the etf at time t is the AUM of the etf at t - 1 plus
        # the sum of the changes in the instruments from t-1 to t accounting
        # for exchange rates, transaction costs, and dividends.
        etf[t] = etf[t - 1] + portfolio_sum
    return etf


def portfolio_to_returns(portfolio: pd.DataFrame) -> pd.Series:
    index = portfolio.index.levels[1].tz_localize('America/New_York')
    prices = pd.Series(etf(portfolio), index=index)
    return prices_to_daily_returns(prices)


def prices_to_daily_returns(prices: pd.Series) -> pd.Series:
    """
    Calculates daily returns for a Series of prices.
    Note: drops the first value of the given Series.
    """
    return (prices / prices.shift(1) - 1)[1:]


def universe_to_returns(universe: str,
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None) -> pd.Series:
    start_date = start_date if start_date != None else "1990-01-01"
    end_date = end_date if end_date != None else "2019-01-11"

    historical_prices = get_historical_prices(
        universe,
        start_date=start_date,
        end_date=end_date,
        fields=["Open", "High", "Low", "Close", "Volume"])
    closes = historical_prices.loc["Close"]
    ID = closes.columns[0]
    index = closes.index.tz_localize('America/New_York')
    prices = pd.Series(closes.loc[:, ID].values,
                       index=index)  # Turn dataframe into series of prices
    return prices_to_daily_returns(prices)


# FIXME: Finish this function
def get_historical_prices(universe: str,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None,
                          fields: List[str] = []) -> pd.DataFrame:
    return pd.DataFrame({})


def tear_sheet_from_returns(returns: pd.Series,
                            benchmark: str,
                            start_date: Optional[str] = None,
                            end_date: Optional[str] = None,
                            live_start_date: str = '2018-01-01') -> None:
    start_date = start_date if start_date != None else returns.index[
        0].strftime('%Y-%m-%d')
    end_date = end_date if end_date != None else returns.index[-1].strftime(
        '%Y-%m-%d')
    benchmark_returns = universe_to_returns(benchmark,
                                            start_date=start_date,
                                            end_date=end_date)

    pf.create_returns_tear_sheet(returns,
                                 benchmark_rets=benchmark_returns,
                                 live_start_date=live_start_date)
    pf.create_returns_tear_sheet(benchmark_returns,
                                 live_start_date=live_start_date)


def holdings(val: pd.DataFrame, hodls: np.ndarray, i: pd.DataFrame, t: int,
             aum_t: int) -> float:
    open_price = val[i].loc['Open'][t]

    # If the open price is NaN, this instrument's open wasn't recorded at time t.
    # So let's use the previous day's calculation.
    if math.isnan(open_price):
        prev_day: float = hodls[t - 1][val.columns.get_loc(i)]
        return prev_day
    else:
        # TODO: make the exchange rate flexible. This should generally be the dollar value of 1 point of instrument i.
        exchange_rate = 1
        # The purpose of the (weights_i_t * sum_of_weights ^ -1) in the holdings calculation is to de-lever the allocations.
        sum_of_weights = np.sum(np.abs(val.loc['Weight'].iloc[t]))

        # If today was t + 1, one way to calculate today's holdings would be by using the opening price, since for a future
        # we may not know the closing price of a new contract at roll time.
        # If open prices are unavailable, then the last close price at t will work too.
        next_open = val[i].loc['Close'][t]
        if math.isnan(next_open):
            last_close_price: float = hodls[t - 1][val.columns.get_loc(i)]
            return last_close_price

        weighted_holding: float = val[i].loc['Weight'][
            t] * aum_t / next_open * exchange_rate * sum_of_weights
        return weighted_holding


def delta(val: pd.DataFrame, i: str, t: int) -> float:
    """
    This function measures the change in market value from t - 1 to t.
    """
    before: float = val[i].loc["Close"][t - 1]
    after: float = val[i].loc["Close"][t]
    if (math.isnan(before) or math.isnan(after)):
        return 0

    return after - before


def etfs_and_components_to_portfolio(etfs: pd.DataFrame, xs: Dict[str, float],
                                     weights: Dict[str, float]
                                     ) -> pd.DataFrame:
    components = []
    for key, val in etfs.items():
        prices = get_historical_prices(
            val, fields=["Open", "High", "Low", "Close", "Volume"])
        arrays = [[
            'Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume',
            'Weight'
        ], prices.index.levels[1]]
        df = prices.reindex(
            pd.MultiIndex.from_product(arrays, names=['Field', 'Date']))
        df.columns = [key]
        df[key].loc["Weight"] = np.repeat(weights[key],
                                          df[key].loc["Weight"].index.shape[0])
        components.append(df)

    for key, val in xs.items():
        arrays = [[
            'Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume'
        ],
                  pd.DatetimeIndex(val['Date'])]
        index = pd.MultiIndex.from_product(arrays, names=['Field', 'Date'])
        df = pd.DataFrame(val.unstack().values, index=index)
        df.columns = [key]
        arrays = [[
            'Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume',
            'Weight'
        ],
                  pd.DatetimeIndex(val['Date'])]
        df = df.reindex(
            pd.MultiIndex.from_product(arrays, names=['Field', 'Date']))
        df[key].loc["Weight"] = np.repeat(weights[key],
                                          df[key].loc["Weight"].index.shape[0])
        components.append(df)
    return pd.concat(components, join='inner', sort=False, axis=1)
