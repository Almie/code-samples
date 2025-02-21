from . import ui
from PySide2.QtWidgets import QApplication
import sys, os, json

def get_rigs_config():
    with open('rigs_config.json') as f:
        rigs_config = json.load(f)
        f.close()
        return rigs_config

def main():
    app = QApplication(sys.argv)
    with open(os.path.join(os.path.dirname(__file__), 'Obit.qss'), 'r') as f:
        app.setStyleSheet(f.read())
    rigs_config = get_rigs_config()
    mainWindow = ui.CacherMainWindow(rigs_config)
    mainWindow.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
