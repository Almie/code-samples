import pdb
from .base import *
from .types import *
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

from ibapi.contract import Contract
from ibapi.order import *

from decimal import *
import time, datetime, math
import pandas as pd

from ..config import Config
from ..utils import trading_offset_factory, get_market_hours, singleton

from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *

import logging
log = logging.getLogger('Market Data')

BAR_SIZE_REMAP = {'1s':'1 secs','5s':'5 secs','10s':'10 secs','15s':'15 secs','30s':'30 secs',
                '1m':'1 min','2m':'2 mins','3m':'3 mins','5m':'5 mins','10m':'10 mins','15m':'15 mins','20m':'20 mins','30m':'30 mins',
                '1h':'1 hour','2h':'2 hours','3h':'3 hours','4h':'4 hours','8h':'8 hours',
                '1D':'1 day','1W':'1 week','1M':'1 month'}
TIME_FORMAT = "%Y%m%d %H:%M:%S"

def getIbkrDuration(startTime, endTime, barSize):
    if barSize.endswith('s') and int(barSize.replace('s', '')) < 15:
        roundFreq = '6H'
    elif barSize.endswith('s') and int(barSize.replace('s', '')) >= 15:
        roundFreq = '12H'
    elif barSize.endswith('W'):
        n = int(barSize.replace('W', ''))
        roundFreq = '{}D'.format(n*7)
    elif barSize.endswith('M'):
        n = int(barSize.replace('M', ''))
        roundFreq = '{}D'.format(n*30)
    else:
        roundFreq = '1D'

    delta = endTime - startTime
    delta = delta.ceil(freq=roundFreq)
    if delta == pd.Timedelta(0):
        delta = pd.Timedelta(roundFreq)
    if roundFreq.endswith('D'):
        if delta > pd.Timedelta('365D'):
            years = math.ceil(delta / pd.Timedelta('365D'))
            return '{} Y'.format(years)
        return '{} D'.format(delta.days)
    else:
        return '{} S'.format(int(delta.total_seconds()))

