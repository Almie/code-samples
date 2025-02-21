from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *

import pyqtgraph as pg
import pandas as pd

from ...common import VisToggle, ColorPicker
from ....indicators import (Indicator, available_indicators,
                            IndicatorStyleOptions, PlotStyleOptions,
                            PlotFillStyleOptions, BarsStyleOptions)
def IndicatorItem(indicator, *args, **kwargs):
    if indicator.displayType == "plot":
        return PlotIndicatorItem(indicator, *args, **kwargs)
    elif indicator.displayType == "multi_plot":
        return MultiPlotIndicatorItem(indicator, *args, **kwargs)
    elif indicator.displayType == "bars":
        return BarsIndicatorItem(indicator, *args, **kwargs)
    else:
        return None

class BaseIndicatorItem(object):
    def __init__(self, indicator):
        self.indicator = indicator
        self.chartItem = None
        self._visible = indicator.styleOptions.visible
        self.hoverItem = pg.TextItem(text=f'{indicator.name}\n0.00', color='#FFF', fill=QColor("#000000"), anchor=(1,1))
        self.hoverItem.setVisible(False)

    def calculate(self, barData, barSize):
        indicatorData = self.indicator.calculate(barData, barSize)

    def addToChart(self, plotItem):
        plotItem.addItem(self.chartItem)
        plotItem.addItem(self.hoverItem)

    def removeFromChart(self, plotItem):
        plotItem.removeItem(self.chartItem)
        plotItem.removeItem(self.hoverItem)

    def setVisible(self, visible):
        self.chartItem.setVisible(visible)
        self._visible = visible

    def isVisible(self):
        return self._visible

    def hover(self, pos, value):
        self.hoverItem.setVisible(True)
        self.hoverItem.setPos(pos)
        self.hoverItem.setText(f'{self.indicator.name}\n{value:.2f}')
        return self.hoverItem

    def unhover(self):
        self.hoverItem.setVisible(False)

    def editIndicator(self, editedIndicator):
        self.indicator = editedIndicator

class PlotIndicatorItem(BaseIndicatorItem):
    def __init__(self, indicator):
        BaseIndicatorItem.__init__(self, indicator)
        self.chartItem = pg.PlotDataItem()
        plot = indicator.styleOptions.plot()
        self.chartItem.setPen(pg.mkPen(color=QColor(plot.color), width=plot.width, style=plot.qtStyle))
        self.hoverItem.fill = pg.mkBrush(QColor(plot.color))

    def calculate(self, barData, barSize, offset):
        indicatorData = self.indicator.calculate(barData, barSize)
        self.chartItem.setData([index.timestamp() for index in indicatorData.index], indicatorData.tolist())

    def editIndicator(self, editedIndicator):
        BaseIndicatorItem.editIndicator(self, editedIndicator)
        plot = self.indicator.styleOptions.plot()
        self.chartItem.setPen(pg.mkPen(color=QColor(plot.color), width=plot.width, style=plot.qtStyle))
        self.hoverItem.fill = pg.mkBrush(QColor(plot.color))

