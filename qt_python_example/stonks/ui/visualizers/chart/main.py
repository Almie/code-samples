from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from .book_depth import BookDepthGrid, BookDepthItem
from .indicators import IndicatorComboBox, IndicatorAddDialog, IndicatorItem

import pyqtgraph as pg
from pyqtgraph.dockarea import DockArea, Dock
import numpy as np
import pandas as pd
import math
from decimal import Decimal, getcontext

from datetime import datetime, timedelta
from time import mktime, time

import os
import logging
ui_log = logging.getLogger('UI')

from ..base import BaseVisualizer
from ....market_data.types import MarketDepth, get_empty_bar_dataframe
from ....indicators import Indicator, available_indicators, IndicatorStyleOptions
from ....config import Config
from ....utils import *

COLOR_GREEN = "#26A69A"
COLOR_GREEN_HOVER = "#76ded4"
COLOR_RED = "#EF5350"
COLOR_RED_HOVER = "#ff8c8a"
COLOR_BG = "#151924"

#Set Decimal Precision
getcontext().prec = 6

pg.setConfigOptions(antialias=False)
pg.setConfigOption('foreground', '#C1C1C1')
pg.setConfigOption('background', COLOR_BG)

class Chart(BaseVisualizer):
    name = "Chart"
    icon = ':/icons/chart.png'
    dataRequired = Signal(str, str, pd.Timestamp, pd.Timestamp, bool)
    bookDepthVisibilityChanged = Signal(bool)
    def __init__(self, ticker_name, barSize='1m', parent=None, api=None):
        BaseVisualizer.__init__(self)
        self.ticker_name = ticker_name
        self.api = api
        self.times = []
        self._barSize = barSize
        market_hours = get_market_hours()
        self._offset = trading_offset_factory(barSize, market_hours[0], market_hours[-1])

        self.hl = QHBoxLayout(self)
        self.hl.setSpacing(0)
        self.setLayout(self.hl)

        self.dockArea = DockArea(self)
        self.dockArea.allowedAreas = []
        self.hl.addWidget(self.dockArea)

        self.config = Config()

        self.chartWidget = ChartWidget(self, self.config)
        self.chartWidget.setLimitsForBarSize(barSize)
        self.dataFillRequestActive = False
        self.chartWidget.getPlotItem().sigXRangeChanged.connect(self.rangeChanged)
        self.chartWidget.rangeChangedQueued = False
        self.chartWidget.mouseReleased.connect(self.onMouseReleased)

        self.bars = None
        self.marketDepthData = None
        self.indicators = []

        self.chartOptions = ChartOptions(self.chartWidget, self)
        self.chartOptions.barSizeCombo.setCurrentText(barSize)
        self.barSizeChanged = self.chartOptions.barSizeChanged
        self.chartOptions.showOptionsChanged.connect(self.onShowOptionChanged)
        self.chartOptions.indicatorOptions.addIndicator.connect(self.addIndicatorFromInput)
        self.chartOptions.indicatorOptions.toggleVisIndicator.connect(self.toggleVisIndicator)
        self.chartOptions.indicatorOptions.editIndicator.connect(self.editIndicator)
        self.chartOptions.indicatorOptions.deleteIndicator.connect(self.deleteIndicator)

        self.chartWidgetDock = Dock("Main", widget=self.chartWidget, size=(850,100), autoOrientation=False, hideTitle=True)
        self.chartWidgetDock.allowedAreas = []
        self.dockArea.addDock(self.chartWidgetDock, 'left')

        self.extraPanes = []

        self.tapeWidget = pg.PlotWidget()
        self.tapeWidget.setMinimumWidth(150)
        tapePlotItem = self.tapeWidget.getPlotItem()
        tapePlotItem.registerPlot('tape')
        tapePlotItem.hideAxis('bottom')
        tapePlotItem.setLimits(xMin=-1, yMin=0, minXRange=2, minYRange=0.001)
        tapePlotItem.setYLink(self.chartWidget.getPlotItem())
        tapePlotItem.hideButtons()
        #self.tapeLockBtn = pg.ButtonItem(os.path.join(os.getcwd(), "icons", "lock.png"), 14, tapePlotItem)
        #self.tapeLockBtn.setPos(0, tapePlotItem.size().height()-15)
        self.tapeAxisY = PriceTapeAxis(orientation='left')
        self.tapeAxisY.attachToPlotItem(tapePlotItem)
        tapePlotItem.hideAxis('left')
        self.bookDepthGrid = BookDepthGrid()
        self.bookDepthItem = BookDepthItem()
        self.tapeWidget.addItem(self.bookDepthGrid)

        self.bookDepthBidLine = None
        self.bookDepthAskLine = None
        self.bookDepthEnabled = self.config.get_property("showBookDepth", True)

        self.tapeWidgetDock = Dock("Tape", widget=self.tapeWidget, size=(1,1), autoOrientation=False, hideTitle=True)
        self.tapeWidgetDock.allowedAreas = []
        self.dockArea.addDock(self.tapeWidgetDock, 'right')

        if not self.bookDepthEnabled:
            self.tapeWidget.hide()
            self.tapeWidgetDock.hide()

        self.setTicker(ticker_name)

    def setTicker(self, new_ticker_name):
        data = get_empty_bar_dataframe()
        if not self.chartWidget.candlestickItem is None:
            self.chartWidget.removeItem(self.chartWidget.candlestickItem)
        self.chartWidget.candlestickItem = CandlestickItem(data, self._offset)
        self.chartWidget.addItem(self.chartWidget.candlestickItem)
        self.chartWidget.addItem(self.chartWidget.candlestickItem.hoverItem)
        self.chartWidget.volumeBarsItem.setData(data)
        #self.chartWidget.candlestickItem.setData(data)

        self.clearBars()
        self.marketDepthData = MarketDepth(new_ticker_name)
        self.tapeWidget.clear()
        self.bookDepthItem.clear()

        self.ticker_name = new_ticker_name

    def clearBars(self):
        self.bars = None
        self.dataFillRequestActive = False

    @property
    def barSize(self):
        return self._barSize

    @barSize.setter
    def barSize(self, newBarSize):
        self._barSize = newBarSize
        market_hours = get_market_hours()
        self._offset = trading_offset_factory(newBarSize, market_hours[0], market_hours[-1])
        self.chartWidget.setLimitsForBarSize(newBarSize)
        self.chartWidget.candlestickItem.offset = self._offset

    def onMouseReleased(self):
        if self.chartWidget.rangeChangedQueued:
            self.rangeChanged(self.chartWidget.getPlotItem(), self.chartWidget.getPlotItem().viewRange()[0])

    def rangeChanged(self, viewBox, range):
        if self.bars is None:
            return
        if self.dataFillRequestActive:
            return
        if self.chartWidget.mousePressed:
            self.chartWidget.rangeChangedQueued = True
            return
        self.chartWidget.rangeChangedQueued = False
        timezone = self.config.get_property("timezone_tws", "US/Pacific")
        startTimeStamp = pd.Timestamp.fromtimestamp(range[0]).round(freq='s').tz_localize(timezone)
        #startTimeStamp = self._offset.fromtimestamp(range[0]).round(freq='s').tz_localize(timezone)
        barsStart = self.bars.index[0].tz_convert(timezone)
        if startTimeStamp >= barsStart:
            return
        ui_log.debug('RANGE START: {}, BARS START: {}'.format(startTimeStamp, barsStart))
        self.dataFillRequestActive = True
        self.dataRequired.emit(self.ticker_name, self.barSize, startTimeStamp, barsStart, False)

    def addIndicator(self, indicator, name, styleOptions=None, **options):
        newIndicator = Indicator(indicator, name, styleOptions, **options)
        newIndicatorItem = IndicatorItem(newIndicator)
        if newIndicator.relativeDataRequired:
            newIndicator.setApi(self.api)
            newIndicator.dataUpdated.connect(self.updateIndicatorWrapper(newIndicatorItem))
        self.indicators.append(newIndicatorItem)
        if styleOptions and styleOptions.visible == False:
            newIndicatorItem.setVisible(False)
        return newIndicatorItem

    def addIndicatorFromInput(self):
        newIndicator = IndicatorAddDialog.getNewIndicator(self)
        if newIndicator:
            newIndicatorItem = IndicatorItem(newIndicator)
            if newIndicator.relativeDataRequired:
                newIndicator.setApi(self.api)
                newIndicator.dataUpdated.connect(self.updateIndicatorWrapper(newIndicatorItem))
                """
                timezone = self.config.get_property("timezone_tws", "US/Pacific")
                barsStart = self.bars.index[0].tz_convert(timezone)
                for symbol in newIndicator.relativeSymbolsRequired():
                    self.dataRequired.emit(symbol, self.barSize, barsStart, None, True)
                """
            if self.bars is not None:
                newIndicatorItem.calculate(self.bars, self.barSize, self._offset)
            chart = self.getIndicatorChart(newIndicatorItem)
            newIndicatorItem.addToChart(chart)
            self.indicators.append(newIndicatorItem)
            self.saveIndicators()

    def addChartPane(self, name):
        newChartPane = ChartPane(self, name, self.config)
        newPlotItem = newChartPane.getPlotItem()
        newPlotItem.registerPlot(name)
        newPlotItem.hideAxis('bottom')
        newPlotItem.hideAxis('left')
        newPlotItem.showAxis('right')
        newPlotItem.setXLink(self.chartWidget.getPlotItem())
        self.extraPanes.append(newChartPane)
        newDock = Dock(name, widget=newChartPane, size=(850, 1), autoOrientation=False, hideTitle=True)
        newDock.allowedAreas = []
        self.dockArea.addDock(newDock, 'bottom', self.chartWidgetDock)
        return newChartPane

    def getChartPane(self, name):
        for chart in self.extraPanes:
            if chart.name == name:
                return chart
        return None

    def removeChartPane(self, name):
        self.dockArea.docks[name].close()
        for chartPane in self.extraPanes[:]:
            if chartPane.name == name:
                self.extraPanes.remove(chartPane)
                chartPane.deleteLater()

    def getIndicatorChart(self, indicatorItem):
        if indicatorItem.indicator.plotLocation == "main":
            return self.chartWidget
        else:
            chartPane = self.getChartPane(indicatorItem.indicator.plotLocation)
            ui_log.debug(f'GOT CHART PANE FOR {indicatorItem.indicator.plotLocation}, {indicatorItem.indicator.name}')
            if not chartPane:
                ui_log.debug('oops it\'s None, creating...')
                chartPane = self.addChartPane(indicatorItem.indicator.plotLocation)
            return chartPane

    def toggleVisIndicator(self, indicatorItem, state):
        chart = self.getChartPane(indicatorItem.indicator.plotLocation)
        if state and not chart:
            chart = self.addChartPane(indicatorItem.indicator.plotLocation)
        if state and not chart.isVisible():
            chart.setVisible(True)
            self.dockArea.docks[indicatorItem.indicator.plotLocation].show()
            self.dockArea.docks[indicatorItem.indicator.plotLocation].setStretch(y=1)
        indicatorItem.indicator.styleOptions.visible = state
        indicatorItem.setVisible(state)
        if chart and not any([item.isVisible() for item in chart.listDataItems()]):
            #self.removeChartPane(indicatorItem.indicator.plotLocation)
            chart.setVisible(False)
            self.dockArea.docks[indicatorItem.indicator.plotLocation].setStretch(y=0)
            self.dockArea.docks[indicatorItem.indicator.plotLocation].hide()
        self.saveIndicators()

    def editIndicator(self, indicatorItem):
        index = self.indicators.index(indicatorItem)
        editedIndicator = IndicatorAddDialog.editIndicator(indicatorItem.indicator, self)
        if editedIndicator.relativeDataRequired:
            editedIndicator.setApi(self.api)
            editedIndicator.dataUpdated.connect(self.updateIndicatorWrapper(self.indicators[index]))
        if editedIndicator:
            self.indicators[index].editIndicator(editedIndicator)
            if self.bars is not None:
                self.indicators[index].calculate(self.bars, self.barSize, self._offset)
            self.saveIndicators()

    def deleteIndicator(self, indicatorItem):
        result = QMessageBox.question(self, 'Deleting "{}"'.format(indicatorItem.indicator.name), 'Are you sure you want to delete "{}"?'.format(indicatorItem.indicator.name), QMessageBox.Yes | QMessageBox.No)
        if result == QMessageBox.Yes:
            if indicatorItem.indicator.relativeDataRequired:
                indicatorItem.indicator.cancelSubscriptions()
            chart = self.getIndicatorChart(indicatorItem)
            indicatorItem.removeFromChart(chart)
            indexToRemove = self.indicators.index(indicatorItem)
            self.indicators.pop(indexToRemove)
            self.chartOptions.indicatorOptions.updateIndicatorList()
            self.saveIndicators()

            if indicatorItem.indicator.plotLocation != "main" and len(chart.listDataItems()) == 0:
                self.removeChartPane(indicatorItem.indicator.plotLocation)

    def updateIndicatorWrapper(self, indicatorItem):
        def updateIndicatorWrapped():
            if self.bars is not None:
                indicatorItem.calculate(self.bars, self.barSize, self._offset)
        return updateIndicatorWrapped

    def updateIndicator(self, indicatorItem):
        if self.bars is not None:
            indicatorItem.calculate(self.bars, self.barSize, self._offset)

    def updateAllIndicators(self):
        if self.bars is None:
            return
        for indicatorItem in self.indicators:
            indicatorItem.calculate(self.bars, self.barSize, self._offset)

    def saveIndicators(self):
        indicatorsObj = [indicatorItem.indicator.serialize() for indicatorItem in self.indicators]
        self.config.set_property("indicators", indicatorsObj)

    def loadIndicators(self):
        indicatorsObj = self.config.get_property("indicators", [])
        for indicatorObj in indicatorsObj:
            styleOptions = IndicatorStyleOptions.from_json(indicatorObj['styleOptions'])
            self.addIndicator(indicatorObj['indicatorType'], indicatorObj['name'], styleOptions, **indicatorObj['options'])
        for chart in self.extraPanes:
            if chart and not any([item.isVisible() for item in chart.listDataItems()]):
                chart.setVisible(False)
                self.dockArea.docks[chart.name].setStretch(y=0)

    def updateMktPrice(self, newMktPrice=None, newLine=False):
        if self.bars is None:
            return
        if not newMktPrice:
            newMktPrice = self.bars.iloc[-1]['close']
        else:
            self.bars.at[self.bars.index[-1], 'close'] = newMktPrice
            if newMktPrice > self.bars.iloc[-1]['high']:
                self.bars.at[self.bars.index[-1], 'high'] = newMktPrice
            if newMktPrice < self.bars.iloc[-1]['low']:
                self.bars.at[self.bars.index[-1], 'low'] = newMktPrice
            self.chartWidget.candlestickItem.setLastBar(self.bars.iloc[-1])
        if self.bars.iloc[-1]['open'] < self.bars.iloc[-1]['close']:
            color = QColor(COLOR_GREEN)
        else:
            color = QColor(COLOR_RED)
        self.chartWidget.updateMktPrice(newMktPrice, color)

    def onShowOptionChanged(self, option, value):
        if option == "Book Depth":
            if value:
                self.tapeWidgetDock.show()
                self.tapeWidget.show()
            else:
                self.tapeWidget.hide()
                self.tapeWidgetDock.hide()
            self.bookDepthEnabled = value
            self.config.set_property("showBookDepth", value)
            self.bookDepthVisibilityChanged.emit(value)
        elif option == "Grid":
            self.chartWidget.gridItem.setVisible(value)
            self.config.set_property("showGrid", value)
        elif option == "Crosshair":
            self.chartWidget.crosshair_h.setVisible(value)
            self.chartWidget.crosshair_v.setVisible(value)
            self.config.set_property("crosshair_enable", value)
        elif option == "Pre/Post-Market Highlight":
            self.chartWidget.prePostMarketItem.setVisible(value)
            for chartPane in self.extraPanes:
                chartPane.prePostMarketItem.setVisible(value)
            self.config.set_property("pre_post_market_highlight", value)

    def historicalDataReceived(self, symbol, bars, startTimeStamp, endTimeStamp):
        ui_log.debug(f'HISTORICAL DATA RECEIVED, {symbol}, {startTimeStamp}, {endTimeStamp}')
        if not symbol == self.ticker_name:
            return
        if bars.empty:
            return
        adjustRange = False
        if self.bars is not None:
            self.bars = bars.combine_first(self.bars)
        else:
            self.bars = bars
            adjustRange = True

        self.dataFillRequestActive = False
        #self.chartWidget.clear()
        #self.chartWidget.candlestickItem = CandlestickItem(self.bars)
        self.chartWidget.candlestickItem.setData(self.bars)
        self.chartWidget.volumeBarsItem.setData(self.bars)
        #self.chartWidget.addItem(self.chartWidget.candlestickItem)
        if adjustRange:
            self.chartWidget.getPlotItem().blockSignals(True)
            freq = infer_freq(self.bars).total_seconds()
            endTimeStamp = self.bars.index[-1]
            rangeLookback = max(-self.bars.index.size, -120)
            startTimeStamp = self.bars.index[rangeLookback]
            ymin = min([bar.low for bar in sorted(self.bars.itertuples(), key=lambda k:k.Index.timestamp(), reverse=True)[rangeLookback:]])
            ymax = max([bar.high for bar in sorted(self.bars.itertuples(), key=lambda k:k.Index.timestamp(), reverse=True)[rangeLookback:]])
            self.chartWidget.setRange(xRange=(startTimeStamp.timestamp(), endTimeStamp.timestamp()+freq*50), yRange=(ymin,ymax))
            #self.chartWidget.setLimits(xMax=endTimeStamp.timestamp()+freq*50)
            self.chartWidget.getPlotItem().blockSignals(False)
        maxVolumeRange = self.bars["volume"].max()*5
        self.chartWidget.volumeViewBox.setLimits(minYRange=maxVolumeRange, yMin=0, yMax=maxVolumeRange)
        #self.chartWidget.getPlotItem().showGrid(x=True,y=True, alpha=0.3)

        for i, indicatorItem in enumerate(self.indicators):
            chart = self.getIndicatorChart(indicatorItem)
            indicatorItem.removeFromChart(chart)
            visState = indicatorItem.isVisible()
            indicatorItem.calculate(self.bars, self.barSize, self._offset)
            indicatorItem.addToChart(chart)
            if visState and not chart.isVisible():
                chart.setVisible(True)
                self.dockArea.docks[indicatorItem.indicator.plotLocation].show()
                self.dockArea.docks[indicatorItem.indicator.plotLocation].setStretch(y=1)
            if chart and not any([item.isVisible() for item in chart.listDataItems()]):
                chart.setVisible(False)
                self.dockArea.docks[indicatorItem.indicator.plotLocation].setStretch(y=0)
                self.dockArea.docks[indicatorItem.indicator.plotLocation].hide()
            #indicatorItem = self.chartWidget.getPlotItem().plot([i.timestamp() for i in indicatorData.index], list(indicatorData))
            #self.chartWidget.indicatorItems.append(indicatorItem)

        #if self.config.get_property("crosshair_enable", True):
            #self.chartWidget.addItem(self.chartWidget.crosshair_v, ignoreBounds=True)
            #self.chartWidget.addItem(self.chartWidget.crosshair_h, ignoreBounds=True)

        #self.chartWidget.addItem(self.chartWidget.gridItem)

        self.updateMktPrice()
        #Check if we need to request additional data, in case user moved view while request in progress
        #self.rangeChanged(self.chartWidget.getPlotItem().getViewBox(), self.chartWidget.getPlotItem().viewRange()[0])

    def historicalBarUpdate(self, symbol, bar):
        if not symbol == self.ticker_name:
            return
        if self.bars is None:
            return
        isNewBar = not bar.index[-1] == self.bars.index[-1]
        self.bars = bar.combine_first(self.bars)
        self.chartWidget.candlestickItem.setData(self.bars)
        self.chartWidget.volumeBarsItem.setData(self.bars)
        self.updateMktPrice()

        self.updateAllIndicators()
        
        #offset view range on new bar

        if isNewBar:
            freq = infer_freq(self.bars).total_seconds()
            oldRange = self.chartWidget.viewRange()
            #oldXMax = self.chartWidget.getViewBox().state['limits']['xLimits'][1]
            #self.chartWidget.setLimits(xMax=oldXMax+freq)
            self.chartWidget.setRange(xRange=(oldRange[0][0]+freq, oldRange[0][1]+freq), padding=0)
            newRange = self.chartWidget.viewRange()

        #self.chartWidget.update()
        #QApplication.processEvents()

    def marketDepthUpdate(self, marketDepthData):
        self.marketDepthData = marketDepthData
        if len(self.marketDepthData.dataframe) == 0:
            return

        self.tapeWidget.clear()
        bookData = self.marketDepthData.bookData()
        bidData = bookData['size_bid'].dropna()*(-1)
        askData = bookData['size_ask'].dropna()
        minBid = 0
        maxAsk = 0
        if len(bidData) > 0:
            if self.bookDepthBidLine is None:
                self.bookDepthBidLine = self.tapeWidget.getPlotItem().plot(list([float(p) for p in bidData.index]), list(bidData))
            else:
                self.bookDepthBidLine.setData(list([float(p) for p in bidData.index]), list(bidData))
            minBid = min(bidData)
        if len(askData) > 0:
            if self.bookDepthAskLine is None:
                self.bookDepthAskLine = self.tapeWidget.getPlotItem().plot(list([float(p) for p in askData.index]), list(askData))
            else:
                self.bookDepthAskLine.setData(list([float(p) for p in askData.index]), list(askData))
            maxAsk = max(askData)
        graphSize = max(abs(minBid), maxAsk)
        self.tapeWidget.getPlotItem().setLimits(xMin=-graphSize, xMax=graphSize)
        self.tapeWidget.getPlotItem().setXRange(-graphSize,graphSize)
        #print(self.marketDepthData.bookData())

        self.bookDepthGrid.setBookData(self.marketDepthData)
        self.tapeWidget.addItem(self.bookDepthGrid)
        self.bookDepthItem.setBookData(self.marketDepthData)
        self.tapeWidget.addItem(self.bookDepthItem)
        #self.axisY.setBookData(self.marketDepthData.bookData())

        #self.tapeWidget.addItem(self.tapeLockBtn)
        #self.tapeLockBtn.setPos(0, self.tapeWidget.getPlotItem().size().height()-15)

        self.tapeWidget.update()
        QApplication.processEvents()