class IBApi(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.signals = IBSignals()
        self.config = Config()
        #self.cache = MarketDataCache()

        self.activeRequests = []

        self.historicalBarsBuffer = {}
        self.historicalBarSizes = {}
        self.requestSymbols = {}
        self.marketDepthData = {}
        self.lastMarketDepthUpdate = {}
        self.frequency = self.config.get_property("lvl2_update_frequency", 0.25)
        self.twsTimezone = self.config.get_property("timezone_tws", "US/Pacific")

    def getRequest(self, reqId):
        for request in self.activeRequests:
            if request.tickerId == reqId:
                return request
        return None

    def getNewTickerId(self):
        tickerId = 0
        while tickerId in [r.tickerId for r in self.activeRequests]:
            tickerId += 1
        return tickerId

    def historicalData(self, reqId, bar):
        #print('historicalData: {} {}'.format(reqId, bar))
        timestamp = pd.Timestamp(bar.date, tz=self.twsTimezone)
        request = self.getRequest(reqId)
        if request:
            request.addBarToBuffer(bar, timestamp)
        else:
            log.warning('NO REQUEST', reqId)

    def historicalDataEnd(self, reqId, startDate, endDate):
        #print('historicalDataEnd: {} {} {}'.format(reqId, startDate, endDate))
        startTimeStamp = pd.Timestamp(startDate, tz=self.twsTimezone)
        endTimeStamp = pd.Timestamp(endDate, tz=self.twsTimezone)
        request = self.getRequest(reqId)

        #self.cache.addData(request.symbol, 'bars_{}'.format(request.barSize), bars)
        #print('historicalDataEnd about to emit', reqId, request.symbol, request.getBarsFromBuffer(), startTimeStamp, endTimeStamp, request.barSize, (request.callback))
        self.signals.onHistoricalBarEnd.emit(request.symbol, request.getBarsFromBuffer(), startTimeStamp, endTimeStamp, request.barSize, (request.callback))

        if not request.live_request:
            self.activeRequests.remove(request)

    def historicalDataUpdate(self, reqId, bar):
        timestamp = pd.Timestamp(bar.date, tz=self.twsTimezone)
        bar_df = get_empty_bar_dataframe()
        bar_df.loc[timestamp] = [bar.open, bar.high, bar.low, bar.close, bar.volume]
        request = self.getRequest(reqId)
        self.signals.onHistoricalBarUpdate.emit(request.symbol, bar_df, request.barSize, (request.live_callback))

    def updateMktDepth(self, reqId, position, operation, side, price, size):
        super().updateMktDepth(reqId, position, operation, side, price, size)
        log.debug("UpdateMktDepth, {} {} {} {} {} {}".format(reqId, position, operation, side, price, size))

    def updateMktDepthL2(self, reqId, position, marketMaker, operation, side, price, size, isSmartDepth):
        super().updateMktDepthL2(reqId, position, marketMaker, operation, side, price, size, isSmartDepth)
        #print("UpdateMktDepth, {} {} {} {} {} {}".format(reqId, position, operation, side, price, size))
        request = self.getRequest(reqId)
        if not request:
            return
        if operation == 0: #insert
            request.marketDepthData.insert(position, price, side, size)
        if operation == 1: #update
            request.marketDepthData.update(position, price, side, size)
        if operation == 2: #remove
            request.marketDepthData.delete(position, price, side, size)
        currentTime = time.time()
        if not request.lastMarketDepthUpdate:
            self.signals.onMarketDepthUpdate.emit(request.symbol, request.marketDepthData, (request.callback))
            request.lastMarketDepthUpdate = currentTime
        elif currentTime - request.lastMarketDepthUpdate >= self.frequency:
            self.signals.onMarketDepthUpdate.emit(request.symbol, request.marketDepthData, (request.callback))
            request.lastMarketDepthUpdate = currentTime

    def tickByTickAllLast(self, reqId, tickType, time, price, size, tickAttribLast, exchange, special):
        super().tickByTickAllLast(reqId, tickType, time, price, size, tickAttribLast, exchange, special)
        #print("tick update {} {} {} {}".format(reqId, time, price, size))
        request = self.getRequest(reqId)
        if request:
            self.signals.onTickLastUpdate.emit(request.symbol, time, price, size, (request.callback))

    def error(self, reqId, errorCode, errorMsg, advancedOrderRejectJson=None):
        super().error(id, errorCode, errorMsg)
        if errorCode == 162:
            request = self.getRequest(reqId)
            if request:
                self.signals.onHistoricalBarError.emit(reqId, request.symbol, request.barSize, errorCode, errorMsg)
        log.error('IBKR API Error: {} {} {} {}'.format(reqId, errorCode, errorMsg, advancedOrderRejectJson))

    def scannerParameters(self, xml):
        print(xml)
        with open('F:\\Docs\\git\\stonks\\scannerParams.xml', 'w') as f:
            f.write(xml)
        return super().scannerParameters(xml)

    def connectionClosed(self):
        super().connectionClosed()
        log.info('IBKR API Connection Closed')


class IBSignals(QObject):
    onHistoricalBar = Signal(int, float, float, float, float, float)
    onHistoricalBarUpdate = Signal(str, pd.DataFrame, str, tuple)
    onHistoricalBarEnd = Signal(str, pd.DataFrame, pd.Timestamp, pd.Timestamp, str, tuple)
    onHistoricalBarError = Signal(int, str, str, int, str)
    onMarketDepthUpdate = Signal(str, MarketDepth, tuple)
    onTickLastUpdate = Signal(str, float, float, float, tuple)

class IBThread(QThread):
    def __init__(self, ibapi):
        QThread.__init__(self)
        self.ibapi = ibapi

    def run(self):
        self.ibapi.run()

@singleton
class IBClientIDs(object):
    def __init__(self):
        self.clientIds = []

class IBRequest(object):
    REALTIME_BARS = 1
    REALTIME_LEVEL2 = 2
    HISTORICAL_BARS = 3
    HISTORICAL_LEVEL2 = 4
    REALTIME_TICKS = 5
    HISTORICAL_TICKS = 6
    def __init__(self, tickerId, contract, reqType, api):
        self.tickerId = tickerId
        self.contract = contract
        self.reqType = reqType
        self.api = api
        self.live_request = True

        if self.reqType == IBRequest.HISTORICAL_BARS:
            self._historicalBarsBuffer = get_empty_bar_dataframe()
            self._historicalBarsCache = get_empty_bar_dataframe()
            self.barSize = '1m'
            self.live_request = False

        if self.reqType == IBRequest.REALTIME_LEVEL2:
            self.marketDepthData = MarketDepth(contract.symbol)
            self.lastMarketDepthUpdate = None
            self.live_request = True

    def __eq__(self, other):
        return (self.tickerId == other.tickerId) and (self.contract == other.contract) and (self.type == other.type)

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def symbol(self):
        if self.reqType == IBRequest.REALTIME_BARS:
            return self.contract
        else:
            return self.contract.symbol

    def cancel(self):
        if self.api:
            if self.reqType == IBRequest.HISTORICAL_BARS:
                self.api.cancelHistoricalData(self.tickerId)
            elif self.reqType == IBRequest.REALTIME_TICKS:
                self.api.cancelTickByTickData(self.tickerId)
            elif self.reqType == IBRequest.REALTIME_LEVEL2:
                self.api.cancelMktDepth(self.tickerId, True)
            elif self.reqType == IBRequest.REALTIME_BARS:
                self.api.cancelRealTimeBars(self.tickerId)
            self.api.activeRequests.remove(self)

    def addBarToBuffer(self, bar, timestamp):
        self._historicalBarsBuffer.loc[timestamp] = [bar.open, bar.high, bar.low, bar.close, bar.volume]

    def addToCache(self, dataframe):
        if dataframe is None:
            return
        self._historicalBarsCache = dataframe.combine_first(self._historicalBarsCache)

    def getBarsFromBuffer(self):
        return self._historicalBarsBuffer

    def getBarsFromCache(self):
        return self._historicalBarsCache

    def getBars(self):
        return self._historicalBarsBuffer.combine_first(self._historicalBarsCache)

class IBApiWrapper(BaseAPIWrapper):
    name = "IBKR"
    def __init__(self):
        self.ibapi = IBApi()
        self.onHistoricalBar = self.ibapi.signals.onHistoricalBar
        self.onHistoricalBarUpdate = self.ibapi.signals.onHistoricalBarUpdate
        self.onHistoricalBarEnd = self.ibapi.signals.onHistoricalBarEnd
        self.onHistoricalBarError = self.ibapi.signals.onHistoricalBarError
        self.onMarketDepthUpdate = self.ibapi.signals.onMarketDepthUpdate
        self.onTickLastUpdate = self.ibapi.signals.onTickLastUpdate
        self.activeRequests = self.ibapi.activeRequests
        self.getNewTickerId = self.ibapi.getNewTickerId
        
        self.ibapi.signals.onHistoricalBarEnd.connect(self.historicalBarsCallback)
        self.ibapi.signals.onHistoricalBarUpdate.connect(self.historicalBarsUpdateCallback)
        self.ibapi.signals.onMarketDepthUpdate.connect(self.marketDepthCallback)
        self.ibapi.signals.onTickLastUpdate.connect(self.tickDataCallback)

        self.listeningThread = IBThread(self.ibapi)

    def connect(self, host, port, clientId=0):
        clientIds = IBClientIDs()
        while clientId in clientIds.clientIds:
            clientId += 1
        clientIds.clientIds.append(clientId)
        self.ibapi.connect(host, port, clientId)
        self.listeningThread.start()
        log.debug("CLIENT IDS: {clientIds.clientIds}")

    def requestHistoricalBars(self, symbol, barSize='1m', startTime=None, endTime=None, live=False, callback=None, live_callback=None, error_callback=None):
        log.debug('HISTORICAL BARS REQUEST TOP')
        if live and self.hasRequest(symbol, IBRequest.HISTORICAL_BARS, barSize, live):
            log.debug('request exists already, skipping')
            return

        contract = Contract()
        contract.symbol = symbol.upper()
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"

        barSizeMapped = BAR_SIZE_REMAP[barSize]

        log.debug('historical bar request {}\n---start: {}\n---end: {}\n'.format(symbol, startTime, endTime))
        if live:
            durationStr = '60 S'
            endTimeStr = ""
        else:
            endTimeStr = endTime.strftime(TIME_FORMAT)
            durationStr = getIbkrDuration(startTime, endTime, barSize)

        if durationStr == '0 D' or durationStr == '0 S':
            bars = get_empty_bar_dataframe()
            self.onHistoricalBarEnd.emit(-1, symbol, bars, startTime, endTime, barSize, (callback))
            return

        tickerId = self.getNewTickerId()
        newRequest = IBRequest(tickerId, contract, IBRequest.HISTORICAL_BARS, api=self.ibapi)
        newRequest.barSize = barSize
        newRequest.callback = callback
        newRequest.live_request = live
        newRequest.live_callback = live_callback
        log.debug('-----\n---endTimeStr: {}\n---durationStr: {}\n'.format(endTimeStr, durationStr))
        self.ibapi.reqHistoricalData(tickerId, contract, endTimeStr, durationStr, barSizeMapped, "TRADES", 0, 1, live, [])
        self.activeRequests.append(newRequest)

    def requestMarketDepth(self, symbol, callback):
        contract = Contract()
        contract.symbol = symbol.upper()
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"

        tickerId = self.getNewTickerId()
        newRequest = IBRequest(tickerId, contract, IBRequest.REALTIME_LEVEL2, api=self.ibapi)
        newRequest.callback = callback

        self.ibapi.marketDepthData[tickerId] = MarketDepth(symbol)
        self.ibapi.requestSymbols[tickerId] = symbol.upper()
        self.ibapi.reqMktDepth(tickerId, contract, 100, True, [])
        self.activeRequests.append(newRequest)

    def requestTickData(self, symbol, callback):
        contract = Contract()
        contract.symbol = symbol.upper()
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"

        tickerId = self.getNewTickerId()
        newRequest = IBRequest(tickerId, contract, IBRequest.REALTIME_TICKS, api=self.ibapi)
        newRequest.callback = callback

        #self.ibapi.marketDepthData[tickerId] = MarketDepth(symbol)
        self.ibapi.requestSymbols[tickerId] = symbol.upper()
        self.ibapi.reqTickByTickData(tickerId, contract, "AllLast", 0, True)
        self.activeRequests.append(newRequest)

    @Slot(str, pd.DataFrame, pd.Timestamp, pd.Timestamp, str, tuple)
    def historicalBarsCallback(self, symbol, bars, startTime, endTime, barSize, callback):
        if callback is not None:
            callback(symbol, barSize, bars, startTime, endTime)

    @Slot(str, pd.DataFrame, str, tuple)
    def historicalBarsUpdateCallback(self, symbol, bar, barSize, callback):
        if callback is not None:
            callback(symbol, bar, barSize)

    def marketDepthCallback(self, symbol, marketDepthData, callback):
        if callback is not None:
            callback(symbol, marketDepthData)

    def tickDataCallback(self, symbol, time, price, size, callback):
        if callback is not None:
            callback(symbol, time, price, size)

    def hasRequest(self, symbol, requestType, barSize=None, live=False):
        for request in self.activeRequests[:]:
            if not request.reqType == requestType:
                continue
            if not request.symbol == symbol:
                continue
            if barSize and not request.barSize == barSize:
                continue
            if live != request.live_request:
                continue
            return True
        return False
    
    def getRequests(self, symbol, requestType, barSize=None, live=False):
        requests = []
        for request in self.activeRequests[:]:
            if not request.reqType == requestType:
                continue
            if not request.symbol == symbol:
                continue
            if barSize and not request.barSize == barSize:
                continue
            if live != request.live_request:
                continue
            requests.append(request)
        return requests

    def cancelRequests(self, symbol=None, requestType=None):
        for request in self.activeRequests[:]:
            if requestType and not request.reqType == requestType:
                continue
            if symbol and not request.symbol == symbol:
                continue
            request.cancel()

    def disconnect(self):
        self.listeningThread.quit()
        self.ibapi.disconnect()
