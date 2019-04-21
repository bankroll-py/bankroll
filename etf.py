import math
import pandas as pd
import numpy as np
import pyfolio as pf
from typing import Optional, List, Dict
from decimal import Decimal
import model
from dataclasses import asdict
from ib_insync import util
import ib_insync as ibapi


def etf(portfolio: pd.DataFrame) -> pd.Series:
    """
    Returns a time series representing the investment of $1 in a basket of instruments weighted proportionally by the given weights.

    @param val: A DataFrame of instruments containing Open, Close, and Weight data indexed by Date.
    """
    # Initialize a zero'd out T-sized array where T is the length of the date range.
    etf = np.zeros(portfolio.loc['open'].shape[0])
    etf[0] = Decimal(1)  # Initial AUM for this instrument is $1.

    # Initialize an I x T array of holdings over time so we can keep track of how we've divided our AUM
    # across the given instruments over time.
    hodls = np.zeros(portfolio.loc['open'].shape)

    for t in range(1, etf.shape[0]):
        portfolio_sum: Decimal = Decimal(0)

        for i in portfolio.columns:
            # Calculate the absolute change of asset i from time t to t - 1.
            change = delta(portfolio, i, t)

            # TODO: Figure out where to get dividend information if it's not calculated into the price.
            dividend = Decimal(0)
            exchange_rate = Decimal(1)

            # Calculate the holdings of instrument i at t - 1 and store it in our hodls matrix.
            holdings_t_minus_1 = holdings(portfolio, hodls, i, t - 1,
                                          etf[t - 1])
            hodls[t - 1][portfolio.columns.get_loc(i)] = holdings_t_minus_1

            portfolio_sum += holdings_t_minus_1 * exchange_rate * (change +
                                                                   dividend)

        # The AUM of the etf at time t is the AUM of the etf at t - 1 plus
        # the sum of the changes in the instruments from t-1 to t accounting
        # for exchange rates, transaction costs, and dividends.
        etf[t] = Decimal(etf[t - 1]) + portfolio_sum
    return etf


def portfolio_to_returns(portfolio: pd.DataFrame, timezone: str) -> pd.Series:
    index = portfolio.index.levels[1].tz_localize(timezone)
    prices = pd.Series(etf(portfolio), index=index)
    return prices_to_daily_returns(prices)


def prices_to_daily_returns(prices: pd.Series) -> pd.Series:
    """
    Calculates daily returns for a Series of prices.
    Note: drops the first value of the given Series.
    """
    return (prices / prices.shift(1) - 1)[1:]


def positions_to_dataframe(positions: List[model.Position]) -> pd.DataFrame:
    """
    Returns a dataframe of positions with an additional `value` and `allocation` columns
    calculated from the averagePrice and quantity.
    """
    is_stock = lambda position: type(position.instrument) == model.Stock
    stocks = []
    for p in filter(is_stock, positions):
        stock = asdict(p)
        avgPrice = p.averagePrice
        stock['averagePrice'] = avgPrice.quantity
        stock['currency'] = avgPrice.currency.value
        stocks.append(stock)

    frame = pd.DataFrame.from_dict(stocks)
    frame["value"] = frame["averagePrice"] * frame["quantity"]
    frame["allocation"] = frame["value"] / frame["value"].sum()
    return frame


def positions_and_history_to_returns(frame: pd.DataFrame,
                                     historical_data: pd.DataFrame,
                                     timezone: str) -> pd.Series:
    """
    Returns a Series of returns calculated by allocating $1 to the given historical data assets by the allocations specified in a positions frame.
    The timezones of the returns series are localized to the given timezone.
    """
    weights = {}
    components = {}
    for i, row in frame.iterrows():
        weights[row['instrument'].symbol] = row['allocation']
        components[row['instrument'].symbol] = historical_data[i]

    portfolio = stocks_to_portfolio(components, weights)

    return portfolio_to_returns(portfolio, timezone)


def position_dataframe_to_history(ib: ibapi.IB,
                                  frame: pd.DataFrame) -> List[pd.DataFrame]:
    """
    Returns 1 year of daily historical data for a dataframe of positions.
    """
    bars = []
    for i, row in frame.iterrows():
        stock = ibapi.Stock(row['instrument'], 'SMART', row['currency'])
        contracts = ib.reqContractDetails(stock)
        ib.qualifyContracts(
            stock)  # Fill in the stock struct with contract details from IB.

        bars.append(
            ib.reqHistoricalData(stock,
                                 endDateTime='',
                                 durationStr='1 Y',
                                 barSizeSetting='1 day',
                                 whatToShow='TRADES',
                                 useRTH=True,
                                 formatDate=1))
    return list(map(util.df, bars))


def holdings(val: pd.DataFrame, hodls: np.ndarray, i: pd.DataFrame, t: int,
             aum_t: int) -> Decimal:
    open_price = val[i].loc['open'][t]

    # If the open price is NaN, this instrument's open wasn't recorded at time t.
    # So let's use the previous day's calculation.
    if math.isnan(open_price):
        prev_day: Decimal = hodls[t - 1][val.columns.get_loc(i)]
        return prev_day
    else:
        # TODO: make the exchange rate flexible. This should generally be the dollar value of 1 point of instrument i.
        exchange_rate = Decimal(1)
        # The purpose of the (weights_i_t * sum_of_weights ^ -1) in the holdings calculation is to de-lever the allocations.
        sum_of_weights: Decimal = val.loc['weight'].iloc[t].abs().sum()

        # If today was t + 1, one way to calculate today's holdings would be by using the opening price, since for a future
        # we may not know the closing price of a new contract at roll time.
        # If open prices are unavailable, then the last close price at t will work too.
        next_open = val[i].loc['close'][t]
        if math.isnan(next_open):
            last_close_price: Decimal = hodls[t - 1][val.columns.get_loc(i)]
            return last_close_price

        weighted_holding: Decimal = Decimal(
            val[i].loc['weight'][t]) * Decimal(aum_t) / Decimal(
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
    return pd.concat(instruments, join='inner', sort=False, axis=1)
