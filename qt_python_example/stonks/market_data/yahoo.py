import yfinance as yf
import pandas as pd

from .base import *

from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *

from ..config import Config
from ..utils import trading_offset_factory, get_market_hours, singleton

class YahooSignals(QObject):
    onHistoricalBarEnd = Signal(str, pd.DataFrame, pd.Timestamp, pd.Timestamp, str, tuple)

class YahooAPIWrapper(BaseAPIWrapper):
    name = "Yahoo Finance"
    def __init__(self):
        pass

    @to_thread
    def requestHistoricalBars(self, symbols, barSize='1m', startTime=None, endTime=None, callback=None, error_callback=None):
        symbols_str = ' '.join(symbols)
        bars = yf.download(symbols_str,
                            start=startTime,
                            end=endTime,
                            interval=barSize,
                            prepost=True)

        self.onHistoricalBarEnd.emit(symbols_str, bars, startTime, endTime, barSize, (callback))

    def historicalBarsCallback(self, symbol, bars, startTime, endTime, barSize, callback):
        if callback is not None:
            callback(symbol, bars, startTime, endTime, barSize)
