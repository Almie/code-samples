from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *

from .backtest import NewBacktestDialog, BacktestProgressDialog
from .dashboard import AlgoPageDashboard

import os
import json

class AlgoPage(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        #self.vl = QVBoxLayout(self)
        self.mainHl = QHBoxLayout(self)
        self.mainHl.setContentsMargins(20,20,20,20)
        self.mainHl.setSpacing(0)
        self.setLayout(self.mainHl)

        #self.topRow = QWidget(self)
        #self.topHl = QHBoxLayout(self.topRow)
        #self.topHl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        #self.topHl.setSpacing(50)
        #self.topRow.setLayout(self.topHl)
        #self.vl.addWidget(self.topRow)

        #self.strategySelect = AlgoPageStrategySelect(self)
        #self.topHl.addWidget(self.strategySelect)

        #self.mainRow = QWidget(self)
        #self.mainRow.setLayout(self.mainHl)
        #self.vl.addWidget(self.mainRow)

        self.leftColumn = QWidget(self)
        self.leftColumn.setMaximumWidth(250)
        self.leftVl = QVBoxLayout(self.leftColumn)
        self.leftVl.setContentsMargins(0,0,0,0)
        self.leftVl.setSpacing(0)
        self.leftColumn.setLayout(self.leftVl)
        self.mainHl.addWidget(self.leftColumn)

        self.leftColumnTitleRow = QWidget(self)
        self.leftColumnTitleHl = QHBoxLayout(self.leftColumnTitleRow)
        self.leftColumnTitleHl.setContentsMargins(15,0,0,0)
        self.leftColumnTitleHl.setSpacing(0)
        self.leftColumnTitleRow.setLayout(self.leftColumnTitleHl)
        self.leftVl.addWidget(self.leftColumnTitleRow)

        self.tradeLogsLabel = QLabel('Trade Logs')
        self.leftColumnTitleHl.addWidget(self.tradeLogsLabel)

        self.newBacktestBtn = QPushButton("New Backtest")
        self.newBacktestBtn.setMaximumWidth(150)
        self.newBacktestBtn.clicked.connect(self.newBacktest)
        self.leftColumnTitleHl.addWidget(self.newBacktestBtn)

        self.backtestLogList = AlgoPageBacktestLogList(self.leftColumn)
        self.backtestLogList.itemDoubleClicked.connect(self.loadLogFromList)
        self.leftVl.addWidget(self.backtestLogList)

        self.backtestPageTabWidget = QTabWidget(self)
        self.backtestPageTabWidget.setTabsClosable(True)
        self.backtestPageTabWidget.setMovable(True)
        self.backtestPageTabWidget.tabCloseRequested.connect(self.tabCloseRequested)
        self.backtestPageTabs = []
        self.mainHl.addWidget(self.backtestPageTabWidget)

    def newBacktest(self):
        backtestParams = NewBacktestDialog.getInputParameters(self)
        if not backtestParams:
            return
        print('NEW BACKTEST')
        self.backtestProgressDialog = BacktestProgressDialog(backtestParams)
        self.backtestProgressDialog.loadLog.connect(self.loadLog)
        self.backtestProgressDialog.start()

    def loadLogFromList(self, item, column):
        if not item:
            return
        if not hasattr(item, "logPath"):
            return
        self.loadLog(item.logPath)

    def loadLog(self, logPath):
        for i in range(self.backtestPageTabWidget.count()):
            dashboard = self.backtestPageTabWidget.widget(i)
            if logPath == dashboard.logPath:
                self.backtestPageTabWidget.setCurrentIndex(i)
                return
        try:
            sourcePath = logPath.replace(".csv", ".py")
            metaPath = logPath.replace(".csv", ".json")
            with open(metaPath, 'r') as f:
                metaObj = json.load(f)
            backtestDashboard = AlgoPageDashboard(self, logPath, sourcePath, **metaObj)
            self.backtestPageTabs.append(backtestDashboard)
            self.backtestPageTabWidget.addTab(backtestDashboard, os.path.basename(logPath))
            self.backtestPageTabWidget.setCurrentWidget(backtestDashboard)
        except:
            import traceback
            ok = QMessageBox.critical(self, "Error", f"Error loading log {logPath}:\n{traceback.format_exc()}", QMessageBox.Ok)

    def tabCloseRequested(self, index):
        self.backtestPageTabWidget.widget(index).deleteLater()
        self.backtestPageTabWidget.removeTab(index)

class AlgoPageBacktestLogList(QTreeWidget):
    BACKTEST_LOGS_FOLDER = "%LOCALAPPDATA%\\StonX\\backtests"
    def __init__(self, parent):
        QTreeWidget.__init__(self, parent)
        self.setMaximumWidth(250)
        self.header().hide()
        logFolder = os.path.expandvars(self.BACKTEST_LOGS_FOLDER)
        strategies = os.listdir(logFolder)
        self.strategyItems = []
        for strategy in strategies:
            strategyItem = QTreeWidgetItem([strategy])
            self.strategyItems.append(strategyItem)
            self.invisibleRootItem().addChild(strategyItem)
            strategyFolder = os.path.join(logFolder, strategy)
            for date in os.listdir(strategyFolder):
                dateFolder = os.path.join(strategyFolder, date)
                for log in [p for p in os.listdir(dateFolder) if p.endswith('.csv')]:
                    logItem = QTreeWidgetItem([log])
                    logPath = os.path.join(dateFolder, log)
                    logItem.logPath = logPath
                    strategyItem.addChild(logItem)