class ChartWidget(pg.PlotWidget):
    mouseReleased = Signal()
    def __init__(self, parent=None, config=Config()):
        pg.PlotWidget.__init__(self)
        self.parentWidget = parent
        self.config = config
        self.twsTimezone = self.config.get_property("twsTimezone", "US/Pacific")

        #self.getViewBox().setBackgroundColor(QColor(COLOR_BG))
        plotItem = self.getPlotItem()
        plotItem.showAxis('right')
        plotItem.hideAxis('left')
        plotItem.registerPlot('chart')
        plotItem.showGrid(x=True,y=True, alpha=0.3)
        plotItem.setLimits(xMin=0, yMin=0, minXRange=15, minYRange=0.001)
        plotItem.hideButtons()
        self.mktPricePen = pg.mkPen(COLOR_GREEN)
        self.mktPricePen.setStyle(Qt.DotLine)
        self.mktPrice = 0
        self.mktPriceLine = pg.InfiniteLine(self.mktPrice, 0, self.mktPricePen, movable=False, label="{value}", labelOpts={"position":1})
        self.mktPriceLine.addMarker('v', 1, 15)
        self.mktPriceLine.label.fill = pg.mkBrush(self.mktPricePen.color())
        self.mktPriceLine.label.anchors = [(1, 0.5), (1, 0.5)]
        self.addItem(self.mktPriceLine)
        self.candlestickItem = None

        self.axisX = DateAxisItem(orientation='bottom', offset=self.parentWidget._offset, timezone=self.twsTimezone)
        self.axisX.attachToPlotItem(plotItem)
        self.axisY = PriceTapeAxis(orientation='right')
        self.axisY.attachToPlotItem(plotItem)

        #Volume Axis
        self.volumeViewBox = pg.ViewBox()
        self.volumeAxis = pg.AxisItem('right')
        plotItem.layout.addItem(self.volumeAxis, 2, 3)
        plotItem.scene().addItem(self.volumeViewBox)
        self.volumeAxis.linkToView(self.volumeViewBox)
        self.volumeViewBox.setXLink(plotItem)
        self.volumeAxis.setZValue(-10000)
        self.volumeAxis.setVisible(False)

        self.volumeBarsItem = VolumeBars(get_empty_bar_dataframe(), self.parentWidget._offset)
        self.volumeViewBox.addItem(self.volumeBarsItem)
        self.volumeViewBox.addItem(self.volumeBarsItem.hoverItem)


        self.gridItem = pg.GridItem(textPen=None)
        self.gridItem.setTickSpacing(x=[86400, 3600, 60], y=[1.0,0.1,0.01,0.001])
        self.addItem(self.gridItem)
        self.gridItem.setVisible(self.config.get_property("showGrid", True))

        #Crosshair
        self.crossHairPen = pg.mkPen("#666666")
        self.crossHairPen.setStyle(Qt.DotLine)
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=self.crossHairPen, label="{value}", labelOpts={"position":0})
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=self.crossHairPen, label="{value}", labelOpts={"position":1})
        self.crosshair_v.label.fill = pg.mkBrush(self.crossHairPen.color())
        self.crosshair_v.label.anchors = [(0.5, 1), (0.5, 1)]
        self.crosshair_h.label.fill = pg.mkBrush(self.crossHairPen.color())
        self.crosshair_h.label.anchors = [(1, 0.5), (1, 0.5)]
        self.addItem(self.crosshair_v, ignoreBounds=True)
        self.addItem(self.crosshair_h, ignoreBounds=True)
        crosshairVisible = self.config.get_property("crosshair_enable", True)
        self.crosshair_v.setVisible(crosshairVisible)
        self.crosshair_h.setVisible(crosshairVisible)

        self.prePostMarketItem = PrePostMarketItem(self.twsTimezone, self.parentWidget._offset)
        self.addItem(self.prePostMarketItem)
        self.prePostMarketItem.setVisible(self.config.get_property("pre_post_market_highlight", True))

        self.setMouseTracking(True)
        self.mousePressed = False

        plotItem.vb.sigResized.connect(self.updateViewBoxes)

    def paintEvent(self, e):
        pg.PlotWidget.paintEvent(self, e)

    def updateViewBoxes(self):
        self.volumeViewBox.setGeometry(self.getPlotItem().vb.sceneBoundingRect())
        self.volumeViewBox.linkedViewChanged(self.getPlotItem().vb, self.volumeViewBox.XAxis)

    def setLimitsForBarSize(self, barSize):
        plotItem = self.getPlotItem()
        market_hours = get_market_hours(self.twsTimezone)
        offset = trading_offset_factory(barSize, market_hours[0], market_hours[-1])

        currentTime = pd.Timestamp.now()
        startTime = currentTime - 10000*offset
        freq = barSize.replace('m', 'T')
        minRange = (pd.Timedelta(freq)*10).total_seconds()
        maxRange = (currentTime - startTime).total_seconds()
        plotItem.setLimits(minXRange=minRange, maxXRange=maxRange, xMin=startTime.timestamp())

    def mousePressEvent(self, e):
        ui_log.debug(f'MOUSE PRESS EVENT {e}')
        self.mousePressed = True
        pg.PlotWidget.mousePressEvent(self, e)

    def mouseReleaseEvent(self, e):
        ui_log.debug(f'MOUSE RELEASE EVENT {e}')
        self.mousePressed = False
        self.mouseReleased.emit()
        pg.PlotWidget.mouseReleaseEvent(self, e)

    def mouseMoveEvent(self, e):
        pos = e.pos()
        if self.sceneBoundingRect().contains(pos):
            mousePoint = self.getPlotItem().vb.mapSceneToView(pos)
            #Crosshair adjust
            if self.config.get_property('crosshair_enable', True):
                self.crosshair_v.setPos(mousePoint.x())
                self.crosshair_h.setPos(mousePoint.y())
                priceValue = mousePoint.y()
                if mousePoint.y() < 1:
                    priceValue = round(priceValue, 4)
                else:
                    priceValue = round(priceValue, 3)
                self.crosshair_h.label.setFormat(str(priceValue))
                try:
                    timeValue = datetime.fromtimestamp(mousePoint.x()).strftime("%d %b - %H:%M")
                    #timeValue = self.parentWidget._offset.fromtimestamp(mousePoint.x(), self.twsTimezone).strftime("%d %b - %H:%M")
                    self.crosshair_v.label.setFormat(timeValue)
                except OSError:
                    ui_log.warning("WARNING: Invalid Time Value on mouse cursor")
                self.crosshair_v.setVisible(True)
                self.crosshair_h.setVisible(True)
            #Check for hover
            activeHovers = []

            barHover = self.candlestickItem.mouseOverBar(mousePoint)
            if barHover:
                activeHovers.append(self.candlestickItem.hoverItem)
            volMousePoint = self.volumeViewBox.mapSceneToView(pos)
            volHover = self.volumeBarsItem.mouseOverBar(volMousePoint)
            if volHover:
                activeHovers.append(self.volumeBarsItem.hoverItem)

            for indicatorItem in self.parentWidget.indicators:
                if indicatorItem.indicator.plotLocation != "main":
                    continue
                if indicatorItem.indicator.displayType == "multi_plot":
                    for plotName, plotItem in indicatorItem.chartItems.items():
                        if plotItem.curve.mouseShape().contains(mousePoint) and plotItem.isVisible():
                            data = plotItem.getData()
                            series = pd.Series(data[1], index=data[0])
                            nearestIndex = series.index.get_indexer([mousePoint.x()], method='nearest')
                            nearestValue = float(series.iloc[nearestIndex])
                            hoverPoint = QPointF(mousePoint.x(), mousePoint.y())
                            for activeHoverItem in activeHovers:
                                rect = activeHoverItem.boundingRect().marginsAdded(QMarginsF(4,4,4,4))
                                rect = activeHoverItem.mapRectToParent(rect)
                                hoverPoint += QPointF(0, rect.height())
                            hoverItem = indicatorItem.hover(hoverPoint, nearestValue, plotName)
                            ui_log.debug(f'{indicatorItem.indicator.name}, {plotName}, {nearestValue}, {hoverItem.mapRectToScene(hoverItem.boundingRect())}')
                            activeHovers.append(hoverItem)
                            shadowPenWidth = plotItem.opts['pen'].width()+2
                            plotItem.setShadowPen(pg.mkPen(QColor(255,255,255,100), width=shadowPenWidth))
                        else:
                            indicatorItem.unhover(plotName)
                            plotItem.setShadowPen(pg.mkPen(None))
                elif indicatorItem.indicator.displayType == "plot":
                    plotItem = indicatorItem.chartItem
                    if plotItem.curve.mouseShape().contains(mousePoint) and plotItem.isVisible():
                        data = plotItem.getData()
                        series = pd.Series(data[1], index=data[0])
                        nearestIndex = series.index.get_indexer([mousePoint.x()], method='nearest')
                        nearestValue = float(series.iloc[nearestIndex])
                        hoverPoint = QPointF(mousePoint.x(), mousePoint.y())
                        for activeHoverItem in activeHovers:
                            rect = activeHoverItem.boundingRect().marginsAdded(QMarginsF(4,4,4,4))
                            rect = activeHoverItem.mapRectToParent(rect)
                            hoverPoint += QPointF(0, rect.height())
                        ui_log.debug(f'{indicatorItem.indicator.name}, {nearestValue}')
                        hoverItem = indicatorItem.hover(hoverPoint, nearestValue)
                        activeHovers.append(hoverItem)
                        shadowPenWidth = plotItem.opts['pen'].width()+2
                        plotItem.setShadowPen(pg.mkPen(QColor(255,255,255,100), width=shadowPenWidth))
                    else:
                        indicatorItem.unhover()
                        plotItem.setShadowPen(pg.mkPen(None))
        else:
            self.crosshair_v.setVisible(False)
            self.crosshair_h.setVisible(False)
        pg.PlotWidget.mouseMoveEvent(self, e)

    def updateMktPrice(self, newMktPrice, mktPriceColor=QColor(COLOR_GREEN)):
        self.mktPricePen.setColor(mktPriceColor)
        self.mktPrice = newMktPrice
        self.mktPriceLine.setValue(newMktPrice)
        self.mktPriceLine.setPen(self.mktPricePen)
        self.mktPriceLine.label.fill = pg.mkBrush(self.mktPricePen.color())

    def leaveEvent(self, e):
        self.crosshair_v.setVisible(False)
        self.crosshair_h.setVisible(False)
        pg.PlotWidget.leaveEvent(self, e)

