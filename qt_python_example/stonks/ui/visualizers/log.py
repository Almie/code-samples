from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from .base import BaseVisualizer

import logging

class GuiHandler(logging.Handler):
    def __init__(self, logger_name, log_signal):
        logging.Handler.__init__(self)
        self.logger_name = logger_name
        self._signal = log_signal

    def emit(self, record):
        self._signal.emit(self.logger_name, self.format(record))

class GuiLog(BaseVisualizer):
    name = "Log"
    icon = ':/icons/paper.png'
    logEntry = Signal(str, str)
    def __init__(self, ticker_name, parent=None):
        BaseVisualizer.__init__(self)
        self.vl = QVBoxLayout(self)
        self.setLayout(self.vl)

        self.tabWidget = QTabWidget(self)
        self.vl.addWidget(self.tabWidget)

        self.loggers = {}

        self.logEntry.connect(self.log)

        loggers = ['Market Data', 'Broker', 'UI', 'Backtest Engine', 'Live Engine', 'Indicators', 'Scanner']
        for logger_name in loggers:
            logger = logging.getLogger(logger_name)
            guiHandler = GuiHandler(logger_name, self.logEntry)
            #guiHandler.setLevel(logging.DEBUG)
            guiFormatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            guiHandler.setFormatter(guiFormatter)
            logger.addHandler(guiHandler)

    def getLog(self, name):
        if not name in self.loggers.keys():
            self.logEdit = QPlainTextEdit(self)
            self.logEdit.setReadOnly(True)
            self.tabWidget.addTab(self.logEdit, name)
            self.loggers[name] = self.logEdit
        return self.loggers[name]

    def log(self, log_name, entry):
        logEdit = self.getLog(log_name)
        scroll = logEdit.verticalScrollBar().value() == logEdit.verticalScrollBar().maximum()
        logEdit.appendPlainText(entry)
        if scroll:
            logEdit.ensureCursorVisible()
