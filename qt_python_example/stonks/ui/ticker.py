from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *

from pyqtgraph.dockarea import DockArea, Dock
import pandas as pd

from .visualizers.log import GuiLog
from .visualizers.chart import Chart
from .visualizers.portfolio import PortfolioWidget
from .visualizers.algo_manager import AlgoManagerWidget
from .common import MyDock

from ..market_data.ibkr import IBApiWrapper, IBRequest

from ..config import Config

from ..utils import trading_offset_factory, get_market_hours, timer_func

import logging
mktDataLogger = logging.getLogger('Market Data')
ui_log = logging.getLogger('UI')

class StonkTickerNameInput(QWidget):
    def __init__(self, parent=None, ticker_name=None):
        QWidget.__init__(self, parent)

        self.layout = QHBoxLayout(self)
        print('STONKTICKERNAMEINPUT MARGINS '+str(self.layout.contentsMargins()))
        self.layout.setContentsMargins(9,0,0,0)
        self.setLayout(self.layout)

        #self.tickerLabel = QLabel("Ticker Symbol: ", self)
        #self.layout.addWidget(self.tickerLabel)
        self.tickerEdit = StonkTickerLineEdit(ticker_name, self)
        self.layout.addWidget(self.tickerEdit)
        self.mktPrice = 0
        self.mktPriceLabel = QLabel(self)
        self.mktPriceLabel.setStyleSheet("""
                                        QLabel{font-size:24px;}
                                        QLabel[move="up"]{color:#26A69A;}
                                        QLabel[move="down"]{color:#EF5350;}
                                        """)
        self.layout.addWidget(self.mktPriceLabel)
        self.layout.addStretch()

    @property
    def ticker_name(self):
        return self.tickerText.text()

    def updateMktPrice(self, newMktPrice):
        if newMktPrice < self.mktPrice:
            self.mktPriceLabel.setProperty("move", "down")
        elif newMktPrice > self.mktPrice:
            self.mktPriceLabel.setProperty("move", "up")
        self.mktPrice = newMktPrice
        self.mktPriceLabel.setText(' '+str(newMktPrice))

class StonkTickerLineEdit(QLineEdit):
    def __init__(self, ticker_name, parent=None):
        QLineEdit.__init__(self, ticker_name, parent)
        self.setProperty("tickerEdit", "yes")
        self.setMaximumWidth(100)

    def focusInEvent(self, e):
        QLineEdit.focusInEvent(self, e)
        QTimer.singleShot(0, self.selectAll)