class ChartOptions(pg.GraphicsWidget, pg.GraphicsWidgetAnchor):
    barSizeChanged = Signal(str, Chart)
    def __init__(self, plotWidget, chart, config=Config()):
        pg.GraphicsWidget.__init__(self)
        pg.GraphicsWidgetAnchor.__init__(self)
        self.config = config
        self.plotWidget = plotWidget
        self.chart = chart
        self.setFlag(self.GraphicsItemFlag.ItemIgnoresTransformations)
        self.layout = QGraphicsLinearLayout()
        self.setLayout(self.layout)

        self.barSizeCombo = QComboBox()
        self.barSizeCombo.addItems(['1s', '5s', '10s', '15s', '30s', '1m', '2m', '3m', '5m', '10m', '15m', '20m', '30m', '1h', '2h', '3h', '4h', '8h', '1D', '1W', '1M'])
        self.barSizeCombo.insertSeparator(5)
        self.barSizeCombo.insertSeparator(14)
        self.barSizeCombo.insertSeparator(20)
        self.barSizeCombo.setCurrentText(self.config.get_property('current_bar_size', '1m'))
        self.barSizeCombo.currentIndexChanged.connect(self.barSizeComboChanged)
        self.barSizeComboProxy = plotWidget.scene().addWidget(self.barSizeCombo)
        self.layout.addItem(self.barSizeComboProxy)

        self.showOptions = OptionComboBox("Show", ['Book Depth', 'Grid', 'Crosshair', 'Pre/Post-Market Highlight'])
        self.showOptions.items[0].setData(Qt.Checked if self.config.get_property('showBookDepth', False) else Qt.Unchecked, Qt.CheckStateRole)
        self.showOptions.items[1].setData(Qt.Checked if self.config.get_property('showGrid', False) else Qt.Unchecked, Qt.CheckStateRole)
        self.showOptions.items[2].setData(Qt.Checked if self.config.get_property('crosshair_enabled', True) else Qt.Unchecked, Qt.CheckStateRole)
        self.showOptions.items[3].setData(Qt.Checked if self.config.get_property('pre_post_market_highlight', True) else Qt.Unchecked, Qt.CheckStateRole)
        self.showOptionsProxy = plotWidget.scene().addWidget(self.showOptions)
        self.showOptionsChanged = self.showOptions.optionChanged
        self.layout.addItem(self.showOptionsProxy)

        self.indicatorOptions = IndicatorComboBox(self.chart.indicators)
        self.indicatorProxy = plotWidget.scene().addWidget(self.indicatorOptions)
        self.layout.addItem(self.indicatorProxy)

        self.setParentItem(plotWidget.getPlotItem())
        self.anchor(itemPos=(0,0), parentPos=(0,0), offset=(10,10))

    def barSizeComboChanged(self, index):
        newBarSize = str(self.barSizeCombo.currentText())
        self.barSizeChanged.emit(newBarSize, self.chart)
        self.chart.barSize = newBarSize

