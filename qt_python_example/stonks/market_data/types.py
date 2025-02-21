import pandas as pd
import numpy as np
from decimal import Decimal, getcontext

#Set Decimal Precision
getcontext().prec = 6

BAR_SIZES = ['1s', '5s', '10s', '15s', '30s', '1m', '2m', '3m', '5m', '10m', '15m', '20m', '30m', '1h', '2h', '3h', '4h', '8h', '1D', '1W', '1M']

def get_empty_bar_dataframe():
    return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

def is_intraday(dataType):
    if dataType.startswith('bars_'):
        return not dataType[-1] in ['D','W','M']
    else:
        return True

class CandleBar(object):
    def __init__(self, time, open_, high, low, close, volume=0):
        self.time = time
        self.open = open_
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume

    @property
    def tuple(self):
        return (self.time, self.open, self.close, self.low, self.high, self.volume)

    @property
    def dataframe(self):
        return pd.DataFrame(np.array([[self.open, self.high, self.low, self.close, self.volume]]), columns=["open", "high", "low", "close", "volume"], index=[self.time])

class MarketDepth(object):
    def __init__(self, ticker_name):
        self.ticker_name = ticker_name
        self.dataframe = pd.DataFrame(columns=["price", "size", "side", "position"])
        self.dataframe = self.dataframe.set_index(["side", "position"])

    def insert(self, position, price, side, size):
        self.dataframe.loc[(side, position), :] = [round(Decimal(price),6), size]

    def update(self, position, price, side, size):
        self.dataframe.loc[(side, position), :] = [round(Decimal(price),6), size]

    def delete(self, position, price, side, size):
        self.dataframe = self.dataframe.drop(index=(side, position))

    def bookData(self, minStep=None):
        try:
            bidData = self.dataframe.loc[1,:].set_index('price').filter(['size'])
            askData = self.dataframe.loc[0,:].set_index('price').filter(['size'])
        except KeyError:
            print('WARNING: KeyError while generating book depth data')
            return pd.DataFrame(columns=["size_bid", "size_ask"])
        except IndexError:
            print('WARNING: IndexError while generating book depth data')
            return pd.DataFrame(columns=["size_bid", "size_ask"])
        data = bidData.join(askData, lsuffix="_bid", rsuffix="_ask", how="outer")
        if minStep:
            minStep = Decimal(minStep)
            data['price_consolidated'] = data.apply(lambda row: (round(Decimal(row.name) / minStep)*minStep) if not pd.isna(row.name) and Decimal(row.name) % minStep != 0 else row.name, axis=1)
            data = data.groupby(data.price_consolidated).sum()
            data.index.name = 'price'
        else:
            data = data.groupby(data.index).sum()
        return data
