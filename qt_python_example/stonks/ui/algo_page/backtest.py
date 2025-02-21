from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *

from ...algo_manager.backtest_engine import BacktestEngine
from ...algo_manager.commissions import available_calc_types
from ...strategy import available_strategies

from ..common import PdDateTimeEdit

import pandas as pd
from decimal import Decimal

class AlgoPageStrategySelect(QComboBox):
    def __init__(self, parent):
        QComboBox.__init__(self, parent)
        self.strategies = available_strategies()
        strategyNames = [strategy.name for strategy in self.strategies]
        self.addItems(strategyNames)
        self.setEditable(True)
        self.completer = QCompleter(strategyNames, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.setCompleter(self.completer)

    @property
    def selectedStrategy(self):
        for strategy in self.strategies:
            if strategy.name == self.currentText():
                return strategy
        return None

class NewBacktestDialog(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.vl = QVBoxLayout(self)
        self.setLayout(self.vl)

        self.backtestParamBox = QGroupBox(self)
        self.fl = QFormLayout(self)
        self.backtestParamBox.setLayout(self.fl)
        self.vl.addWidget(self.backtestParamBox)

        self.strategySelect = AlgoPageStrategySelect(self)
        self.strategy = self.strategySelect.selectedStrategy
        self.strategySelect.currentIndexChanged.connect(self.strategySelected)
        self.fl.addRow("Strategy", self.strategySelect)

        self.balanceEdit = QLineEdit("10000")
        self.fl.addRow("Starting Balance", self.balanceEdit)

        self.symbolsEdit = QLineEdit("SPY")
        self.fl.addRow("Symbols", self.symbolsEdit)

        self.startTimeEdit = PdDateTimeEdit(self, pd.Timestamp.now().floor(freq="D") - pd.Timedelta('30D'))
        self.fl.addRow("Start Time", self.startTimeEdit)

        self.endTimeEdit = PdDateTimeEdit(self, pd.Timestamp.now().floor(freq="D"))
        self.fl.addRow("End Time", self.endTimeEdit)

        self.commissionCalcType = QComboBox(self)
        self.commissionCalcType.addItems(list(available_calc_types.keys()))
        self.fl.addRow("Commission Calculation", self.commissionCalcType)

        self.strategyParamBox = QGroupBox(self)
        self.strategyParamFl = QFormLayout(self)
        self.strategyParamBox.setLayout(self.strategyParamFl)
        self.vl.addWidget(self.strategyParamBox)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.vl.addWidget(self.buttonBox)

    def strategySelected(self, index):
        self.strategy = self.strategySelect.selectedStrategy
        self.updateStrategyParams()

    def updateStrategyParams(self):
        if self.strategyParamFl.rowCount() > 0:
            self.clearStrategyParams()
        if self.strategy is None:
            return
        for parameter in self.strategy.parameters():
            if parameter.value_choices:
                paramWidget = QComboBox()
                paramWidget.addItems([str(opt) for opt in parameter.value_choices])
                paramWidget.setCurrentText(str(parameter.default_value))
                paramWidget.text = paramWidget.currentText
                paramWidget.setText = paramWidget.setCurrentText
            else:
                paramWidget = QLineEdit(str(parameter.default_value))
            paramWidget.param_name = parameter.name
            self.strategyParamFl.addRow(parameter.display_name, paramWidget)
        for param_name, option in self.strategy.get_indicator_params().items():
            if option.value_choices:
                paramWidget = QComboBox()
                paramWidget.addItems([str(opt) for opt in option.value_choices])
                paramWidget.setCurrentText(str(option.value))
                paramWidget.text = paramWidget.currentText
                paramWidget.setText = paramWidget.setCurrentText
            else:
                paramWidget = QLineEdit(str(option.value))
            paramWidget.param_name = param_name
            self.strategyParamFl.addRow(param_name, paramWidget)

    def clearStrategyParams(self):
        while ((child := self.strategyParamFl.takeRow(0)) != None):
            child.widget().deleteLater()
            del child

    def getStrategyParams(self):
        params = {}
        rowCount = self.strategyParamFl.rowCount()
        for row in range(rowCount):
            paramItem = self.strategyParamFl.itemAt(row, QFormLayout.FieldRole)
            if not paramItem:
                continue
            paramWidget = paramItem.widget()
            params[paramWidget.param_name] = str(paramWidget.text())
        return params

    @property
    def parameters(self):
        return {
                'strategy': self.strategy(**self.getStrategyParams()),
                'balance': Decimal(self.balanceEdit.text()),
                'symbols': str(self.symbolsEdit.text()).replace(' ', '').split(','),
                'startTime': self.startTimeEdit.getPdTimestamp(),
                'endTime': self.endTimeEdit.getPdTimestamp(),
                'commissionType': available_calc_types[str(self.commissionCalcType.currentText())]
                }

    @staticmethod
    def getInputParameters(parent=None):
        newBacktestDialog = NewBacktestDialog(parent)
        newBacktestDialog.updateStrategyParams()
        result = newBacktestDialog.exec_()
        if result:
            return newBacktestDialog.parameters
        else:
            return None

class BacktestProgressDialog(QDialog):
    loadLog = Signal(str)
    def __init__(self, backtestParams, parent=None):
        QDialog.__init__(self, parent)
        print('BACKTEST PARAMS', backtestParams)
        self.setWindowTitle('Backtesting Strategy {}'.format(backtestParams['strategy'].name))
        self.backtestEngine = BacktestEngine(**backtestParams)
        self.backtestEngine.progressMsg.connect(self.updateProgressMsg)
        self.backtestEngine.finished.connect(self.backtestFinished)

        self.vl = QVBoxLayout(self)
        self.setLayout(self.vl)

        self.infoLabel = QLabel("Backtest in progress...")
        self.vl.addWidget(self.infoLabel)

        self.progressBar = QProgressBar(self)
        self.progressBar.setRange(0, 1)
        self.progressBar.setValue(0.5)
        self.progressBar.setFormat("Doing stuff - %p%")
        self.vl.addWidget(self.progressBar)

        self.finishedButtonBox = QDialogButtonBox(self)
        self.finishedButtonBox.addButton("OK", QDialogButtonBox.RejectRole)
        self.finishedButtonBox.addButton("View Results", QDialogButtonBox.AcceptRole)
        self.finishedButtonBox.accepted.connect(self.viewResults)
        self.finishedButtonBox.rejected.connect(self.close)
        self.vl.addWidget(self.finishedButtonBox)
        self.finishedButtonBox.hide()

        self.logPath = ""

    def start(self):
        self.show()
        self.backtestEngine.start()

    def updateProgressMsg(self, msg):
        self.progressBar.setFormat('{} - %p%'.format(msg))

    def updateProgressNumber(self, val):
        self.progressBar.setValue(val)

    def backtestFinished(self, logPath):
        self.infoLabel.setText("Backtest finished!")
        self.finishedButtonBox.show()
        self.logPath = logPath

    def viewResults(self):
        self.loadLog.emit(self.logPath)
        self.close()