class ChartPane(pg.PlotWidget):
    def __init__(self, parent, name, config=Config()):
        pg.PlotWidget.__init__(self, parent)
        self.parentWidget = parent
        self.name = name
        self.config = config
        self.twsTimezone = self.config.get_property("twsTimezone", "US/Pacific")
        
        plotItem = self.getPlotItem()
        plotItem.registerPlot(name)
        plotItem.hideButtons()
        self.prePostMarketItem = PrePostMarketItem(self.twsTimezone, self.parentWidget._offset)
        self.addItem(self.prePostMarketItem)
        self.prePostMarketItem.setVisible(self.config.get_property("pre_post_market_highlight", True))
    
    def mouseMoveEvent(self, e):
        pos = e.pos()
        if self.sceneBoundingRect().contains(pos):
            mousePoint = self.getPlotItem().vb.mapSceneToView(pos)
            #Crosshair adjust
            """
            if self.config.get_property('crosshair_enable', True):
                self.crosshair_v.setPos(mousePoint.x())
                self.crosshair_h.setPos(mousePoint.y())
                priceValue = mousePoint.y()
                if mousePoint.y() < 1:
                    priceValue = round(priceValue, 4)
                else:
                    priceValue = round(priceValue, 3)
                self.crosshair_h.label.setFormat(str(priceValue))
                try:
                    timeValue = datetime.fromtimestamp(mousePoint.x()).strftime("%d %b - %H:%M")
                    self.crosshair_v.label.setFormat(timeValue)
                except OSError:
                    print("WARNING: Invalid Time Value on mouse cursor")
                self.crosshair_v.setVisible(True)
                self.crosshair_h.setVisible(True)"""
            #Check for hover
            activeHovers = []

            for indicatorItem in self.parentWidget.indicators:
                if indicatorItem.indicator.plotLocation != self.name:
                    continue
                if indicatorItem.indicator.displayType == "multi_plot":
                    for plotName, plotItem in indicatorItem.chartItems.items():
                        if plotItem.curve.mouseShape().contains(mousePoint) and plotItem.isVisible():
                            data = plotItem.getData()
                            series = pd.Series(data[1], index=data[0])
                            nearestIndex = series.index.get_indexer([mousePoint.x()], method='nearest')
                            nearestValue = float(series.iloc[nearestIndex])
                            hoverPoint = QPointF(mousePoint.x(), mousePoint.y())
                            for activeHoverItem in activeHovers:
                                rect = activeHoverItem.boundingRect().marginsAdded(QMarginsF(4,4,4,4))
                                rect = activeHoverItem.mapRectToParent(rect)
                                hoverPoint += QPointF(0, rect.height())
                            hoverItem = indicatorItem.hover(hoverPoint, nearestValue, plotName)
                            ui_log.debug(f'{indicatorItem.indicator.name}, {plotName}, {nearestValue}, {hoverItem.mapRectToScene(hoverItem.boundingRect())}')
                            activeHovers.append(hoverItem)
                            shadowPenWidth = plotItem.opts['pen'].width()+2
                            plotItem.setShadowPen(pg.mkPen(QColor(255,255,255,100), width=shadowPenWidth))
                        else:
                            indicatorItem.unhover(plotName)
                            plotItem.setShadowPen(pg.mkPen(None))
                elif indicatorItem.indicator.displayType == "plot":
                    plotItem = indicatorItem.chartItem
                    if plotItem.curve.mouseShape().contains(mousePoint) and plotItem.isVisible():
                        data = plotItem.getData()
                        series = pd.Series(data[1], index=data[0])
                        nearestIndex = series.index.get_indexer([mousePoint.x()], method='nearest')
                        nearestValue = float(series.iloc[nearestIndex])
                        hoverPoint = QPointF(mousePoint.x(), mousePoint.y())
                        for activeHoverItem in activeHovers:
                            rect = activeHoverItem.boundingRect().marginsAdded(QMarginsF(4,4,4,4))
                            rect = activeHoverItem.mapRectToParent(rect)
                            hoverPoint += QPointF(0, rect.height())
                        ui_log.debug(f'{indicatorItem.indicator.name}, {nearestValue}')
                        hoverItem = indicatorItem.hover(hoverPoint, nearestValue)
                        activeHovers.append(hoverItem)
                        shadowPenWidth = plotItem.opts['pen'].width()+2
                        plotItem.setShadowPen(pg.mkPen(QColor(255,255,255,100), width=shadowPenWidth))
                    else:
                        indicatorItem.unhover()
                        plotItem.setShadowPen(pg.mkPen(None))

