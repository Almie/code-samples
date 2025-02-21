from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *

class BaseVisualizer(QWidget):
    name = 'Base'
    icon = ':/icons/dollar.png'
    def __init__(self, parent=None):
        QWidget.__init__(self)
        self.setAttribute(Qt.WA_StyledBackground)
        self.__frameVl = QVBoxLayout(self)
        self.__frameVl.setSpacing(0)
        self.__frameVl.setContentsMargins(15,15,15,15)
        self.__frameVl.setAlignment(Qt.AlignTop)
        self.setLayout(self.__frameVl)
        self.__frameTitleRow = QWidget(self)
        self.__frameTitleRow.setObjectName('frameTitle')
        self.__frameTitleHl = QHBoxLayout(self.__frameTitleRow)
        self.__frameTitleHl.setContentsMargins(0,0,0,0)
        self.__frameTitleHl.setAlignment(Qt.AlignLeft)
        self.__frameTitleRow.setLayout(self.__frameTitleHl)
        self.__frameVl.addWidget(self.__frameTitleRow)

        self.__frameIcon = QLabel()
        self.__frameIcon.setPixmap(QPixmap(self.icon).scaledToHeight(14, Qt.SmoothTransformation))
        self.__frameIcon.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.__frameTitleHl.addWidget(self.__frameIcon)
        self.__frameLabel = QLabel(self.name)
        self.__frameLabel.setObjectName('frameLabel')
        self.__frameLabel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.__frameTitleHl.addWidget(self.__frameLabel)
        self.__mainWidget = QWidget(self)
        self.__frameVl.addWidget(self.__mainWidget)
        self.setLayout = self.__mainWidget.setLayout