class StonkTicker(QWidget):
    tickerChanged = Signal(str)
    def __init__(self, parent, ticker_name, api, brokerApi):
        QWidget.__init__(self, parent)
        self.ticker_name = ''
        self.bookDepthData = None

        self.config = Config()

        self.vl = QVBoxLayout(self)
        self.vl.setSpacing(0)
        self.setLayout(self.vl)

        self.api = api
        self.brokerApi = brokerApi

        self.tickerInput = StonkTickerNameInput(self, ticker_name)
        self.tickerInput.tickerEdit.returnPressed.connect(self.updateTicker)
        self.vl.addWidget(self.tickerInput)

        self.dockArea = DockArea(self)
        #elf.dockArea.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.vl.addWidget(self.dockArea)

        self.charts = []
        startBarSize = self.config.get_property('current_bar_size', '1m')
        self.mainChart = Chart(ticker_name, startBarSize, self, api)
        self.mainChart.barSizeChanged.connect(self.barSizeChanged)
        self.mainChart.dataRequired.connect(self.chartDataRequired)
        self.mainChart.bookDepthVisibilityChanged.connect(self.checkIfBookDepthNeeded)
        self.charts.append(self.mainChart)
        self.mainChartDock = MyDock("Chart", widget=self.mainChart, autoOrientation=False)
        self.dockArea.addDock(self.mainChartDock)
        #self.vl.addWidget(self.mainChart)

        self.testLog = GuiLog(ticker_name, self)
        self.testLogDock = MyDock("Log", widget=self.testLog, autoOrientation=False)
        self.dockArea.addDock(self.testLogDock)
        #self.vl.addWidget(self.testLog)

        self.portfolioWidget = PortfolioWidget(self, self.brokerApi)
        self.portfolioDock = MyDock("Portfolio", widget=self.portfolioWidget, autoOrientation=False)
        self.dockArea.addDock(self.portfolioDock)

        self.algoManagerWidget = AlgoManagerWidget(self, self.brokerApi)
        self.algoManagerDock = MyDock("Algo Manager", widget=self.algoManagerWidget, autoOrientation=False)
        self.dockArea.addDock(self.algoManagerDock)

        self.dockState = self.config.get_property("layout_dock_state", None)
        if self.dockState:
            self.dockArea.restoreState(self.dockState, missing='create')

        self.layoutLocked = self.config.get_property("layout_locked", True)
        self.lockLayoutBtn = QPushButton()
        self.lockLayoutBtn.setMaximumWidth(150)
        self.lockLayoutBtn.clicked.connect(self.toggleLayoutLock)
        self.vl.addWidget(self.lockLayoutBtn)
        self.updateLayoutLockStatus()

        self.statusBar = QStatusBar()
        self.statusBar.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.statusBar.showMessage("Idle.")
        self.vl.addWidget(self.statusBar)

        #self.api.onHistoricalBarError.connect(self.historicalBarError)

        self.twsTimezone = self.config.get_property("timezone_tws", "US/Pacific")

        if ticker_name:
            self.setTicker(ticker_name)

        for chart in self.charts:
            chart.loadIndicators()

    def setTicker(self, ticker_name):
        if self.ticker_name != ticker_name:
            self.statusBar.showMessage(f'Loading ticker f{ticker_name}...')
            QGuiApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
            self.bookDepthData = None
            self.api.cancelSubscriptions(self.ticker_name)
            self.ticker_name = ticker_name
            self.mainChart.setTicker(ticker_name)

            market_hours = get_market_hours(self.twsTimezone)
            tradingOffset = trading_offset_factory(barSize='1m', start=market_hours[0], end=market_hours[-1])
            endTime = tradingOffset.rollback(pd.Timestamp.now().tz_localize(self.twsTimezone))

            barSizesRequested = []
            for chart in self.charts:
                if not chart.barSize in barSizesRequested:
                    self.api.requestHistoricalBars(ticker_name,
                                                    chart.barSize,
                                                    callback=self.historicalBarEnd,
                                                    error_callback=self.historicalBarError)
                    self.api.subscribeToLiveBars(ticker_name, chart.barSize, self.historicalBarUpdate)
                    barSizesRequested.append(chart.barSize)
            self.api.subscribeToTickData(ticker_name, callback=self.tickLastUpdate)
            self.checkIfBookDepthNeeded()
            self.config.set_property("currentTicker", ticker_name)
            self.tickerInput.tickerEdit.setText(ticker_name)
            self.tickerChanged.emit(ticker_name)

    def disconnect(self):
        self.api.disconnect()

    def updateTicker(self):
        new_ticker_name = str(self.tickerInput.tickerEdit.text()).upper()
        self.tickerInput.tickerEdit.clearFocus()
        self.setTicker(new_ticker_name)

    def historicalBarUpdate(self, symbol, bar, barSize):
        mktDataLogger.info("historical bar update: {} {} {}".format(symbol, barSize, bar))
        #self.tickerInput.updateMktPrice(bar.close)
        self.mainChart.historicalBarUpdate(symbol, bar)

    def historicalBarEnd(self, symbol, barSize, bars, startTimeStamp, endTimeStamp):
        mktDataLogger.info('historicalDataEnd {} {} {}'.format(len(bars), symbol, barSize))
        mktDataLogger.info(str(bars))
        self.statusBar.showMessage(f'Received data for {symbol} - {barSize}.')
        QGuiApplication.restoreOverrideCursor()
        for chart in self.charts:
            if chart.barSize == barSize:
                chart.historicalDataReceived(symbol, bars, startTimeStamp, endTimeStamp)

    def historicalBarError(self, symbol, barSize, errorCode, errorMsg):
        self.statusBar.showMessage("Error ({}) while requesting historical data: {}".format(errorCode, errorMsg))
        QGuiApplication.restoreOverrideCursor()
        #ok = QMessageBox.critical(self, "Error", "Error ({}) while requesting historical data: {}".format(errorCode, errorMsg), QMessageBox.Ok)
        for chart in self.charts:
            if chart.ticker_name == symbol and chart.barSize == barSize:
                chart.dataFillRequestActive = False

    def marketDepthUpdate(self, symbol, marketDepthData):
        #print("UpdateMktDepthL2, {} {}".format(reqId, marketDepthData))
        self.mainChart.marketDepthUpdate(marketDepthData)

    def tickLastUpdate(self, symbol, time, price, size):
        mktDataLogger.info("tick update {} {} {} {}".format(symbol, time, price, size))
        self.tickerInput.updateMktPrice(price)
        self.mainChart.updateMktPrice(newMktPrice=price)

    @Slot(str, Chart)
    def barSizeChanged(self, newBarSize, chart):
        ui_log.debug(f'barsizechanged {newBarSize} {chart}')
        self.config.set_property('current_bar_size', newBarSize)
        chart.clearBars()
        self.api.cancelSubscriptions(self.ticker_name, 'historicalBars')
        self.statusBar.showMessage(f'Requesting data for {self.ticker_name} - {newBarSize}...')
        QGuiApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        self.api.requestHistoricalBars(self.ticker_name, newBarSize, callback=self.historicalBarEnd)
        self.api.subscribeToLiveBars(self.ticker_name, newBarSize, callback=self.historicalBarUpdate)

    #@Slot(str, str, object, object, bool)
    def chartDataRequired(self, symbol, barSize, startTimeStamp, endTimeStamp=None, live=False):
        self.statusBar.showMessage(f'Requesting data for {symbol} - {barSize}...')
        QGuiApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        self.api.requestHistoricalBars(symbol, barSize, startTimeStamp, endTimeStamp, callback=self.historicalBarEnd)

    def checkIfBookDepthNeeded(self):
        needed = any([chart.bookDepthEnabled for chart in self.charts])
        if needed and not self.api.isSubscriptionActive(self.ticker_name, 'marketDepth'):
            self.api.subscribeToMarketDepth(self.ticker_name, callback=self.marketDepthUpdate)
        elif not needed and self.api.isSubscriptionActive(self.ticker_name, 'marketDepth'):
            self.api.cancelSubscriptions(self.ticker_name, 'marketDepth')

    def toggleLayoutLock(self):
        self.layoutLocked = not self.layoutLocked
        self.config.set_property("layout_locked", self.layoutLocked)
        self.updateLayoutLockStatus()
        if self.layoutLocked:
            self.config.set_property("layout_dock_state", self.dockArea.saveState())

    def updateLayoutLockStatus(self):
        self.lockLayoutBtn.setText("Unlock Layout" if self.layoutLocked else "Lock Layout")
        for dockName in self.dockArea.docks:
            if self.layoutLocked:
                self.dockArea.docks[dockName].hideTitleBar()
                container = self.dockArea.docks[dockName].container()
                if not container is None:
                    container.setHandleWidth(0)
                    for i in range(container.count()):
                        if i == 0:
                            continue
                        handle = container.handle(i)
                        handle.setEnabled(False)
            else:
                self.dockArea.docks[dockName].setOrientation('horizontal', force=True)
                self.dockArea.docks[dockName].showTitleBar()
                container = self.dockArea.docks[dockName].container()
                if not container is None:
                    container.setHandleWidth(5)
                    for i in range(container.count()):
                        if i == 0:
                            continue
                        handle = container.handle(i)
                        handle.setEnabled(True)