class OptionComboBox(QComboBox):
    optionChanged = Signal(str, bool)
    def __init__(self, name, options=[]):
        QComboBox.__init__(self)
        self.name = name
        self.itemModel = QStandardItemModel(len(options), 1)
        self.items = []
        self.setProperty("optionBox", "yes")
        maxWidth = 0
        for i, text in enumerate(options):
            item = QStandardItem(text)
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setData(Qt.Checked, Qt.CheckStateRole)
            self.itemModel.setItem(i,0,item)
            self.items.append(item)
            textWidth = self.fontMetrics().horizontalAdvance(text)
            if textWidth > maxWidth:
                maxWidth = textWidth
        self.setModel(self.itemModel)
        self.itemModel.itemChanged.connect(self.onItemChanged)
        #self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.setMinimumWidth(50)
        #print("QComboBox QAbstractItemView::item {{min-width:{}px;}}".format(int(maxWidth)+25))
        #self.setStyleSheet("QComboBox QAbstractItemView::item {{min-width:{}px;}}".format(int(maxWidth)+25))

    def paintEvent(self, e):
        painter = QStylePainter(self)
        painter.setPen(self.palette().color(QPalette.Text))

        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        opt.currentText = self.name
        painter.drawComplexControl(QStyle.CC_ComboBox, opt)

        painter.drawControl(QStyle.CE_ComboBoxLabel, opt)

    def onItemChanged(self, item):
        ui_log.debug(f'OPTION CHANGED, {item.text()}, {item.checkState()}')
        self.optionChanged.emit(str(item.text()), item.checkState() == Qt.Checked)

    def showPopup(self):
        self.view().setMinimumWidth(self.view().viewportSizeHint().width())
        QComboBox.showPopup(self)
        self.view().setFocusPolicy(Qt.NoFocus)