class MultiPlotIndicatorItem(BaseIndicatorItem):
    def __init__(self, indicator):
        BaseIndicatorItem.__init__(self, indicator)
        self.chartItems = {}
        self.fills = []
        self.hoverItems = {}
        for plotName in indicator.plots:
            plotItem = pg.PlotDataItem()
            plot = indicator.styleOptions.plot(plotName)
            if plot is None:
                plot = PlotStyleOptions("default")
            plotItem.setPen(pg.mkPen(color=QColor(plot.color), width=plot.width, style=plot.qtStyle))
            plotItem.setVisible(plot.visible)
            self.chartItems[plotName] = plotItem
            hoverItem = pg.TextItem(text=f'{indicator.name}\n{plotName}\n0.00', color='#FFF', fill=QColor(plot.color), anchor=(1,1))
            hoverItem.setVisible(False)
            self.hoverItems[plotName] = hoverItem

        for i, fill in enumerate(indicator.fills):
            curve1 = self.chartItems[fill[0]]
            curve2 = self.chartItems[fill[1]]
            try:
                style = indicator.styleOptions.fills[i]
            except IndexError:
                style = PlotFillStyleOptions(fill[0], fill[1])
            fillItem = pg.FillBetweenItem(curve1=curve1, curve2=curve2, brush=pg.mkBrush(QColor(style.color)))
            fillItem.setVisible(style.visible)
            self.fills.append(fillItem)

    def calculate(self, barData, barSize, offset):
        indicatorData = self.indicator.calculate(barData, barSize)
        for i in range(len(indicatorData)):
            data = indicatorData[i]
            plotName = self.indicator.plots[i]
            self.chartItems[plotName].setData([index.timestamp() for index in data.index], data.tolist())

    def addToChart(self, plotItem):
        print('ADDING TO CHART', self.indicator.plotLocation, self.indicator.name, plotItem)
        for chartItem in self.chartItems.values():
            plotItem.addItem(chartItem)
        for fillItem in self.fills:
            plotItem.addItem(fillItem)
        for hoverItem in self.hoverItems.values():
            plotItem.addItem(hoverItem)

    def removeFromChart(self, plotItem):
        for chartItem in self.chartItems.values():
            plotItem.removeItem(chartItem)
        for fillItem in self.fills:
            plotItem.removeItem(fillItem)
        for hoverItem in self.hoverItems.values():
            plotItem.removeItem(hoverItem)

    def setVisible(self, visible):
        for plotName, chartItem in self.chartItems.items():
            plotVisible = True
            plotStyle = self.indicator.styleOptions.plot(plotName)
            if plotStyle:
                plotVisible = plotStyle.visible
            chartItem.setVisible(visible and plotVisible)
        for num, fillItem in enumerate(self.fills):
            try:
                fillStyle = self.indicator.styleOptions.fills[num]
                fillVisible = fillStyle.visible
            except:
                fillVisible = True
            fillItem.setVisible(visible and fillVisible)
        self._visible = visible

    def hover(self, pos, value, plot):
        self.hoverItems[plot].setVisible(True)
        self.hoverItems[plot].setPos(pos)
        self.hoverItems[plot].setText(f'{self.indicator.name}\n{plot}\n{value:.2f}')
        return self.hoverItems[plot]

    def unhover(self, plot):
        self.hoverItems[plot].setVisible(False)

    def editIndicator(self, editedIndicator):
        BaseIndicatorItem.editIndicator(self, editedIndicator)
        for plotName, chartItem in self.chartItems.items():
            plot = self.indicator.styleOptions.plot(plotName)
            print("EDITING PLOT", plot.name, plot.color, plot.width, plot.style, plot.visible)
            chartItem.setPen(pg.mkPen(color=QColor(plot.color), width=plot.width, style=plot.qtStyle))
            chartItem.setVisible(plot.visible)
            self.hoverItems[plotName].fill = pg.mkBrush(QColor(plot.color))
        for num, fillItem in enumerate(self.fills):
            try:
                fillStyle = self.indicator.styleOptions.fills[num]
            except:
                continue
            print("EDITING FILL", fillStyle.color, fillStyle.visible)
            fillItem.setBrush(pg.mkBrush(QColor(fillStyle.color)))
            fillItem.setVisible(fillStyle.visible)

class BarsIndicatorItem(BaseIndicatorItem):
    def __init__(self, indicator):
        BaseIndicatorItem.__init__(self, indicator)
        self.chartItem = pg.BarGraphItem()
        self.chartItem.setOpts(pen=pg.mkPen(None))
        barStyle = self.indicator.styleOptions.barStyle()
        self.hoverItem.fill = QColor(barStyle.color1)

    def infer_freq(self, barData):
        if barData.index.size == 0:
            return pd.Timedelta(0)
        return barData.index.to_series().diff().median()

    def calculate(self, barData, barSize, offset):
        indicatorData = self.indicator.calculate(barData, barSize)
        w = self.infer_freq(indicatorData).total_seconds()
        if w == 0:
            print('w 0')
        barStyle = self.indicator.styleOptions.barStyle()
        baseVal = barStyle.base_value
        y0 = [min(val, baseVal) for val in indicatorData.tolist()]
        y1 = [max(val, baseVal) for val in indicatorData.tolist()]
        self.chartItem.setOpts(x=[index.timestamp() for index in indicatorData.index],
                                y0=y0,
                                y1=y1,
                                width = w*0.75)
        if barStyle.color2_active:
            brushes = [pg.mkBrush(QColor(barStyle.color1))
                        if val < barStyle.color2_threshold
                        else pg.mkBrush(QColor(barStyle.color2))
                        for val in indicatorData.tolist()]
            self.chartItem.setOpts(brushes=brushes)
        else:
            self.chartItem.setOpts(brush=pg.mkBrush(barStyle.color1))

