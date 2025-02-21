from .ui.main import StonkMainWindow, StonkSplashScreen
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QFile
from PySide2.QtGui import QIcon
from .themes import Obit_resources
import sys, os

#to print silent exceptions
sys._excepthook = sys.excepthook
def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)
sys.excepthook = exception_hook

import logging
#logging.basicConfig(level=logging.INFO)
loggers = ['Market Data', 'Broker', 'UI', 'Backtest Engine', 'Live Engine', 'Indicators', 'Scanner']
for logger_name in loggers:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    consoleHandler = logging.StreamHandler()
    consoleHandler.setLevel(logging.WARNING)
    consoleFormatter = logging.Formatter('%(asctime)s [%(name)s] [%(levelname)s] %(message)s')
    consoleHandler.setFormatter(consoleFormatter)
    logger.addHandler(consoleHandler)
    logger.info(f'Start of {logger_name} log')

if os.name == 'nt':
    # This is needed to display the app icon on the taskbar on Windows 7
    import ctypes
    myappid = 'StonX.MyGui.1.0.0' # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

def main():
    app = QApplication(sys.argv)
    with open(os.path.join(os.path.dirname(__file__), 'themes', 'Obit.qss'), 'r') as f:
        app.setStyleSheet(f.read())
    app.setWindowIcon(QIcon(":/icons/appicon.png"))
    #styleFile = QFile(":/obit/Obit.qss")
    #styleFile.open(QFile.ReadOnly)
    #content = styleFile.readAll().data()
    #app.setStyleSheet(str(content, "utf-8"))
    splashScreen = StonkSplashScreen()
    splashScreen.show()
    #import time
    #time.sleep(2)

    mainWindow = StonkMainWindow()
    mainWindow.show()
    splashScreen.hide()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