class CandlestickItem(pg.GraphicsObject):
    BRUSH_RED = pg.mkBrush(COLOR_RED)
    BRUSH_RED_HOVER = pg.mkBrush(COLOR_RED_HOVER)
    BRUSH_GREEN = pg.mkBrush(COLOR_GREEN)
    BRUSH_GREEN_HOVER = pg.mkBrush(COLOR_GREEN_HOVER)
    def __init__(self, data, offset):
        pg.GraphicsObject.__init__(self)
        self.data = data  ## data must have fields: time, open, close, min, max
        self.offset = offset
        #self.resampledData = data
        self.picture = self.generatePicture(data)
        #self.resampledPicture = self.generatePicture(self.resampledData)
        self.hoverItem = pg.TextItem(text="", color="#FFF", fill=QColor(61, 64, 105, 128), anchor=(1,1))
        self.hoverItem.setVisible(False)
        self.currentlyHoveredBar = None
        self.lastBar = None
        self.default_width = 0

    def infer_freq(self, barData):
        return barData.index.to_series().diff().median()

    def resampleData(self, data, freq='5T'):
        return data.resample(freq).agg({'open' : 'first', 'high': np.max, 'low': np.min, 'close': 'last'})

    def generatePicture(self, data):
        ## pre-computing a QPicture object allows paint() to run much more quickly,
        ## rather than re-drawing the shapes every time.
        picture = QPicture()
        p = QPainter(picture)
        if len(data) < 2:
            p.end()
            return picture
        p.setPen(pg.mkPen('w'))
        picture.w = w = self.infer_freq(data).total_seconds()
        for bar in data.iloc[:-1].itertuples():
            t = bar.Index.timestamp()
            #t = self.offset.timestamp(bar.Index)
            if bar.open > bar.close:
                p.setBrush(pg.mkBrush(COLOR_RED))
                p.setPen(pg.mkPen(COLOR_RED))
            else:
                p.setBrush(pg.mkBrush(COLOR_GREEN))
                p.setPen(pg.mkPen(COLOR_GREEN))
            if bar.low != bar.high:
                p.drawLine(QPointF(t, bar.low), QPointF(t, bar.high))
            p.drawRect(QRectF(t-w*0.375, bar.open, w*0.75, bar.close-bar.open))
        p.end()
        return picture

    def paint(self, p, *args):
        #barRealWidth = self.getViewBox().mapViewToScene(QRectF(0, 0, self.default_width, 1)).boundingRect().width()
        #print(barRealWidth)
        #if barRealWidth < 1.0:
        #    #print('RESAMPLING DATA')
        #    p.drawPicture(0, 0, self.resampledPicture)
        #else:
        p.drawPicture(0, 0, self.picture)
        if not self.lastBar is None:
            color = COLOR_GREEN if self.lastBar["open"] <= self.lastBar["close"] else COLOR_RED
            p.setBrush(pg.mkBrush(color))
            p.setPen(pg.mkPen(color))
            #lastBarTimestamp = self.offset.timestamp(self.lastBar.name)
            lastBarTimestamp = self.lastBar.name.timestamp()
            lastBarRect = QRectF(lastBarTimestamp-self.picture.w*0.375, self.lastBar["open"], self.picture.w*0.75, self.lastBar["close"]-self.lastBar["open"])
            p.drawLine(QPointF(lastBarTimestamp, self.lastBar["low"]), QPointF(lastBarTimestamp, self.lastBar["high"]))
            p.drawRect(lastBarRect)
        hoverBar = self.currentlyHoveredBar
        if not hoverBar is None:
            color = COLOR_GREEN_HOVER if hoverBar["open"] <= hoverBar["close"] else COLOR_RED_HOVER
            p.setBrush(pg.mkBrush(color))
            p.setPen(pg.mkPen(color))
            #hoverBarTimestamp = self.offset.timestamp(hoverBar.name)
            hoverBarTimestamp = hoverBar.name.timestamp()
            hoverRect = QRectF(hoverBarTimestamp-self.picture.w*0.375, hoverBar["open"], self.picture.w*0.75, hoverBar["close"]-hoverBar["open"])
            p.drawLine(QPointF(hoverBarTimestamp, hoverBar["low"]), QPointF(hoverBarTimestamp, hoverBar["high"]))
            p.drawRect(hoverRect)

    def lastBarRect(self):
        if not self.lastBar is None:
            #lastBarTimestamp = self.offset.timestamp(self.lastBar.name)
            lastBarTimestamp = self.lastBar.name.timestamp()
            lastBarRect = QRectF(lastBarTimestamp-self.default_width*0.375, self.lastBar["open"], self.default_width*0.75, self.lastBar["close"]-self.lastBar["open"])
            return lastBarRect
        else:
            return QRectF()

    def boundingRect(self):
        ## boundingRect _must_ indicate the entire area that will be drawn on
        ## or else we will get artifacts and possibly crashing.
        ## (in this case, QPicture does all the work of computing the bouning rect for us)
        return QRectF(self.picture.boundingRect()).united(self.lastBarRect())

    def setData(self, data):
        if data.empty:
            return
        self.data = data
        self.lastBar = data.iloc[-1]
        self.default_width = self.infer_freq(data).total_seconds()
        #self.resampledData = self.resampleData(data, freq='60T')
        self.picture = self.generatePicture(data)
        #self.resampledPicture = self.generatePicture(self.resampledData)

    def setLastBar(self, lastBar):
        self.lastBar = lastBar
        self.data.iloc[-1] = lastBar
        self.update(self.lastBarRect())

    def showHoverItem(self, barData, mousePos):
        if not self.hoverItem.isVisible():
            self.hoverItem.setVisible(True)
        self.hoverItem.setPos(mousePos)

        hoverBarChanged = False
        oldBarRect = QRectF()
        if not self.currentlyHoveredBar is barData:
            hoverBarChanged = True
            if not self.currentlyHoveredBar is None:
                oldBar = self.currentlyHoveredBar
                #oldBarTimestamp = self.offset.timestamp(oldBar.name)
                oldBarTimestamp = oldBar.name.timestamp()
                oldBarRect = QRectF(oldBarTimestamp-self.picture.w*0.375, oldBar["low"], self.picture.w*0.75, oldBar["high"]-oldBar["low"])
        self.currentlyHoveredBar = barData

        if hoverBarChanged:
            self.hoverItem.setText(f'Open: {barData["open"]}\nHigh: {barData["high"]}\nLow: {barData["low"]}\nClose: {barData["close"]}\nVolume: {barData["volume"]}')
            if barData["open"] > barData["close"]:
                self.hoverItem.fill = pg.mkBrush(COLOR_RED)
            else:
                self.hoverItem.fill = pg.mkBrush(COLOR_GREEN)
            #barDataTimestamp = self.offset.timestamp(barData.name)
            barDataTimestamp = barData.name.timestamp()
            barRect = QRectF(barDataTimestamp-self.picture.w*0.375, barData["low"], self.picture.w*0.75, barData["high"]-barData["low"])
            self.update(barRect.united(oldBarRect))


    def hideHoverItem(self):
        if self.hoverItem.isVisible():
            self.hoverItem.setVisible(False)
            bar = self.currentlyHoveredBar
            #barTimestamp = self.offset.timestamp(bar)
            barTimestamp = bar.name.timestamp()
            rectToUpdate = QRectF(barTimestamp-self.picture.w*0.375, bar["low"], self.picture.w*0.75, bar["high"]-bar["low"])
            self.currentlyHoveredBar = None
            self.update(rectToUpdate)

    def mouseOverBar(self, mousePos):
        x = mousePos.x()
        y = mousePos.y()
        if not isinstance(self.data.index, pd.DatetimeIndex):
            return False
        mouseTimestamp = pd.Timestamp.fromtimestamp(x).tz_localize(self.data.index.tz, ambiguous=True)
        #mouseTimestamp = self.offset.fromtimestamp(x, self.data.index.tz).tz_localize(self.data.index.tz, ambiguous=True)
        if not (mouseTimestamp > self.data.index[0] and mouseTimestamp < self.data.index[-1]):
            self.hideHoverItem()
            return False
        nearestIndex = self.data.index.get_indexer([mouseTimestamp], method='nearest')[0]
        if y >= self.data.iloc[nearestIndex]["low"] and y <= self.data.iloc[nearestIndex]["high"]:
            self.showHoverItem(self.data.iloc[nearestIndex], mousePos)
            return True
        self.hideHoverItem()
        return False