class IndicatorComboBox(QComboBox):
    addIndicator = Signal()
    toggleVisIndicator = Signal(object, bool)
    editIndicator = Signal(object)
    deleteIndicator = Signal(object)
    def __init__(self, indicators):
        QComboBox.__init__(self)
        self.indicators = indicators
        self.visButtons = []
        self.editButtons = []
        self.delButtons = []

        self.indicatorModel = QStandardItemModel(1,2)
        self.setModel(self.indicatorModel)
        self.setMinimumWidth(100)
        self.activated.connect(self.itemActivated)

    def paintEvent(self, e):
        painter = QStylePainter(self)
        painter.setPen(self.palette().color(QPalette.Text))

        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        opt.currentText = "Indicators"
        painter.drawComplexControl(QStyle.CC_ComboBox, opt)

        painter.drawControl(QStyle.CE_ComboBoxLabel, opt)

    def updateIndicatorList(self):
        self.indicatorModel.clear()
        self.visButtons = []
        self.editButtons = []
        self.delButtons = []
        print(self.indicators)
        plusItem = QStandardItem("+")
        plusItem.setTextAlignment(Qt.AlignCenter)
        addNewItem = QStandardItem("Add new...")
        addNewItem.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.indicatorModel.appendRow([plusItem, addNewItem, QStandardItem(), QStandardItem()])
        for row, indicatorItem in enumerate(self.indicators):
            isVisible = indicatorItem.isVisible()
            visibilityItem = QStandardItem("")
            nameItem = QStandardItem(indicatorItem.indicator.name)
            nameItem.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            if not isVisible:
                nameItem.setData(QBrush(QColor("#777777")), Qt.ForegroundRole)
            editItem = QStandardItem("")
            deleteItem = QStandardItem("")
            self.indicatorModel.appendRow([visibilityItem, nameItem, editItem, deleteItem])
            visibilityButton = VisToggle()
            visibilityButton.indicator = indicatorItem
            visibilityButton.setCheckState(Qt.Checked if isVisible else Qt.Unchecked)
            print('vistoggle', indicatorItem.indicator.name, isVisible)
            visibilityButton.stateChanged.connect(self.onToggleVis)
            visButtonIndex = self.indicatorModel.index(row+1, 0)
            self.indicatorView.setIndexWidget(visButtonIndex, visibilityButton)
            self.visButtons.append(visibilityButton)
            editButton = QPushButton("")
            editButton.indicator = indicatorItem
            editButton.setProperty("btnStyle", "indicatorSettings")
            editButton.clicked.connect(self.onEditIndicator)
            editButtonIndex = self.indicatorModel.index(row+1, 2)
            self.indicatorView.setIndexWidget(editButtonIndex, editButton)
            self.editButtons.append(editButton)
            deleteButton = QPushButton("")
            deleteButton.indicator = indicatorItem
            deleteButton.setProperty("btnStyle", "indicatorDelete")
            deleteButton.clicked.connect(self.onDeleteIndicator)
            delButtonIndex = self.indicatorModel.index(row+1, 3)
            self.indicatorView.setIndexWidget(delButtonIndex, deleteButton)
            self.delButtons.append(deleteButton)

    def showPopup(self):
        self.indicatorView = IndicatorView(self)
        self.indicatorView.setModel(self.indicatorModel)
        self.updateIndicatorList()

        self.setView(self.indicatorView)
        QComboBox.showPopup(self)
        self.indicatorView.setupSectionSizes()

        self.view().setMinimumWidth(self.view().viewportSizeHint().width())
        self.view().setMinimumHeight(0)

    def onToggleVis(self, state):
        self.toggleVisIndicator.emit(self.sender().indicator, state == Qt.Checked)
        for row, indicatorItem in enumerate(self.indicators):
            index = self.indicatorModel.index(row+1, 0, QModelIndex())
            indexWidget = self.indicatorView.indexWidget(index)
            if indexWidget == self.sender():
                nameItem = self.indicatorModel.item(row+1, 1)
                color = "#cccccc" if state == Qt.Checked else "#777777"
                nameItem.setData(QBrush(QColor(color)), Qt.ForegroundRole)

    def onDeleteIndicator(self):
        self.deleteIndicator.emit(self.sender().indicator)

    def onEditIndicator(self):
        self.editIndicator.emit(self.sender().indicator)

    def itemActivated(self, index):
        if index == 0:
            self.addIndicator.emit()

