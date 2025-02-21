from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from pyqtgraph.dockarea import Dock
import pandas as pd
from ..config import Config

class VisToggle(QCheckBox):
    def __init__(self, parent=None):
        QCheckBox.__init__(self, "", parent)
        self.setProperty("visToggle", "yes")

class ColorPicker(QPushButton):
    def __init__(self, color="#FFFFFF", parent=None):
        QPushButton.__init__(self, parent)
        self.setColor(color)
        self.clicked.connect(self.onClicked)

    def setColor(self, color):
        self.color = color
        self.setStyleSheet("QPushButton{{background-color:{}}}".format(color))

    def onClicked(self):
        newColor = QColorDialog.getColor(QColor(self.color), self, "Choose Color", QColorDialog.ShowAlphaChannel)
        if newColor.isValid():
            self.setColor(newColor.name(QColor.HexArgb))

class PdDateTimeEdit(QDateTimeEdit):
    def __init__(self, parent=None, default_value=pd.Timestamp.now().floor(freq="D")):
        QDateTimeEdit.__init__(self, parent)
        self.config = Config()
        self.setCalendarPopup(True)
        self.setDisplayFormat("yyyy-MM-dd hh:mm:ss")
        self.setDateTime(QDateTime.fromString(default_value.strftime("%Y-%m-%d %H:%M:%S"), "yyyy-MM-dd hh:mm:ss"))

    def getPdTimestamp(self):
        self.twsTimezone = self.config.get_property("timezone_tws", "US/Pacific")
        return pd.Timestamp(self.dateTime().toString("yyyy-MM-dd hh:mm:ss"), tz=self.twsTimezone)

class MyDock(Dock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nStyle = """
        Dock > QWidget {
            border: 0;
        }"""
        if kwargs.get("disableDrops", False):
            self.allowedAreas = []