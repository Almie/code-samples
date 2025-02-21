from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from .common import PdDateTimeEdit
import pandas as pd
import pyqtgraph as pg

class DataManager(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.vl = QVBoxLayout(self)
        self.setLayout(self.vl)

        self.topBarHl = QHBoxLayout(self)
        self.vl.addLayout(self.topBarHl)
        
        self.symbolSetTypeLabel = QLabel("Symbol Set:")
        self.topBarHl.addWidget(self.symbolSetTypeLabel)
        self.symbolSetDropdown = QComboBox(self)
        self.symbolSetDropdown.addItems(['Index', 'Single Stock'])
        self.topBarHl.addWidget(self.symbolSetDropdown)

        self.singleStockLabel = QLabel("Symbol: ")
        self.topBarHl.addWidget(self.singleStockLabel)
        self.singleStockText = QLineEdit("SPY")
        self.topBarHl.addWidget(self.singleStockText)

        self.indexLabel = QLabel("Index: ")
        self.topBarHl.addWidget(self.indexLabel)
        self.indexDropdown = QComboBox(self)
        self.indexDropdown.addItems(['S&P 500', 'Russell 2000', 'All listed stocks & ETFs'])
        self.topBarHl.addWidget(self.indexDropdown)

        self.dataTypeLabel = QLabel("Data Type: ")
        self.topBarHl.addWidget(self.dataTypeLabel)
        self.dataTypeDropdown = QComboBox(self)
        self.dataTypeDropdown.addItems(['Fundamentals', 'Bar Data'])
        self.topBarHl.addWidget(self.dataTypeDropdown)

        self.topBarHl.addStretch()

        self.startDateLabel = QLabel('Start Date: ')
        self.topBarHl.addWidget(self.startDateLabel)
        self.startDateEdit = PdDateTimeEdit(self, pd.Timestamp.now().floor(freq="D") - pd.Timedelta('30D'))
        self.topBarHl.addWidget(self.startDateEdit)

        self.endDateLabel = QLabel('End Date: ')
        self.topBarHl.addWidget(self.endDateLabel)
        self.endDateEdit = PdDateTimeEdit(self, pd.Timestamp.now().floor(freq="D"))
        self.topBarHl.addWidget(self.endDateEdit)

        self.dataVisualizer = pg.PlotWidget(self)
        self.vl.addWidget(self.dataVisualizer)