class IndicatorView(QTableView):
    def __init__(self, parent=None):
        QTableView.__init__(self, parent)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setShowGrid(False)
        self.setProperty("indicatorView", "yes")

    def setupSectionSizes(self):
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.verticalHeader().setDefaultSectionSize(12)
        self.verticalHeader().setMinimumSectionSize(0)
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        self.horizontalHeader().setMinimumSectionSize(0)
        self.horizontalHeader().resizeSection(0, 25)
        self.horizontalHeader().resizeSection(2, 25)
        self.horizontalHeader().resizeSection(3, 25)
        self.setFocusPolicy(Qt.NoFocus)


class IndicatorAddDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.vl = QVBoxLayout(self)
        self.setLayout(self.vl)

        self.basicsBox = QGroupBox(self)
        self.basicsFl = QFormLayout(self.basicsBox)
        self.basicsBox.setLayout(self.basicsFl)
        self.vl.addWidget(self.basicsBox)

        self.nameEdit = QLineEdit("")
        self.basicsFl.addRow("Name", self.nameEdit)

        self.indicatorTypeComboBox = QComboBox(self)
        self.indicatorTypes = []
        for indicator in available_indicators():
            self.indicatorTypes.append(indicator)
            self.indicatorTypeComboBox.addItem(indicator.indicatorType)
        self.indicatorTypeComboBox.currentIndexChanged.connect(self.indicatorTypeChanged)
        self.basicsFl.addRow("Type", self.indicatorTypeComboBox)
        self.nameEdit.setText(self.indicatorTypeComboBox.currentText())

        self.optionBox = QGroupBox(self)
        self.optionBoxLayout = QFormLayout(self)
        self.optionBox.setLayout(self.optionBoxLayout)
        self.vl.addWidget(self.optionBox)

        self.styleBox = QGroupBox(self)
        self.styleBoxLayout = QGridLayout(self)
        self.styleBox.setLayout(self.styleBoxLayout)
        self.vl.addWidget(self.styleBox)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.vl.addWidget(self.buttonBox)

    def indicatorTypeChanged(self, index):
        self.updateOptionBox()
        if self.nameEdit.text() == "":
            self.nameEdit.setText(self.indicatorTypeComboBox.currentText())

    def updateOptionBox(self):
        currentIndicator = self.indicatorTypes[self.indicatorTypeComboBox.currentIndex()]
        if self.optionBoxLayout.rowCount() > 0:
            self.clearOptionBox()
        for property in currentIndicator.options():
            if property.value_choices:
                optionWidget = QComboBox()
                optionWidget.addItems([str(opt) for opt in property.value_choices])
                optionWidget.setCurrentText(str(property.default_value))
                optionWidget.text = optionWidget.currentText
                optionWidget.setText = optionWidget.setCurrentText
            else:
                optionWidget = QLineEdit(str(property.default_value))
            optionWidget.property = property
            print('updateOptionBox', property.name, property.value, self.optionBoxLayout.rowCount())
            self.optionBoxLayout.addRow(property.display_name, optionWidget)

        if self.styleBoxLayout.rowCount() > 0:
            self.clearStyleBox()
        if currentIndicator.displayType == "plot":
            label = QLabel("Line Style")
            colorWidget = ColorPicker("#FFFFFF")
            widthWidget = QLineEdit("1")
            lineStyleWidget = QComboBox()
            lineStyleWidget.addItems(["solid", "dash", "dot", "dash-dot", "dash-dot-dot"])
            lineStyleWidget.setCurrentText("solid")
            self.styleBoxLayout.addWidget(label, 0, 0)
            self.styleBoxLayout.addWidget(colorWidget, 0, 1)
            self.styleBoxLayout.addWidget(widthWidget, 0, 2)
            self.styleBoxLayout.addWidget(lineStyleWidget, 0, 3)
        elif currentIndicator.displayType == "multi_plot":
            rows = 0
            for plot in currentIndicator.plots:
                visibleCheck = VisToggle()
                visibleCheck.setCheckState(Qt.Checked)
                label = QLabel(str(plot))
                colorWidget = ColorPicker("#FFFFFF")
                widthWidget = QLineEdit("1")
                lineStyleWidget = QComboBox()
                lineStyleWidget.addItems(["solid", "dash", "dot", "dash-dot", "dash-dot-dot"])
                lineStyleWidget.setCurrentText("solid")
                self.styleBoxLayout.addWidget(visibleCheck, rows, 0)
                self.styleBoxLayout.addWidget(label, rows, 1)
                self.styleBoxLayout.addWidget(colorWidget, rows, 2)
                self.styleBoxLayout.addWidget(widthWidget, rows, 3)
                self.styleBoxLayout.addWidget(lineStyleWidget, rows, 4)
                rows += 1
            for num, fill in enumerate(currentIndicator.fills):
                visibleCheck = VisToggle()
                visibleCheck.setCheckState(Qt.Checked)
                label = QLabel(f'Fill #{num}')
                colorWidget = ColorPicker("#FFFFFF")
                self.styleBoxLayout.addWidget(visibleCheck, rows, 0)
                self.styleBoxLayout.addWidget(label, rows, 1)
                self.styleBoxLayout.addWidget(colorWidget, rows, 2)
                rows +=1
        elif currentIndicator.displayType == "bars":
            label = QLabel("Bars Style")
            baseValueLabel = QLabel("Base Level")
            baseValueEdit = QLineEdit("0.0")
            color1Widget = ColorPicker("#FF0000")
            color2ActiveCheck = QCheckBox("Enable 2 Colors")
            color2Label = QLabel("2nd Color")
            color2Label.setVisible(False)
            color2Widget = ColorPicker("#FFFF00")
            color2Widget.setVisible(False)
            color2ThresholdLabel = QLabel("2nd Color Threshold")
            color2ThresholdLabel.setVisible(False)
            color2ThresholdEdit = QLineEdit('0.0')
            color2ThresholdEdit.setVisible(False)
            color2ActiveCheck.toggled.connect(color2Label.setVisible)
            color2ActiveCheck.toggled.connect(color2Widget.setVisible)
            color2ActiveCheck.toggled.connect(color2ThresholdLabel.setVisible)
            color2ActiveCheck.toggled.connect(color2ThresholdEdit.setVisible)
            self.styleBoxLayout.addWidget(label, 0, 0)
            self.styleBoxLayout.addWidget(baseValueEdit, 0, 1)
            self.styleBoxLayout.addWidget(color1Widget, 0, 2)
            self.styleBoxLayout.addWidget(color2ActiveCheck, 0, 3)
            self.styleBoxLayout.addWidget(color2Label, 1, 1)
            self.styleBoxLayout.addWidget(color2Widget, 1, 2)
            self.styleBoxLayout.addWidget(color2ThresholdLabel, 2, 1)
            self.styleBoxLayout.addWidget(color2ThresholdEdit, 2, 2)

    def clearOptionBox(self):
        """
        while ((child := self.optionBoxLayout.takeRow(0)) != None):
            child.widget().deleteLater()
            del child
        """
        while self.optionBoxLayout.rowCount() > 0:
            self.optionBoxLayout.removeRow(0)

    def clearStyleBox(self):
        while ((child := self.styleBoxLayout.takeAt(0)) != None):
            child.widget().deleteLater()
            del child

    def getOptions(self):
        options = {}
        rowCount = self.optionBoxLayout.rowCount()
        for row in range(rowCount):
            optionItem = self.optionBoxLayout.itemAt(row, QFormLayout.FieldRole)
            if not optionItem:
                continue
            optionWidget = optionItem.widget()
            property = optionWidget.property
            options[property.name] = str(optionWidget.text())
        return options

    def getStyleOptions(self):
        currentIndicator = self.indicatorTypes[self.indicatorTypeComboBox.currentIndex()]
        if currentIndicator.displayType == "plot":
            colorItem = self.styleBoxLayout.itemAtPosition(0, 1)
            color = colorItem.widget().color
            widthItem = self.styleBoxLayout.itemAtPosition(0, 2)
            width = float(widthItem.widget().text())
            styleItem = self.styleBoxLayout.itemAtPosition(0, 3)
            style = str(styleItem.widget().currentText())
            plotName = str(self.nameEdit.text())
            plotOptions = PlotStyleOptions(plotName, color, width, style, visible=True)
            styleOptions = IndicatorStyleOptions()
            styleOptions.addPlot(plotOptions)
            return styleOptions
        elif currentIndicator.displayType == "multi_plot":
            styleOptions = IndicatorStyleOptions()
            row = 0
            for plot in currentIndicator.plots:
                visItem = self.styleBoxLayout.itemAtPosition(row, 0)
                visible = visItem.widget().checkState() == Qt.Checked
                plotNameItem = self.styleBoxLayout.itemAtPosition(row, 1)
                plotName = str(plotNameItem.widget().text())
                colorItem = self.styleBoxLayout.itemAtPosition(row, 2)
                color = colorItem.widget().color
                widthItem = self.styleBoxLayout.itemAtPosition(row, 3)
                width = float(widthItem.widget().text())
                styleItem = self.styleBoxLayout.itemAtPosition(row, 4)
                style = str(styleItem.widget().currentText())
                plotOptions = PlotStyleOptions(plotName, color, width, style, visible)
                styleOptions.addPlot(plotOptions)
                row += 1
            for num, fill in enumerate(currentIndicator.fills):
                visItem = self.styleBoxLayout.itemAtPosition(row, 0)
                visible = visItem.widget().checkState() == Qt.Checked
                colorItem = self.styleBoxLayout.itemAtPosition(row, 2)
                color = colorItem.widget().color
                fillOptions = PlotFillStyleOptions(fill[0], fill[1], color, visible)
                styleOptions.addFill(fillOptions)
                row += 1
            return styleOptions
        elif currentIndicator.displayType == "bars":
            styleOptions = IndicatorStyleOptions()
            barsName = str(self.nameEdit.text())
            baseValueItem = self.styleBoxLayout.itemAtPosition(0, 1)
            base_value = float(baseValueItem.widget().text())
            color1Item = self.styleBoxLayout.itemAtPosition(0, 2)
            color1 = color1Item.widget().color
            color2ActiveItem = self.styleBoxLayout.itemAtPosition(0, 3)
            color2_active = color2ActiveItem.widget().checkState() == Qt.Checked
            color2Item = self.styleBoxLayout.itemAtPosition(1, 2)
            color2 = color2Item.widget().color
            color2ThresholdItem = self.styleBoxLayout.itemAtPosition(2, 2)
            color2_threshold = float(color2ThresholdItem.widget().text())
            barsStyleOptions = BarsStyleOptions(barsName, base_value, color1, color2_active, color2, color2_threshold)
            styleOptions.addBarStyle(barsStyleOptions)
            return styleOptions

    def fillFromIndicator(self, indicator):
        self.nameEdit.setText(indicator.name)
        if str(self.indicatorTypeComboBox.currentText()) == indicator.indicatorType:
            self.updateOptionBox()
        else:
            self.indicatorTypeComboBox.setCurrentText(indicator.indicatorType)
        rowCount = self.optionBoxLayout.rowCount()
        print('fill from indicator', rowCount)
        for row in range(rowCount):
            optionItem = self.optionBoxLayout.itemAt(row, QFormLayout.FieldRole)
            print('optionItem', optionItem)
            if not optionItem:
                continue
            optionWidget = optionItem.widget()
            property = optionWidget.property
            optionWidget.setText(str(getattr(indicator, property.name).value))

        if indicator.displayType == "plot":
            plot = indicator.styleOptions.plot()
            colorItem = self.styleBoxLayout.itemAtPosition(0, 1)
            colorItem.widget().setColor(plot.color)
            widthItem = self.styleBoxLayout.itemAtPosition(0, 2)
            widthItem.widget().setText(str(plot.width))
            styleItem = self.styleBoxLayout.itemAtPosition(0, 3)
            styleItem.widget().setCurrentText(str(plot.style))
        elif indicator.displayType == "multi_plot":
            row = 0
            for plotName in indicator.plots:
                plot = indicator.styleOptions.plot(plotName)
                if not plot:
                    continue
                visItem = self.styleBoxLayout.itemAtPosition(row, 0)
                visItem.widget().setCheckState(Qt.Checked if plot.visible else Qt.Unchecked)
                colorItem = self.styleBoxLayout.itemAtPosition(row, 2)
                colorItem.widget().setColor(plot.color)
                widthItem = self.styleBoxLayout.itemAtPosition(row, 3)
                widthItem.widget().setText(str(plot.width))
                styleItem = self.styleBoxLayout.itemAtPosition(row, 4)
                styleItem.widget().setCurrentText(str(plot.style))
                row += 1
            for num, fill in enumerate(indicator.fills):
                try:
                    fillStyle = indicator.styleOptions.fills[num]
                except IndexError:
                    continue
                visItem = self.styleBoxLayout.itemAtPosition(row, 0)
                visItem.widget().setCheckState(Qt.Checked if fillStyle.visible else Qt.Unchecked)
                colorItem = self.styleBoxLayout.itemAtPosition(row, 2)
                colorItem.widget().setColor(fillStyle.color)
        elif indicator.displayType == "bars":
            barStyle = indicator.styleOptions.barStyle()
            baseValueItem = self.styleBoxLayout.itemAtPosition(0, 1)
            baseValueItem.widget().setText(str(barStyle.base_value))
            color1Item = self.styleBoxLayout.itemAtPosition(0, 2)
            color1Item.widget().setColor(barStyle.color1)
            color2ActiveItem = self.styleBoxLayout.itemAtPosition(0, 3)
            color2ActiveItem.widget().setCheckState(Qt.Checked if barStyle.color2_active else Qt.Unchecked)
            color2Item = self.styleBoxLayout.itemAtPosition(1, 2)
            color2Item.widget().setColor(barStyle.color1)
            color2ThresholdItem = self.styleBoxLayout.itemAtPosition(2, 2)
            color2ThresholdItem.widget().setText(str(barStyle.color2_threshold))

    @property
    def indicator(self):
        indicatorType = self.indicatorTypes[self.indicatorTypeComboBox.currentIndex()].indicatorType
        name = str(self.nameEdit.text())
        options = self.getOptions()
        styleOptions = self.getStyleOptions()
        newIndicator = Indicator(indicatorType, name, styleOptions, **options)
        return newIndicator

    @staticmethod
    def getNewIndicator(parent=None):
        indicatorDialog = IndicatorAddDialog(parent)
        indicatorDialog.setWindowTitle("New Indicator")
        indicatorDialog.updateOptionBox()
        result = indicatorDialog.exec_()
        if result:
            return indicatorDialog.indicator
        else:
            return None

    @staticmethod
    def editIndicator(indicator, parent=None):
        indicatorDialog = IndicatorAddDialog(parent)
        indicatorDialog.setWindowTitle("Editing {}".format(indicator.name))
        indicatorDialog.fillFromIndicator(indicator)
        result = indicatorDialog.exec_()
        if result:
            return indicatorDialog.indicator
        else:
            return None
