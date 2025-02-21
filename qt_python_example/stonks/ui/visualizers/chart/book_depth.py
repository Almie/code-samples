from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
import pyqtgraph as pg
import numpy as np
import pandas as pd
import math
from decimal import Decimal, getcontext

import logging
ui_log = logging.getLogger('UI')

COLOR_GREEN = "#26A69A"
COLOR_RED = "#EF5350"
COLOR_BG = "#151924"

#Set Decimal Precision
getcontext().prec = 6

class BookDepthItem(pg.ScatterPlotItem):
    def __init__(self):
        pg.ScatterPlotItem.__init__(self)
        self.marketDepthData = None
        self.minStep = None

    def setBookData(self, marketDepthData):
        self.marketDepthData = marketDepthData
        self.generateSpots()

    def generateSpots(self):
        spots = []
        bookData = self.marketDepthData.bookData(self.minStep)
        #print('BOOK DEPTH SPOTS', list(bookData.index))
        for row in bookData.itertuples():
            if pd.notna(row.size_bid) and row.size_bid > 0:
                symbol, scale = self.createTextSymbol(str(row.size_bid), side=1)
                spots.append({'pos': (0, row.Index), 'data': row.Index, 'brush': pg.mkBrush('w'), 'pen': pg.mkPen(None), 'symbol': symbol, 'size': scale * 10})
            if pd.notna(row.size_ask) and row.size_ask > 0:
                symbol, scale = self.createTextSymbol(str(row.size_ask), side=0)
                spots.append({'pos': (0, row.Index), 'data': row.Index, 'brush': pg.mkBrush('w'), 'pen': pg.mkPen(None), 'symbol': symbol, 'size': scale * 10})
        self.setData(spots)

    def createTextSymbol(self, text, side=0):
        symbol = QPainterPath()
        font = QFont()
        font.setPointSize(10)
        symbol.addText(0,0,font,text)

        br = symbol.boundingRect()
        padding = 7
        scale = min(0.5/(br.width()+padding), 1./br.height())
        tr = QTransform()
        tr.scale(scale, scale)
        if side == 0:
            tr.translate(-br.x() + padding, -br.y() - br.height() / 2.)
        elif side == 1:
            tr.translate(-br.x() - (br.width()+padding), -br.y() - br.height() / 2.)

        return tr.map(symbol), 0.1/scale

    def paint(self, p, *args):
        screenHeight = self.getViewWidget().rect().height()
        textHeight = 15
        maxTicks = math.floor(screenHeight / textHeight)
        maxVal = self.viewRect().bottom()
        minVal = self.viewRect().top()
        range = abs(maxVal-minVal)
        tickStep = Decimal(1)
        for stepValue in [1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001, 0.0005, 0.0002, 0.0001]:
            if range/maxTicks < stepValue:
                tickStep = Decimal(stepValue)
        if self.minStep != tickStep:
            self.minStep = tickStep
            self.generateSpots()
        pg.ScatterPlotItem.paint(self, p, *args)
        #print('paint!', self.getViewWidget().rect(), maxVal, minVal, self.viewRect(), tickStep)

class BookDepthGrid(pg.GridItem):
    def __init__(self, *args, **kwargs):
        pg.GridItem.__init__(self, *args, **kwargs)
        self.bookData = None

    def generatePicture(self):
        self.picture = QPicture()
        p = QPainter(self.picture)
        p.setPen(pg.mkPen('#373D53'))
        boundingRect = self.boundingRect()
        vr = self.getViewWidget().rect()
        unit = self.pixelWidth(), self.pixelHeight()
        #print(boundingRect.top(), boundingRect.bottom(), vr, unit)
        tickStep, ticks = self.tickValues(boundingRect.top(), boundingRect.bottom())[0]

        #colored rectangles
        oddRow = True
        if self.bookData:
            data = self.bookData.bookData(minStep=tickStep)
            ui_log.debug(str(data))
            ui_log.debug(f'{tickStep}, {type(tickStep)}, {getcontext().prec}, {ticks}')
            for tick in ticks:
                bidRect = QRectF(boundingRect.left(), tick-(tickStep/2), (boundingRect.right()-boundingRect.left())/2, tickStep)
                askRect = QRectF(boundingRect.left()+(boundingRect.right()-boundingRect.left())/2, tick-(tickStep/2), (boundingRect.right()-boundingRect.left())/2, tickStep)
                colorBidBg = QColor("#151924" if oddRow else "#0F1219")
                colorAskBg = QColor("#1E2231" if oddRow else "#151924")
                p.fillRect(bidRect, QBrush(colorBidBg))
                p.fillRect(askRect, QBrush(colorAskBg))
                oddRow = not oddRow

                if not tick in data.index:
                    continue
                if not pd.isna(data.loc[tick,'size_bid']) and data.loc[tick,'size_bid'] > 0:
                    bidRect.setLeft(-data.loc[tick,'size_bid'])
                    #print('BID', tick, data.loc[tick, 'size_bid'], tickStep, bidRect)
                    alpha = data.loc[tick,'size_bid'] / max(data['size_bid'])
                    alpha = alpha*0.6+0.4
                    color = QColor(COLOR_GREEN)
                    color.setAlphaF(alpha)
                    p.fillRect(bidRect, QBrush(color))
                if not pd.isna(data.loc[tick,'size_ask']) and data.loc[tick,'size_ask'] > 0:
                    askRect.setRight(data.loc[tick,'size_ask'])
                    #print('ASK', tick, data.loc[tick, 'size_ask'], tickStep, askRect)
                    alpha = data.loc[tick,'size_ask'] / max(data['size_ask'])
                    alpha = alpha*0.6+0.4
                    color = QColor(COLOR_RED)
                    color.setAlphaF(alpha)
                    p.fillRect(askRect, QBrush(color))

        #horizontal lines
        """
        for tick in ticks:
            lineStart = QPointF(boundingRect.left(), tick+(tickStep/2))
            lineEnd = QPointF(boundingRect.right(), tick+(tickStep/2))
            p.drawLine(lineStart, lineEnd)
        """

        #vertical line
        #p.drawLine(QPointF(0, boundingRect.top()), QPointF(0, boundingRect.bottom()))

        p.end()

    def tickValues(self, minVal, maxVal, size=0):
        screenHeight = self.getViewWidget().rect().height()
        textHeight = 15
        maxTicks = math.floor(screenHeight / textHeight)
        range = abs(maxVal-minVal)
        tickStep = Decimal(1)
        for stepValue in [1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001, 0.0005, 0.0002, 0.0001]:
            if range/maxTicks < stepValue:
                tickStep = Decimal(stepValue)
        maxTick = math.floor(Decimal(maxVal)/tickStep)*tickStep
        minTick = math.ceil(Decimal(minVal)/tickStep)*tickStep

        def safe_arange(start, stop, step):
            return step * np.arange(start / step, stop / step)

        ticks = list(safe_arange(minTick, maxTick+tickStep, tickStep))
        return [(tickStep, ticks)]

    def setBookData(self, bookData):
        self.bookData = bookData
