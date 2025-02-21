from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from .base import BaseVisualizer

from decimal import Decimal

COLOR_GREEN = "#26A69A"
COLOR_RED = "#EF5350"

class PortfolioWidget(BaseVisualizer):
    name = "Portfolio"
    icon = ':/icons/portfolio.png'
    def __init__(self, parent, brokerApi):
        BaseVisualizer.__init__(self, parent)
        self.parentTicker = parent
        self.vl = QVBoxLayout(self)
        self.setLayout(self.vl)

        self.brokerApi = brokerApi

        self.balanceRow = QWidget(self)
        self.balanceGl = QGridLayout(self.balanceRow)
        self.balanceGl.setSpacing(0)
        self.balanceGl.setContentsMargins(0,0,0,0)
        self.balanceRow.setLayout(self.balanceGl)
        self.vl.addWidget(self.balanceRow)

        self.balanceLabel = QLabel('Cash Balance')
        self.balanceLabel.setProperty('smolText', True)
        self.balanceGl.addWidget(self.balanceLabel, 0, 0)
        self.balance = QLabel("0.0")
        self.balance.setProperty('bigText', True)
        self.balanceGl.addWidget(self.balance, 1, 0)

        self.netLiquidityLabel = QLabel('Net Liquidity')
        self.netLiquidityLabel.setProperty('smolText', True)
        self.balanceGl.addWidget(self.netLiquidityLabel, 0, 1)
        self.netLiquidity = QLabel("0.0")
        self.netLiquidity.setProperty('bigText', True)
        self.balanceGl.addWidget(self.netLiquidity, 1, 1)

        self.positionsTable = PositionsTable(self)
        self.positionsTable.itemDoubleClicked.connect(self.openChart)
        self.vl.addWidget(self.positionsTable)

        self.brokerApi.onManagedAccounts.connect(self.populateAccount)
        self.brokerApi.requestAccounts()
    
    def populateAccount(self, account):
        self.account = account
        self.brokerApi.subscribeToAccountUpdates(self.account, self.portfolioUpdate)
    
    def portfolioUpdate(self, portfolio):
        self.balance.setText(f'{portfolio.balanceCurrency} {portfolio.balance}')
        self.netLiquidity.setText(f'{portfolio.netLiquidityCurrency} {portfolio.netLiquidity}')
        self.currency = portfolio.balanceCurrency
        self.positionsTable.setData(portfolio.positions)
    
    def openChart(self, item):
        if not hasattr(item, 'symbol'):
            return
        self.parentTicker.setTicker(item.symbol)

class PositionsTable(QTableWidget):
    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        self.verticalHeader().hide()
        self.horizontalHeader().setSectionsClickable(True)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.setSortingEnabled(True)
    
    def setData(self, positions):
        self.setSortingEnabled(False)
        self.clear()
        positions = positions.copy()
        positions.index.name = 'symbol'
        positions = positions.reset_index(level=0)
        self.setRowCount(positions.shape[0])
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels(['Symbol', 'Pos', 'Cost', 'Profit', 'Profit%', 'Price', 'Value'])

        for row, row_data in positions.iterrows():
            symbolItem = QTableWidgetItem()
            symbolItem.setFlags(Qt.ItemIsEnabled)
            symbolItem.setData(Qt.EditRole, str(row_data['symbol']))
            symbolItem.symbol = str(row_data['symbol'])
            self.setItem(row, 0, symbolItem)
            posItem = QTableWidgetItem()
            posItem.setFlags(Qt.ItemIsEnabled)
            posItem.setData(Qt.EditRole, int(row_data['position']))
            posItem.setData(Qt.DisplayRole, f'x{row_data["position"]}')
            self.setItem(row, 1, posItem)
            costItem = QTableWidgetItem()
            costItem.setFlags(Qt.ItemIsEnabled)
            costItem.setData(Qt.EditRole, float(row_data["avgCost"]))
            costItem.setData(Qt.DisplayRole, f'@{float(row_data["avgCost"]):.2f}')
            self.setItem(row, 2, costItem)

            profitItem = QTableWidgetItem()
            profitItem.setFlags(Qt.ItemIsEnabled)
            profitItem.setData(Qt.EditRole, float(row_data["profit"]))
            profitItem.setData(Qt.DisplayRole, f'{float(row_data["profit"]):+.2f}')
            self.setItem(row, 3, profitItem)
            profitPercentItem = QTableWidgetItem()
            profitPercentItem.setFlags(Qt.ItemIsEnabled)
            profitPercentItem.setData(Qt.EditRole, float(row_data["profitPercent"]))
            profitPercentItem.setData(Qt.DisplayRole, f'{float(row_data["profitPercent"]):+.2f}%')
            self.setItem(row, 4, profitPercentItem)

            profit = float(row_data["profit"])
            color = COLOR_GREEN if profit > 0 else COLOR_RED
            if profit != 0:
                profitItem.setData(Qt.BackgroundRole, QColor(color))
                profitItem.setData(Qt.ForegroundRole, QColor("#FFFFFF"))
                profitPercentItem.setData(Qt.BackgroundRole, QColor(color))
                profitPercentItem.setData(Qt.ForegroundRole, QColor("#FFFFFF"))

            priceItem = QTableWidgetItem()
            priceItem.setFlags(Qt.ItemIsEnabled)
            priceItem.setData(Qt.EditRole, float(row_data["marketPrice"]))
            priceItem.setData(Qt.DisplayRole, f'{float(row_data["marketPrice"]):.2f}')
            self.setItem(row, 5, priceItem)
            valueItem = QTableWidgetItem()
            valueItem.setFlags(Qt.ItemIsEnabled)
            valueItem.setData(Qt.EditRole, float(row_data["marketValue"]))
            valueItem.setData(Qt.DisplayRole, f'{float(row_data["marketValue"]):.2f}')
            self.setItem(row, 6, valueItem)

        self.resizeColumnsToContents()
        self.horizontalHeader().setStretchLastSection(True)
        self.setSortingEnabled(True)
