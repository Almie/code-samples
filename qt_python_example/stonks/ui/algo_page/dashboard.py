from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *

from ...config import Config

from .utils import PythonHighlighter

import pyqtgraph as pg
import pandas as pd

COLOR_GREEN = "#26A69A"
COLOR_GREEN_HOVER = "#76ded4"
COLOR_RED = "#EF5350"
COLOR_RED_HOVER = "#ff8c8a"
COLOR_BG = "#151924"

class AlgoPageDashboard(QScrollArea):
    def __init__(self, parent, logPath, sourcePath, strategyName, startTime, endTime, startingBalance, symbols, backtestDate, strategyParams, indicatorParams):
        QScrollArea.__init__(self, parent)
        self.setAttribute(Qt.WA_StyledBackground)
        self.mainWidget = QWidget(self)
        self.mainWidget.setObjectName('dashboardWidget')
        self.mainVl = QVBoxLayout(self.mainWidget)
        self.mainVl.setContentsMargins(25,25,25,25)
        self.mainVl.setSpacing(35)
        self.mainWidget.setLayout(self.mainVl)

        self.config = Config()
        self.twsTimezone = self.config.get_property("timezone_tws", "US/Pacific")

        self.logPath = logPath
        self.sourcePath = sourcePath
        self.strategyName = strategyName
        try:
            logData = pd.read_csv(logPath, index_col=0, parse_dates=[0], infer_datetime_format=True)
        except pd.errors.EmptyDataError:
            self.errorLabel = QLabel("Error reading log: {}".format(logPath))
            self.mainVl.addWidget(self.errorLabel)
            self.setWidget(self.mainWidget)
        if not isinstance(logData.index, pd.DatetimeIndex):
            logData.index = pd.to_datetime(logData.index, utc=True)
        logData.index = logData.index.tz_convert(self.twsTimezone)

        self.titleRow = QWidget(self)
        self.titleHl = QHBoxLayout(self.titleRow)
        self.titleHl.setContentsMargins(0,0,0,0)
        self.titleRow.setLayout(self.titleHl)
        self.mainVl.addWidget(self.titleRow)

        self.titleBox = QWidget(self)
        self.titleBoxVl = QVBoxLayout(self.titleBox)
        self.titleBoxVl.setContentsMargins(0,0,0,0)
        self.titleBoxVl.setSpacing(0)
        self.titleBox.setLayout(self.titleBoxVl)
        self.titleHl.addWidget(self.titleBox)

        self.titleLabel = QLabel(strategyName)
        self.titleLabel.setObjectName('titleLabel')
        self.titleBoxVl.addWidget(self.titleLabel)
        self.backtestDateLabel = QLabel("backtested on {}".format(pd.Timestamp(backtestDate).strftime("%d %b %Y")))
        self.titleBoxVl.addWidget(self.backtestDateLabel)

        self.titleHl.addStretch()

        self.sourceDialog = None
        self.btnViewSource = QPushButton("View Source Code")
        self.btnViewSource.clicked.connect(self.viewSource)
        self.titleHl.addWidget(self.btnViewSource)

        self.highlightsRow = QWidget(self)
        self.highlightsHl = QHBoxLayout(self)
        self.highlightsHl.setContentsMargins(0,0,0,0)
        self.highlightsHl.setSpacing(35)
        self.highlightsHl.setAlignment(Qt.AlignLeft)
        self.highlightsRow.setLayout(self.highlightsHl)
        self.mainVl.addWidget(self.highlightsRow)

        netProfit = logData["balance"][-1] - logData["balance"][0]
        netProfitPercent = netProfit / logData["balance"][0] * 100
        lengthOfTest = logData.index[-1] - logData.index[0]
        if lengthOfTest < pd.Timedelta('1d'):
            lengthRounded = lengthOfTest.round(freq='1H').total_seconds() / 3600
            lengthStr = "over {} hours".format(lengthRounded)
        else:
            lengthRounded = lengthOfTest.round(freq='1D').total_seconds() / 86400
            lengthStr = "over {} days".format(lengthRounded)

        netProfitColor = COLOR_GREEN if netProfitPercent > 0 else COLOR_RED
        self.netProfitBox = AlgoPageHighlightBox(self, "Net Profit", f'{netProfitPercent:.2f}%', lengthStr, mainColor=netProfitColor)
        self.highlightsHl.addWidget(self.netProfitBox)

        wins = 0
        total_trades = logData[logData["action"] == "exit"]["balance"].size
        prevBalance = logData["balance"][0]
        for exit in logData[logData["action"] == "exit"]["balance"].tolist():
            if exit > prevBalance:
                wins += 1
            prevBalance = exit
        if total_trades > 0:
            winRate = float(wins) / total_trades * 100
        else:
            winRate = 0

        winRateColor = COLOR_GREEN if winRate > 50 else COLOR_RED
        self.winrateBox = AlgoPageHighlightBox(self, "Winrate", f'{winRate:.2f}%', f'over {total_trades} trades', mainColor=winRateColor)
        self.highlightsHl.addWidget(self.winrateBox)

        cumMax = logData[logData["action"] == "exit"]["balance"].cummax()
        drawdowns = logData[logData["action"] == "exit"]["balance"] - cumMax
        drawdownsPercent = drawdowns / cumMax * 100
        maxDrawdown = drawdowns.min()
        maxDrawdownPercent = drawdownsPercent.min()
        totalCommissions = logData["commission"].sum()

        self.maxDrawdownBox = AlgoPageHighlightBox(self, "Max Drawdown %", f'{maxDrawdownPercent:.2f}%', "", mainColor=COLOR_RED)
        self.highlightsHl.addWidget(self.maxDrawdownBox)

        self.mainRow = QWidget(self)
        self.mainHl = QHBoxLayout(self.mainRow)
        self.mainHl.setContentsMargins(0,0,0,0)
        self.mainHl.setSpacing(35)
        self.mainRow.setLayout(self.mainHl)
        self.mainVl.addWidget(self.mainRow)

        self.leftColumn = QWidget(self)
        self.leftVl = QVBoxLayout(self.leftColumn)
        self.leftVl.setContentsMargins(0,0,0,0)
        self.leftVl.setSpacing(35)
        self.leftColumn.setLayout(self.leftVl)
        self.mainHl.addWidget(self.leftColumn)

        self.paramsBox = AlgoPageBox(self, "Parameters")
        self.leftVl.addWidget(self.paramsBox)

        paramsObj = {**strategyParams,**indicatorParams}
        self.paramsTable = AlgoPageStaticTable(self, paramsObj)
        self.paramsTable.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.paramsBox.addWidget(self.paramsTable)

        self.btnWedgeParams = QPushButton("Run parameter wedge test")
        self.btnWedgeParams.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btnWedgeParams.setEnabled(False)
        self.paramsBox.addWidget(self.btnWedgeParams)
        self.paramsBox.setAlignment(self.btnWedgeParams, Qt.AlignRight)

        self.detailsBox = AlgoPageBox(self, "Details")
        self.leftVl.addWidget(self.detailsBox)

        detailsObj = {'Starting Balance' : f'{logData["balance"][0]:.2f}',
                        'Final Balance' : f'{logData["balance"][-1]:.2f}',
                        'Net Profit': f'{netProfit:.2f}',
                        'Net Profit %': f'{netProfitPercent:.2f}%',
                        'Max Drawdown': f'{maxDrawdown:.2f}',
                        'Max Drawdown %' : f'{maxDrawdownPercent:.2f}%',
                        'Total Commissions:' : f'{totalCommissions:.2f}',
                        'Start Date' : pd.Timestamp(startTime).strftime('%Y-%m-%d %H:%M:%S'),
                        'End Date' : pd.Timestamp(endTime).strftime('%Y-%m-%d %H:%M:%S'),
                        'Symbols Traded' : ', '.join(symbols)}

        self.detailsTable = AlgoPageStaticTable(self, detailsObj)
        self.detailsTable.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.detailsBox.addWidget(self.detailsTable)

        self.rightColumn = QWidget(self)
        self.rightVl = QVBoxLayout(self.rightColumn)
        self.rightVl.setContentsMargins(0,0,0,0)
        self.rightColumn.setLayout(self.rightVl)
        self.mainHl.addWidget(self.rightColumn)

        self.equityBox = AlgoPageBox(self, "Equity Curve")
        self.equityChart = EquityChart(logData[logData["action"]!="entry"]["balance"])
        self.equityChart.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.equityBox.addWidget(self.equityChart)
        self.rightVl.addWidget(self.equityBox)

        self.tradesListBox = AlgoPageBox(self, "Trades")
        self.mainVl.addWidget(self.tradesListBox)

        self.tradesListTable = AlgoPageTradesTable(self, logData)
        self.tradesListBox.addWidget(self.tradesListTable)

        self.setWidgetResizable(True)
        self.setWidget(self.mainWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def viewSource(self):
        if not self.sourceDialog:
            self.sourceDialog = AlgoPageViewSourceDialog(self, self.strategyName, self.sourcePath)
        self.sourceDialog.show()


class AlgoPageBox(QWidget):
    def __init__(self, parent, title):
        QWidget.__init__(self, parent)
        self.setAttribute(Qt.WA_StyledBackground)
        self.mainVl = QVBoxLayout(self)
        self.setLayout(self.mainVl)

        self.titleLabel = QLabel(title)
        self.titleLabel.setObjectName('titleLabel')
        self.mainVl.addWidget(self.titleLabel)

        self.addWidget = self.mainVl.addWidget
        self.setAlignment = self.mainVl.setAlignment

class AlgoPageHighlightBox(AlgoPageBox):
    def __init__(self, parent, title, mainText, secondaryText, icon=None, mainColor='#D3D3D3'):
        AlgoPageBox.__init__(self, parent, title)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.mainLabel = QLabel(mainText)
        self.mainLabel.setStyleSheet(f'QLabel{{color:{mainColor};}}')
        self.mainLabel.setObjectName('mainLabel')
        self.addWidget(self.mainLabel)

        self.secondaryLabel = QLabel(secondaryText)
        self.secondaryLabel.setObjectName('secondaryLabel')
        self.addWidget(self.secondaryLabel)

class AlgoPageStaticTable(QTableWidget):
    def __init__(self, parent, data):
        QTableWidget.__init__(self, parent)
        self.setColumnCount(2)
        self.verticalHeader().hide()
        self.horizontalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.setShowGrid(False)
        self.setRowCount(len(data.keys()))
        for i, key in enumerate(data.keys()):
            keyItem = QTableWidgetItem(key)
            keyItem.setFlags(Qt.NoItemFlags)
            keyItem.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            valueItem = QTableWidgetItem(str(data[key]))
            valueItem.setFlags(Qt.NoItemFlags)
            valueItem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(i, 0, keyItem)
            self.setItem(i, 1, valueItem)
        self.updateSize()

    def updateSize(self):
        w = 4
        for i in range(self.columnCount()):
            w += self.columnWidth(i)
        h = 4
        for i in range(self.rowCount()):
            h += self.rowHeight(i)
        size = QSize(w, h)
        self.setMinimumSize(size)
        #self.setMaximumSize(size)

class AlgoPageTradesTable(QTableWidget):
    def __init__(self, parent, logData):
        QTableWidget.__init__(self, parent)
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels(["Time", "Action", "Symbol", "Amount", "Price", "Commission", "Balance"])
        self.verticalHeader().hide()
        self.setRowCount(logData[logData["action"]!="start"].shape[0]-1)

        for row, date in enumerate(logData.index):
            if logData.loc[date,"action"]=="start":
                continue
            timeItem = QTableWidgetItem(date.strftime('%Y-%m-%d %H:%M:%S'))
            timeItem.setFlags(Qt.NoItemFlags)
            self.setItem(row-1, 0, timeItem)
            actionItem = QTableWidgetItem(str(logData.loc[date,"action"]))
            actionItem.setFlags(Qt.NoItemFlags)
            self.setItem(row-1, 1, actionItem)
            symbolItem = QTableWidgetItem(str(logData.loc[date,"symbol"]))
            symbolItem.setFlags(Qt.NoItemFlags)
            self.setItem(row-1, 2, symbolItem)
            amountItem = QTableWidgetItem(str(logData.loc[date,"amount"]))
            amountItem.setFlags(Qt.NoItemFlags)
            self.setItem(row-1, 3, amountItem)
            priceItem = QTableWidgetItem(str(logData.loc[date,"price"]))
            priceItem.setFlags(Qt.NoItemFlags)
            self.setItem(row-1, 4, priceItem)
            if not "commission" in logData.columns:
                commission = 0
            else:
                commission= logData.loc[date,"commission"]
            commissionItem = QTableWidgetItem(str(commission))
            commissionItem.setFlags(Qt.NoItemFlags)
            self.setItem(row-1, 5, commissionItem)
            balanceItem = QTableWidgetItem(str(logData.loc[date,"balance"]))
            balanceItem.setFlags(Qt.NoItemFlags)
            self.setItem(row-1, 6, balanceItem)
        self.updateSize()

    def updateSize(self):
        w = 4
        for i in range(self.columnCount()):
            w += self.columnWidth(i)
        h = 4
        for i in range(self.rowCount()):
            h += self.rowHeight(i)
        size = QSize(w, h)
        self.setMinimumSize(size)
        #self.setMaximumSize(size)

class MyPlotCurveItem(pg.PlotCurveItem):

    def paint(self, p, opt, widget):
        import pdb; pdb.set_trace()
        pg.PlotCurveItem.paint(self, p, opt, widget)

    def _getFillPathList(self):
        import pdb; pdb.set_trace()

    def _getFillPath(self):
        if self.fillPath is not None:
            return self.fillPath

        path = QPainterPath(self.getPath())
        self.fillPath = path
        if self.opts['fillLevel'] == 'enclosed':
            return path

        baseline = self.opts['fillLevel']
        x, y = self.getData()
        import pdb; pdb.set_trace()
        lx, rx = x[[0, -1]]
        ly, ry = y[[0, -1]]

        if ry != baseline:
            path.lineTo(rx, baseline)
        path.lineTo(lx, baseline)
        if ly != baseline:
            path.lineTo(lx, ly)

class EquityChart(pg.PlotWidget):
    def __init__(self, equitySeries):
        pg.PlotWidget.__init__(self)
        self.setBackground('#1F2433')
        self.curveItem = pg.PlotDataItem()
        colorMapPen = pg.ColorMap([0.0, 1.0], [COLOR_RED, COLOR_GREEN])
        colorMapBrush = pg.ColorMap([0.0, 1.0], [COLOR_RED+'44', COLOR_GREEN+'44'])
        gradientPen = colorMapPen.getPen(span=(equitySeries[0]-0.05,equitySeries[0]+0.05), width=2)
        #gradientBrush = colorMapBrush.getBrush(span=(equitySeries[0]-0.05,equitySeries[0]+0.05))
        gradient = QLinearGradient(QPointF(0.,equitySeries[0]-0.05), QPointF(0.,equitySeries[0]+0.05))
        gradient.setColorAt(0.0, QColor(COLOR_RED))
        gradient.setColorAt(1.0, QColor(COLOR_GREEN))
        gradientBrush = QBrush(gradient)
        self.curveItem.setPen(gradientPen)
        self.curveItem.setData([index.timestamp() for index in equitySeries.index], equitySeries.tolist(),
                                fillLevel=equitySeries[0], brush=gradientBrush)#pg.mkBrush("#26A69A66")
        self.addItem(self.curveItem)
        self.setLimits(xMin=equitySeries.index[0].timestamp(),
                        xMax=equitySeries.index[-1].timestamp(),
                        yMin=equitySeries.min(),
                        yMax=equitySeries.max())

class AlgoPageViewSourceDialog(QDialog):
    def __init__(self, parent, strategyName, sourcePath):
        QDialog.__init__(self, parent)
        self.setWindowTitle(f'{strategyName} - Source Code | StonX')
        self.vl = QVBoxLayout(self)
        self.setLayout(self.vl)

        self.editor = AlgoPageViewSourceEdit(self)
        with open(sourcePath, 'r') as f:
            self.editor.setPlainText(f.read())
        self.vl.addWidget(self.editor)

        self.closeBtn = QPushButton("Close")
        self.closeBtn.setMaximumWidth(75)
        self.closeBtn.clicked.connect(self.close)
        self.vl.addWidget(self.closeBtn)
        self.vl.setAlignment(self.closeBtn, Qt.AlignRight)

        self.resize(1200, 800)

class AlgoPageViewSourceEdit(QPlainTextEdit):
    def __init__(self, parent):
        QPlainTextEdit.__init__(self, parent)
        self.lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

        self.highlighter = PythonHighlighter(self.document())
        self.setReadOnly(True)

    def lineNumberAreaWidth(self):
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num *= 0.1
            digits += 1

        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        width = self.lineNumberAreaWidth()
        rect = QRect(cr.left(), cr.top(), width, cr.height())
        self.lineNumberArea.setGeometry(rect)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), Qt.lightGray)
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        offset = self.contentOffset()
        top = self.blockBoundingGeometry(block).translated(offset).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(Qt.black)
                width = self.lineNumberArea.width()
                height = self.fontMetrics().height()
                painter.drawText(0, top, width, height, Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    @Slot()
    def updateLineNumberAreaWidth(self, newBlockCount):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    @Slot()
    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            width = self.lineNumberArea.width()
            self.lineNumberArea.update(0, rect.y(), width, rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    @Slot()
    def highlightCurrentLine(self):
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            line_color = QColor(Qt.yellow).lighter(160)
            selection.format.setBackground(line_color)

            selection.format.setProperty(QTextFormat.FullWidthSelection, True)

            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()

            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        QWidget.__init__(self, editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)
