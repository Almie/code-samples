from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *

from ..config import Config

from ..market_data.base import to_thread

from ..scanner import *

class StonkScanner(QWidget):
    scannerUpdated = Signal()
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.parentWidget = parent
        self.vl = QVBoxLayout(self)
        self.setLayout(self.vl)

        self.topRow = QWidget(self)
        self.topHl = QHBoxLayout(self)
        self.topRow.setLayout(self.topHl)
        self.vl.addWidget(self.topRow)

        self.topHl.addStretch()
        self.btnRefresh = QPushButton('Force Refresh')
        self.btnRefresh.setMaximumWidth(150)
        self.btnRefresh.clicked.connect(self.refresh)
        self.topHl.addWidget(self.btnRefresh)

        self.scannerTable = ScannerTable(self)
        self.scannerTable.itemDoubleClicked.connect(self.openChart)
        self.vl.addWidget(self.scannerTable)
        
        self.scanner_data = get_empty_scanner_dataframe()
        self.scannerTable.setData(self.scanner_data)
        self.scannerUpdated.connect(self.onScannerUpdated)
    
    #@to_thread
    def refresh(self):
        scanner_table = gather_data()
        filters = [
                    Filter('rsSpy_5m', '<', -2),
                    Filter('sma50', '<', 0),
                    Filter('sma100', '<', 0),
                    Filter('sma200', '<', 0),
                    Filter('rvol', '>=', 1)
                    ]
        filtered_table = filter_data(scanner_table, filters)
        self.scanner_data = filtered_table
        self.scannerUpdated.emit()
    
    def onScannerUpdated(self):
        self.scannerTable.setData(self.scanner_data)
    
    def openChart(self, item):
        if not hasattr(item, 'symbol'):
            return
        self.parentWidget.tabWidget.setCurrentIndex(0)
        self.parentWidget.ticker.setTicker(item.symbol)

class ScannerTable(QTableWidget):
    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        self.verticalHeader().hide()
        self.setSortingEnabled(True)
        self.horizontalHeader().setSectionsClickable(True)
        self.horizontalHeader().setSortIndicatorShown(True)

    def setData(self, scanner_data):
        self.setSortingEnabled(False)
        scanner_data.index.name = 'symbol'
        scanner_data = scanner_data.reset_index(level=0)
        columns = scanner_data.columns.tolist()
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        self.setRowCount(scanner_data.shape[0])

        for row, row_data in scanner_data.iterrows():
            for col, col_name in enumerate(columns):
                item = QTableWidgetItem()
                item.setData(Qt.EditRole, row_data[col_name])
                if col_name == 'symbol':
                    item.symbol = str(row_data[col_name])
                item.setFlags(Qt.ItemIsEnabled)
                self.setItem(row, col, item)
        self.setSortingEnabled(True)
