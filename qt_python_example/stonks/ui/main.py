import os
from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtWinExtras import QtWin

from stonks.broker import BrokerAPI

from .ticker import StonkTicker
from .algo_page.main import AlgoPage
from .scanner import StonkScanner
from .data_manager import DataManager
from ..config import Config
from ..market_data import MarketData
from ..algo_manager import AlgoManager

import random

import win32api
import win32gui

from ctypes.wintypes import LONG, MSG

from win32con import WM_NCCALCSIZE, GWL_STYLE, WM_NCHITTEST, WS_MAXIMIZEBOX, WS_THICKFRAME, \
    WS_CAPTION, HTTOPLEFT, HTBOTTOMRIGHT, HTTOPRIGHT, HTBOTTOMLEFT, \
    HTTOP, HTBOTTOM, HTLEFT, HTRIGHT, HTCAPTION, WS_POPUP, WS_SYSMENU, WS_MINIMIZEBOX

class MaximizeBtn(QPushButton):
    def __init__(self):
        super().__init__()
        self.setProperty('maximized', 'yes')
        self.style().unpolish(self)
        self.style().polish(self)

class StonkTitleBar(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setObjectName('titleBar')
        self.setAttribute(Qt.WA_StyledBackground)
        self.parent = parent
        self.maximized = self.parent.windowState() & Qt.WindowMaximized
        self.clickPos = None
        self.hl = QHBoxLayout(self)
        self.hl.setSpacing(0)
        self.hl.setContentsMargins(15,0,0,0)
        self.setLayout(self.hl)

        self.titleLabel = QLabel('StonX')
        self.hl.addWidget(self.titleLabel)
        self.hl.addStretch()
        self.minimizeBtn = QPushButton()
        self.minimizeBtn.setObjectName('minimizeBtn')
        self.hl.addWidget(self.minimizeBtn)
        self.maximizeBtn = MaximizeBtn()
        self.maximizeBtn.setObjectName('maximizeBtn')
        self.maximizeBtn.setProperty('maximized', 'yes' if self.maximized else 'no')
        self.maximizeBtn.style().unpolish(self.maximizeBtn)
        self.maximizeBtn.style().polish(self.maximizeBtn)
        self.hl.addWidget(self.maximizeBtn)
        self.closeBtn = QPushButton()
        self.closeBtn.setObjectName('closeBtn')
        self.hl.addWidget(self.closeBtn)

        self.minimizeBtn.clicked.connect(self.minimize)
        self.maximizeBtn.clicked.connect(self.maximize)
        self.closeBtn.clicked.connect(self.parent.close)
    
    def minimize(self):
        self.parent.setWindowState(Qt.WindowMinimized)
    
    def maximize(self):
        self.parent.setWindowState(Qt.WindowNoState if self.maximized else Qt.WindowMaximized)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clickPos = event.windowPos().toPoint()

    def mouseMoveEvent(self, event):
        if self.clickPos is not None:
            self.window().move(event.globalPos() - self.clickPos)

    def mouseReleaseEvent(self, QMouseEvent):
        self.clickPos = None
    
    def mouseDoubleClickEvent(self, event):
        self.maximize()
        super().mouseDoubleClickEvent(event)

class StonkMainWindow(QMainWindow):
    BORDER_WIDTH = 5
    def __init__(self):
        super().__init__()
        #win32 stuff
        self.hwnd = self.winId().__int__()
        window_style = win32gui.GetWindowLong(self.hwnd, GWL_STYLE)
        win32gui.SetWindowLong(self.hwnd, GWL_STYLE, window_style | WS_POPUP | WS_THICKFRAME | WS_CAPTION | WS_SYSMENU
                                                                  | WS_MAXIMIZEBOX | WS_MINIMIZEBOX)

        if QtWin.isCompositionEnabled():
            # Aero Shadow
            QtWin.extendFrameIntoClientArea(self, -1, -1, -1, -1)
        else:
            QtWin.resetExtendedFrame(self)

        self.setWindowTitle("StonX")

        self.config = Config()

        self.api = MarketData()
        self.brokerApi = BrokerAPI("IBKR")
        self.brokerApi.connect("127.0.0.1", 7497)

        self.algoManager = AlgoManager(self.brokerApi)

        self.resize(1280, 800)

        self.mainWidget = QWidget(self)
        self.mainWidget.setObjectName('mainWidget')
        self.vl = QVBoxLayout(self)
        self.vl.setSpacing(0)
        self.vl.setContentsMargins(0,0,0,0)
        self.mainWidget.setLayout(self.vl)
        self.setCentralWidget(self.mainWidget)

        self.titleBar = StonkTitleBar(self)
        self.vl.addWidget(self.titleBar)
        self.tabWidget = QTabWidget(self)
        self.vl.addWidget(self.tabWidget)

        initialTicker = self.config.get_property("currentTicker", "F")
        self.ticker = StonkTicker(self, initialTicker, self.api, self.brokerApi)
        self.ticker.tickerChanged.connect(self.currentTickerChanged)
        self.tabWidget.addTab(self.ticker, f'Chart: {initialTicker}')

        self.algoPage = AlgoPage(self)
        self.tabWidget.addTab(self.algoPage, "Strategy Analysis")

        self.scannerPage = StonkScanner(self)
        self.tabWidget.addTab(self.scannerPage, "Scanner")

        self.dataManagerPage = DataManager(self)
        self.tabWidget.addTab(self.dataManagerPage, "Data Management")

        geoObj = self.config.get_property("windowGeometry", None)
        if geoObj:
            self.setGeometry(*geoObj)
        if self.config.get_property("windowMaximized", False):
            self.setWindowState(Qt.WindowMaximized)

    @Slot(str)
    def currentTickerChanged(self, new_ticker_name):
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.sender()), f'Chart: {new_ticker_name}')

    def moveEvent(self, event):
        #print(self.geometry(), self.frameGeometry())
        QMainWindow.moveEvent(self, event)

    def closeEvent(self, event):
        geo = self.geometry()
        geoObj = [geo.x(), geo.y(), geo.width(), geo.height()]
        self.config.set_property("windowGeometry", geoObj, save=False)
        self.config.set_property("windowMaximized", bool(self.windowState() & Qt.WindowMaximized), save=False)
        self.config.set_property("layout_dock_state", self.ticker.dockArea.saveState())
        self.ticker.disconnect()
        print('ticker disconnected')
        QMainWindow.closeEvent(self, event)
        QApplication.quit()
    
    def changeEvent(self, event):
        if event.type() == event.WindowStateChange:
            self.titleBar.maximized = self.windowState() & Qt.WindowMaximized
            image = 'unmaximize' if self.titleBar.maximized else 'maximize'
            self.titleBar.maximizeBtn.setStyleSheet(f'QPushButton{{image: url(:/icons/{image}.png);}}')
            #self.titleBar.maximizeBtn.setProperty('maximized', 'yes' if self.titleBar.maximized else 'no')
            #self.titleBar.maximizeBtn.style().unpolish(self.titleBar.maximizeBtn)
            #self.titleBar.maximizeBtn.style().polish(self.titleBar.maximizeBtn)
            if self.titleBar.maximized:
                margin = abs(self.mapToGlobal(self.rect().topLeft()).y())
                self.vl.setContentsMargins(margin, margin, margin, margin)
            else:
                self.vl.setContentsMargins(0,0,0,0)
            self.config.set_property("windowMaximized", bool(self.titleBar.maximized))
        return super().changeEvent(event)
    
    def nativeEvent(self, event, message):
        return_value, result = super().nativeEvent(event, message)

        # if you use Windows OS
        if event == b'windows_generic_MSG':
            msg = MSG.from_address(message.__int__())
            # Get the coordinates when the mouse moves.
            # % 65536: converted an unsigned int to int (for dual monitor issue)
            x = (win32api.LOWORD(LONG(msg.lParam).value) - self.frameGeometry().x() + 7) % 65536
            y = win32api.HIWORD(LONG(msg.lParam).value) - self.frameGeometry().y()

            # Determine whether there are other controls(i.e. widgets etc.) at the mouse position.
            if self.childAt(x, y) is not None and self.childAt(x, y) is not self.findChild(QWidget, "titleBar"):
                if self.width() - self.BORDER_WIDTH > x > self.BORDER_WIDTH and y < self.height() - self.BORDER_WIDTH:
                    return return_value, result

            if msg.message == WM_NCCALCSIZE:
                # Remove system title
                return True, 0

            if msg.message == WM_NCHITTEST:
                w, h = self.width(), self.height()
                #print(x,y,w - self.BORDER_WIDTH,h - self.BORDER_WIDTH)
                lx = x < self.BORDER_WIDTH
                rx = x > w - self.BORDER_WIDTH
                ty = y < self.BORDER_WIDTH
                by = y > h - self.BORDER_WIDTH
                if lx and ty:
                    return True, HTTOPLEFT
                if rx and by:
                    return True, HTBOTTOMRIGHT
                if rx and ty:
                    return True, HTTOPRIGHT
                if lx and by:
                    return True, HTBOTTOMLEFT
                if ty:
                    return True, HTTOP
                if by:
                    return True, HTBOTTOM
                if lx:
                    return True, HTLEFT
                if rx:
                    return True, HTRIGHT

                return True, HTCAPTION

        return QWidget.nativeEvent(self, event, message)

class StonkSplashScreen(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.vl = QVBoxLayout(self)
        self.setLayout(self.vl)

        loading_tips = [
                "Buy high, sell low! Or wait... was it the other way around?",
                "The shorts haven't covered a single share yet!",
                "When in doubt, average down!"
                ]
        loading_tip = random.choice(loading_tips)
        self.tipLabel = QLabel("Tip: {}".format(loading_tip), self)
        self.tipLabelShadow = QGraphicsDropShadowEffect(self)
        self.tipLabelShadow.setColor(QColor("#000000"))
        self.tipLabelShadow.setBlurRadius(1)
        self.tipLabelShadow.setOffset(2,2)
        self.tipLabel.setGraphicsEffect(self.tipLabelShadow)
        self.vl.addStretch()
        self.vl.addWidget(self.tipLabel)

        self.resize(800,450)

        self.bg = QPixmap(":/images/splash_screen")
        self.setStyleSheet("QLabel{background:transparent;font-size:25px;color:#fff;}")
        #self.testLabel.move(50,600)
    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(0,0, self.bg.scaled(self.size(), Qt.IgnoreAspectRatio))
        p.end()
        QWidget.paintEvent(self, event)