class VolumeBars(pg.BarGraphItem):
    def __init__(self, data, offset):
        pg.BarGraphItem.__init__(self)
        self.offset = offset
        self.setData(data)

        self.hoverItem = pg.TextItem(text="", color="#FFF", fill=QColor(61, 64, 105, 128), anchor=(1,1))
        self.hoverItem.setVisible(False)
        self.currentlyHoveredBar = None
        self.w = 0

    def infer_freq(self, barData):
        if barData.index.size == 0:
            return pd.Timedelta(0)
        return barData.index.to_series().diff().median()

    def setData(self, data):
        self.data = data
        self.w = w = self.infer_freq(data).total_seconds()
        data["is_green"] = data["open"] < data["close"]
        brushes = [(pg.mkBrush(COLOR_GREEN+'88') if is_green else pg.mkBrush(COLOR_RED+'88')) for is_green in data["is_green"].tolist()]
        self.setOpts(x=[index.timestamp() for index in data.index],
                    height=data["volume"].tolist(),
                    width=w*0.75,
                    brushes=brushes,
                    pen=pg.mkPen(None))

    def showHoverItem(self, barData, mousePos):
        if not self.hoverItem.isVisible():
            self.hoverItem.setVisible(True)
        self.hoverItem.setPos(mousePos)

        hoverBarChanged = False
        oldBarRect = QRectF()
        if not self.currentlyHoveredBar is barData:
            hoverBarChanged = True
            if not self.currentlyHoveredBar is None:
                oldBar = self.currentlyHoveredBar
                #oldBarTimestamp = self.offset.timestamp(oldBar.name)
                oldBarTimestamp = oldBar.name.timestamp()
                oldBarRect = QRectF(oldBarTimestamp-self.w*0.5, 0.0, self.w, oldBar["volume"])
        self.currentlyHoveredBar = barData

        if hoverBarChanged:
            self.hoverItem.setText(f'Volume\n{barData["volume"]}')
            if barData["open"] > barData["close"]:
                self.hoverItem.fill = pg.mkBrush(COLOR_RED)
            else:
                self.hoverItem.fill = pg.mkBrush(COLOR_GREEN)
            # barDataTimestamp = self.offset.timestamp(barData.name)
            barDataTimestamp = barData.name.timestamp()
            barRect = QRectF(barDataTimestamp-self.w*0.5, 0.0, self.w, barData["volume"])
            self.update(barRect.united(oldBarRect))

    def hideHoverItem(self):
        if self.hoverItem.isVisible():
            self.hoverItem.setVisible(False)
            bar = self.currentlyHoveredBar
            # barTimestamp = self.offset.timestamp(bar.name)
            barTimestamp = bar.name.timestamp()
            rectToUpdate = QRectF(barTimestamp-self.w*0.5, 0.0, self.w, bar["volume"])
            self.currentlyHoveredBar = None
            self.update(rectToUpdate)

    def mouseOverBar(self, mousePos):
        x = mousePos.x()
        y = mousePos.y()
        if not isinstance(self.data.index, pd.DatetimeIndex):
            return False
        mouseTimestamp = pd.Timestamp.fromtimestamp(x).tz_localize(self.data.index.tz, ambiguous=True)
        #mouseTimestamp = self.offset.fromtimestamp(x, self.data.index.tz).tz_localize(self.data.index.tz, ambiguous=True)
        if not (mouseTimestamp > self.data.index[0] and mouseTimestamp < self.data.index[-1]):
            self.hideHoverItem()
            return False
        nearestIndex = self.data.index.get_indexer([mouseTimestamp], method='nearest')[0]
        if y >= 0.0 and y <= self.data.iloc[nearestIndex]["volume"]:
            self.showHoverItem(self.data.iloc[nearestIndex], mousePos)
            return True
        self.hideHoverItem()
        return False

class PrePostMarketItem(pg.GraphicsObject):
    PRE_MARKET_BRUSH = pg.mkBrush("#7a691432")
    POST_MARKET_BRUSH = pg.mkBrush("#14257a32")
    def __init__(self, timezone, offset):
        pg.GraphicsObject.__init__(self)
        self.timezone = timezone
        self.trading_offset = offset
        self.marketHours = preMarketOpen, marketOpen, marketClose, postMarketClose = get_market_hours(self.timezone)
        self.offset = pre_post_market_offset_factory(preMarketOpen, marketOpen, marketClose, postMarketClose)

    def paint(self, p, *args):
        viewRect = QRectF(self.getViewBox().viewRect())
        startTime = pd.Timestamp.fromtimestamp(viewRect.left()).tz_localize(self.timezone, ambiguous=True)
        #startTime = self.trading_offset.fromtimestamp(viewRect.left(), self.timezone).tz_localize(self.timezone, ambiguous=True)
        endTime = pd.Timestamp.fromtimestamp(viewRect.right()).tz_localize(self.timezone, ambiguous=True)
        #endTime = self.trading_offset.fromtimestamp(viewRect.right(), self.timezone).tz_localize(self.timezone, ambiguous=True)
        if endTime - startTime > pd.Timedelta('28D'):
            return
        currentTime = self.offset.rollback(startTime)
        preMarketOpen, marketOpen, marketClose, postMarketClose = self.marketHours
        while currentTime <= endTime:
            currentTimeStr = currentTime.strftime("%H:%M")
            if currentTimeStr in [preMarketOpen, marketClose]:
                if currentTimeStr == preMarketOpen:
                    brush = self.PRE_MARKET_BRUSH
                elif currentTimeStr == marketClose:
                    brush = self.POST_MARKET_BRUSH
                #rectLeft = self.trading_offset.timestamp(currentTime)
                rectLeft = currentTime.timestamp()
                currentTime += self.offset
                #rectRight = self.trading_offset.timestamp(currentTime)
                rectRight = currentTime.timestamp()
                currentTime += self.offset
                rectToDraw = QRectF(QPointF(rectLeft, viewRect.top()), QPointF(rectRight, viewRect.bottom()))
                p.fillRect(rectToDraw, brush)
            else:
                currentTime += self.offset

    def boundingRect(self):
        return QRectF(self.viewRect())
    
    def dataBounds(self, axis, frac=1.0, orthoRange=None):
        return None

