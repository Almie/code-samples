from .ibkr import IBApiWrapper, IBRequest
from .yahoo import YahooAPIWrapper

from .base import BaseAPIWrapper, to_thread
from .cache import MarketDataCache
import sys
import inspect

import pandas as pd
from ..utils import trading_offset_factory, get_market_hours, singleton
from ..config import Config

from PySide2.QtCore import Signal

def available_apis():
    apis = []
    for varName in dir(sys.modules[__name__]):
        var = globals()[varName]
        if not inspect.isclass(var):
            continue
        if var == BaseAPIWrapper:
            continue
        if issubclass(var, BaseAPIWrapper):
            apis.append(var)
    return apis

def MarketDataAPI(name, *args, **kwargs):
    for api in available_apis():
        if api.name == name:
            return api(*args, **kwargs)

class MarketData(object):
    onHistoricalBars = Signal(int, str, pd.DataFrame, pd.Timestamp, pd.Timestamp, str, tuple)
    requestTypes = {'historicalBars' : IBRequest.HISTORICAL_BARS,
                            'ticks' : IBRequest.REALTIME_TICKS,
                            'marketDepth': IBRequest.REALTIME_LEVEL2}
    def __init__(self):
        self._cache = MarketDataCache()
        self._precise_api = MarketDataAPI("IBKR")
        self._precise_api.connect("127.0.0.1", 7497)
        self._bulk_api = MarketDataAPI("Yahoo Finance")
        self.config = Config()
        self.twsTimezone = self.config.get_property('twsTimezone', 'US/Pacific')

        self.subscriptions = []

    def historicalBarsCallback(self, callback, data_source, totalStartTime, totalEndTime):
        def wrapper(symbol, barSize, bars, startTime, endTime):
            dataType = 'bars_'+barSize
            self._cache.addData(symbol, dataType, bars, data_source)
            cached_data = self._cache.getData(symbol, dataType, totalStartTime, totalEndTime)
            callback(symbol, barSize, cached_data, totalStartTime, totalEndTime)
        return wrapper

    @to_thread
    def requestHistoricalBars(self, symbol, barSize='1m', startTime=None, endTime=None, callback=None, error_callback=None):
        market_hours = get_market_hours(tz=self.twsTimezone)
        offset = trading_offset_factory(barSize, start=market_hours[0], end=market_hours[-1])

        if endTime is None:
            endTime = offset.rollback(pd.Timestamp.now().round(freq='T').tz_localize(self.twsTimezone))
        if startTime is None:
            startTime = endTime - offset * 200
        
        dataType = 'bars_'+barSize
        missingStartTime, missingEndTime = self._cache.getMissingRange(symbol, dataType, startTime, endTime)
        print('MISSING START AND END', missingStartTime, missingEndTime)
        if not missingStartTime is None:
            wrapped_callback = self.historicalBarsCallback(callback, self._precise_api.name, startTime, endTime)
            print('about to request')
            self._precise_api.requestHistoricalBars(symbol, barSize, missingStartTime, missingEndTime, False, wrapped_callback, error_callback)
        else:
            print('NO REQUEST REQUIRED, GETTING DATA FROM CACHE')
            bars = self._cache.getData(symbol, dataType, startTime, endTime)
            if not callback is None:
                callback(symbol, barSize, bars, startTime, endTime)

    def requestBulkHistoricalBars(self, symbols, barSize='1m', startTime=None, endTime=None, callback=None, error_callback=None):
        pass

    def subscribeToLiveBars(self, symbol, barSize='1m', callback=None, error_callback=None):
        print('LIVE BAR SUBSCRIPTION', symbol, barSize)
        self._precise_api.requestHistoricalBars(symbol, barSize, live=True, live_callback=callback, error_callback=error_callback)
    
    def subscribeToTickData(self, symbol, callback):
        self._precise_api.requestTickData(symbol, callback)

    def subscribeToMarketDepth(self, symbol, callback):
        self._precise_api.requestMarketDepth(symbol, callback)

    def isSubscriptionActive(self, symbol, subscriptionType, barSize=None, live=False):
        requestType = self.requestTypes[subscriptionType]
        return self._precise_api.hasRequest(symbol, requestType, barSize, live)

    def getSubscriptions(self, symbol=None, subscriptionType=None, barSize=None):
        requestType = self.requestTypes[subscriptionType]
        return self._precise_api.getRequests(symbol, requestType, barSize, True)

    def cancelSubscriptions(self, symbol=None, subscriptionType=None):
        requestType = None
        if subscriptionType:
            requestType = self.requestTypes[subscriptionType]
        self._precise_api.cancelRequests(symbol, requestType)
    
    def disconnect(self):
        self._precise_api.disconnect()
