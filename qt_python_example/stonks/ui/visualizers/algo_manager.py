from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from ...strategy import available_strategies
from .base import BaseVisualizer
from ...algo_manager import AlgoManager

class AlgoManagerWidget(BaseVisualizer):
    name = "Algo Manager"
    def __init__(self, parent, brokerApi):
        BaseVisualizer.__init__(self, parent)
        self.brokerApi = brokerApi
        self.tickerWidget = parent
        self.algoManager = AlgoManager(self.brokerApi)
        self.vl = QVBoxLayout(self)
        self.setLayout(self.vl)
        self.titleLabel = QLabel("{}".format(self.algoManager.liveEngine.balance))
        self.vl.addWidget(self.titleLabel)
        self.strategyList = StrategyList(self)
        self.vl.addWidget(self.strategyList)
        self.startStopBtn = QPushButton("Start", self)
        self.startStopBtn.clicked.connect(self.toggleLiveEngine)
        self.vl.addWidget(self.startStopBtn)
        self.forceEntryBtn = QPushButton("Force Entry Signal", self)
        self.forceEntryBtn.clicked.connect(self.forceEntry)
        self.vl.addWidget(self.forceEntryBtn)

        self.algoManager.liveEngine.accountBalanceChanged.connect(self.updateBalance)

    def toggleLiveEngine(self):
        if self.algoManager.liveEngine.active:
            self.algoManager.liveEngine.stop()
            self.startStopBtn.setText("Start")
        else:
            self.algoManager.liveEngine.forceActiveSymbol(self.tickerWidget.ticker_name)
            self.algoManager.liveEngine.start()
            self.startStopBtn.setText("Stop")

    def updateBalance(self, newBalance):
        self.titleLabel.setText("{}".format(newBalance))

    def forceEntry(self):
        le = self.algoManager.liveEngine
        le.onEntrySignal(self.tickerWidget.ticker_name, le.strategies[0])

class StrategyList(QTableWidget):
    def __init__(self, parent=None):
        QTableWidget.__init__(self, parent)
        self.setColumnCount(1)
        self.setRowCount(len(available_strategies()))
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        for row, strategy in enumerate(available_strategies()):
            print('available strategy: ', strategy, strategy.name)
            nameItem = QTableWidgetItem(strategy.name)
            self.setItem(row, 0, nameItem)