class DateAxisItem(pg.AxisItem):
    """
    A tool that provides a date-time aware axis. It is implemented as an
    AxisItem that interpretes positions as unix timestamps (i.e. seconds
    since 1970).
    The labels and the tick positions are dynamically adjusted depending
    on the range.
    It provides a  :meth:`attachToPlotItem` method to add it to a given
    PlotItem
    """

    # Max width in pixels reserved for each label in axis
    _pxLabelWidth = 80

    def __init__(self, *args, **kwargs):
        pg.AxisItem.__init__(self, *args, **kwargs)
        self.offset = kwargs.get("offset")
        self.timezone = kwargs.get("timezone")
        self._oldAxis = None

    def tickValues(self, minVal, maxVal, size):
        """
        Reimplemented from PlotItem to adjust to the range and to force
        the ticks at "round" positions in the context of time units instead of
        rounding in a decimal base
        """

        maxMajSteps = int(size/self._pxLabelWidth)

        try:
            dt1 = datetime.fromtimestamp(minVal)
            #dt1 = self.offset.fromtimestamp(minVal, self.timezone).to_pydatetime()
        except:
            ui_log.debug(f'{minVal}, {maxVal}, {size}')
        dt2 = datetime.fromtimestamp(maxVal)
        #dt2 = self.offset.fromtimestamp(maxVal, self.timezone).to_pydatetime()

        dx = maxVal - minVal
        majticks = []

        if dx > 63072001:  # 3600s*24*(365+366) = 2 years (count leap year)
            d = timedelta(days=366)
            for y in range(dt1.year + 1, dt2.year):
                dt = datetime(year=y, month=1, day=1)
                majticks.append(mktime(dt.timetuple()))

        elif dx > 5270400:  # 3600s*24*61 = 61 days
            d = timedelta(days=31)
            dt = dt1.replace(day=1, hour=0, minute=0,
                             second=0, microsecond=0) + d
            while dt < dt2:
                # make sure that we are on day 1 (even if always sum 31 days)
                dt = dt.replace(day=1)
                majticks.append(mktime(dt.timetuple()))
                dt += d

        elif dx > 172800:  # 3600s24*2 = 2 days
            d = timedelta(days=1)
            dt = dt1.replace(hour=0, minute=0, second=0, microsecond=0) + d
            while dt < dt2:
                majticks.append(mktime(dt.timetuple()))
                dt += d

        elif dx > 7200:  # 3600s*2 = 2hours
            d = timedelta(hours=1)
            dt = dt1.replace(minute=0, second=0, microsecond=0) + d
            while dt < dt2:
                majticks.append(mktime(dt.timetuple()))
                dt += d

        elif dx > 3600:  # 60s*60 = 60 minutes
            d = timedelta(minutes=10)
            dt = dt1.replace(minute=(dt1.minute // 10) * 10,
                             second=0, microsecond=0) + d
            while dt < dt2:
                majticks.append(mktime(dt.timetuple()))
                dt += d

        elif dx > 120:  # 60s*2 = 2 minutes
            d = timedelta(minutes=1)
            dt = dt1.replace(second=0, microsecond=0) + d
            while dt < dt2:
                majticks.append(mktime(dt.timetuple()))
                dt += d

        elif dx > 20:  # 20s
            d = timedelta(seconds=10)
            dt = dt1.replace(second=(dt1.second // 10) * 10, microsecond=0) + d
            while dt < dt2:
                majticks.append(mktime(dt.timetuple()))
                dt += d

        elif dx > 2:  # 2s
            d = timedelta(seconds=1)
            majticks = range(int(minVal), int(maxVal))

        else:  # <2s , use standard implementation from parent
            return pg.AxisItem.tickValues(self, minVal, maxVal, size)

        L = len(majticks)
        if L > maxMajSteps:
            majticks = majticks[::int(np.ceil(float(L) / maxMajSteps))]

        return [(d.total_seconds(), majticks)]

    def tickStrings(self, values, scale, spacing):
        """Reimplemented from PlotItem to adjust to the range"""
        ret = []
        if not values:
            return []

        if spacing >= 31622400:  # 366 days
            fmt = "%Y"

        elif spacing >= 2678400:  # 31 days
            fmt = "%Y %b"

        elif spacing >= 86400:  # = 1 day
            fmt = "%Y/%b/%d"

        elif spacing >= 3600:  # 1 h
            fmt = "%b %d - %H:%M"

        elif spacing >= 60:  # 1 m
            fmt = "%H:%M"

        elif spacing >= 1:  # 1s
            fmt = "%H:%M:%S"

        else:
            # less than 2s (show microseconds)
            # fmt = '%S.%f"'
            fmt = '[+%fms]'  # explicitly relative to last second

        for x in values:
            try:
                t = datetime.fromtimestamp(x)
                #t = self.offset.fromtimestamp(x, self.timezone).to_pydatetime()
                ret.append(t.strftime(fmt))
            except ValueError:  # Windows can't handle dates before 1970
                ret.append('')

        return ret

    def attachToPlotItem(self, plotItem):
        """Add this axis to the given PlotItem
        :param plotItem: (PlotItem)
        """
        self.setParentItem(plotItem)
        viewBox = plotItem.getViewBox()
        self.linkToView(viewBox)
        self._oldAxis = plotItem.axes[self.orientation]['item']
        self._oldAxis.hide()
        plotItem.axes[self.orientation]['item'] = self
        pos = plotItem.axes[self.orientation]['pos']
        plotItem.layout.addItem(self, *pos)
        self.setZValue(-1000)

class PriceTapeAxis(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        pg.AxisItem.__init__(self, *args, **kwargs)
        self.bookData = None

    def tickValues(self, minVal, maxVal, size):
        screenHeight = self.geometry().height()
        textHeight = 15
        maxTicks = math.floor(screenHeight / textHeight)
        range = abs(maxVal-minVal)
        tickStep = math.pow(10, math.ceil(math.log(range/maxTicks, 10)))
        if range/maxTicks < tickStep * 0.5:
            tickStep = tickStep * 0.5
        if range/maxTicks < tickStep * 0.2:
            tickStep = tickStep * 0.2
        maxTick = math.floor(maxVal/tickStep)*tickStep
        minTick = math.ceil(minVal/tickStep)*tickStep
        ticks = list(np.arange(minTick, maxTick+tickStep, tickStep))
        return [(tickStep, ticks)]

    def tickStrings(self, values, scale, spacing):
        strings = pg.AxisItem.tickStrings(self, values, scale, spacing)
        if self.bookData:
            for i, value in enumerate(values):
                for price, bidSize, askSize in self.bookData:
                    if value == price:
                        strings[i] += ' - {} - {}'.format(bidSize, askSize)
        return strings

    def attachToPlotItem(self, plotItem):
        """Add this axis to the given PlotItem
        :param plotItem: (PlotItem)
        """
        self.setParentItem(plotItem)
        viewBox = plotItem.getViewBox()
        self.linkToView(viewBox)
        self._oldAxis = plotItem.axes[self.orientation]['item']
        self._oldAxis.hide()
        plotItem.axes[self.orientation]['item'] = self
        pos = plotItem.axes[self.orientation]['pos']
        plotItem.layout.addItem(self, *pos)
        self.setZValue(-1000)

    def setBookData(self, bookData):
        self.bookData = bookData
