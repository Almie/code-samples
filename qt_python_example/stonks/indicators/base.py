from PySide2.QtCore import Qt, QObject, Signal

from ..market_data.types import get_empty_bar_dataframe

import logging
log = logging.getLogger('Indicators')

class IndicatorSignals(QObject):
    dataUpdated = Signal()

class BaseIndicator(object):
    indicatorType = ""
    displayType = "plot"
    plots = []
    fills = []
    plotLocation = "main"
    relativeDataRequired = False
    def __init__(self, name='', styleOptions=None, **options):
        self.name = name
        self.initOptions()
        for option_name in options:
            if option_name in self.__dict__ and isinstance(self.__dict__[option_name], Property):
                self.__dict__[option_name].value = options[option_name]
        self.options = self.__options
        if not styleOptions:
            styleOptions = IndicatorStyleOptions()
        self.styleOptions = styleOptions

    def initOptions(self):
        for option_name in dir(self):
            if not isinstance(getattr(self, option_name), Property):
                continue
            setattr(self, option_name, Property.copy(getattr(self, option_name)))

    @classmethod
    def options(self):
        return [getattr(self, option_name) for option_name in dir(self) if isinstance(getattr(self, option_name), Property)]

    def __options(self):
        return [getattr(self, option_name) for option_name in dir(self) if isinstance(getattr(self, option_name), Property)]

    def calculate(self, barData, barSize):
        pass

    def serialize(self):
        obj = {'name' : self.name, 'indicatorType' : self.indicatorType}
        optionNames = [property.name for property in self.options()]
        optionValues = [property.value for property in self.options()]
        log.debug(f'SERIALIZE INDICATOR {optionNames} {optionValues}')
        optionsObj = dict(zip(optionNames, optionValues))
        obj['options'] = optionsObj
        obj['styleOptions'] = self.styleOptions.serialize()
        return obj

class RelativeIndicator(BaseIndicator):
    relativeDataRequired = True
    def __init__(self, name='', styleOptions=None, **options):
        super().__init__(name, styleOptions, **options)
        self._api = None
        self._relativeData = {}
        self._requestActive = False
        self._activeSubscriptions = []
        self._signals = IndicatorSignals()
        self.dataUpdated = self._signals.dataUpdated

    def setApi(self, api):
        self._api = api

    def _requestRelativeData(self, symbol, barSize, startTime, endTime, live=False):
        dataType = f'bars_{barSize}'
        if not self._api:
            return
        if not self._requestActive:
            self._requestActive = True
            self._api.requestHistoricalBars(symbol, barSize, startTime, endTime, self.relativeDataCallback)
        if live and not f'{symbol}_{dataType}' in self._activeSubscriptions:
            self._activeSubscriptions.append(f'{symbol}_{dataType}')
            self._api.subscribeToLiveBars(symbol, barSize, self.liveDataCallback)
    
    def getRelativeData(self, barData, symbol, barSize):
        startTime = barData.index[0]
        endTime = barData.index[-1]
        dataType = f'bars_{barSize}'
        if symbol in self._relativeData.keys():
            if dataType in self._relativeData[symbol].keys():
                relativeBars = self._relativeData[symbol][dataType]
                if not relativeBars.empty:
                    if relativeBars.index[0] > startTime:
                        self._requestRelativeData(symbol, barSize, startTime, relativeBars.index[0], True)
                    return relativeBars
        self._requestRelativeData(symbol, barSize, startTime, endTime, True)
        return get_empty_bar_dataframe()
    
    def addRelativeData(self, symbol, dataType, bars):
        log.debug(f'{self.name} - ADDING RELATIVE DATA {symbol} {dataType}')
        if not symbol in self._relativeData.keys():
            self._relativeData[symbol] = {}
        if not dataType in self._relativeData[symbol].keys():
            self._relativeData[symbol][dataType] = get_empty_bar_dataframe()
        self._relativeData[symbol][dataType] = bars.combine_first(self._relativeData[symbol][dataType])

    def relativeDataCallback(self, symbol, barSize, bars, startTime, endTime):
        dataType = f'bars_{barSize}'
        self.addRelativeData(symbol, dataType, bars)
        self._requestActive = False
        self.dataUpdated.emit()
    
    def liveDataCallback(self, symbol, bar, barSize):
        dataType = f'bars_{barSize}'
        self.addRelativeData(symbol, dataType, bar)
    
    def cancelSubscriptions(self):
        for subscription in self._activeSubscriptions[:]:
            symbol = subscription.split('_')[0]
            barSize = subscription.split('_')[-1]
            requests = self._api.getSubscriptions(symbol, 'historicalBars', barSize)
            for request in requests:
                if not request.live_callback:
                    continue
                if request.live_callback.__self__ == self:
                    request.cancel()
            self._activeSubscriptions.remove(subscription)

class BaseBarDataIndicator(BaseIndicator):
    def calculate(self, barData):
        pass

def multi_plot(func):
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        if isinstance(result, tuple):
            df = result[0].to_frame()
            for series in result[1:]:
                if not series.name:
                    series.name = self.indicatorType
                increment=2
                nameBase = series.name
                while series.name in df.columns:
                    series.name = f'{nameBase}{increment:02}'
                    increment += 1
                df.merge(series, left_index=True, right_index=True)
            return df
        else:
            return result
    return wrapper

class Property(object):
    def __init__(self, name, default_value, value_type=float, display_name=None, description=None, value_choices=None):
        self.name = name
        self.default_value = default_value
        if display_name:
            self.display_name = display_name
        else:
            self.display_name = name
        self.description = description
        self.value_type = value_type
        self.value_choices = value_choices
        self._value = default_value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, newVal):
        self._value = self.value_type(newVal)

    @staticmethod
    def copy(other):
        new_property = Property(other.name, other.default_value, other.value_type, other.display_name, other.description, other.value_choices)
        new_property.value = other.value
        return new_property

class PlotStyleOptions(object):
    QT_STYLES = {'solid': Qt.SolidLine,
                'dash': Qt.DashLine,
                'dot': Qt.DotLine,
                'dash-dot': Qt.DashDotLine,
                'dash-dot-dot': Qt.DashDotDotLine}
    def __init__(self, name, color='#FFF', width=1, style="solid", visible=True):
        self.name = name
        self.color = color
        self.width = width
        self.style = style
        self.visible = visible

    @property
    def qtStyle(self):
        if self.style in self.QT_STYLES.keys():
            return self.QT_STYLES[self.style]
        else:
            return Qt.SolidLine

    def serialize(self):
        obj = {'name' : self.name,
                'color' : self.color,
                'width' : self.width,
                'style': self.style,
                'visible': self.visible
                }
        return obj

    @staticmethod
    def from_json(json_obj):
        newStyleOptions = PlotStyleOptions(name=json_obj.get("name"),
                                            color=json_obj.get("color", "#FFF"),
                                            width=json_obj.get("width", 1),
                                            style=json_obj.get("style", "solid"),
                                            visible=json_obj.get("visible", True))
        return newStyleOptions

class PlotFillStyleOptions(object):
    def __init__(self, curve1, curve2, color="#FFF", visible=True):
        self.curve1 = curve1
        self.curve2 = curve2
        self.color = color
        self.visible = visible

    def serialize(self):
        obj = {'curve1': self.curve1,
                'curve2': self.curve2,
                'color' : self.color,
                'visible': self.visible
                }
        return obj

    @staticmethod
    def from_json(json_obj):
        newStyleOptions = PlotFillStyleOptions(curve1=json_obj.get("curve1"),
                                            curve2=json_obj.get("curve2"),
                                            color=json_obj.get("color", "#FFF"),
                                            visible=json_obj.get("visible", True))
        return newStyleOptions

class BarsStyleOptions(object):
    def __init__(self, name, base_value=0.0, color1="#FF0", color2_active=False, color2="#F00", color2_threshold=0.0):
        self.name = name
        self.base_value = base_value
        self.color1 = color1
        self.color2_active = color2_active
        self.color2 = color2
        self.color2_threshold = color2_threshold

    def serialize(self):
        obj = {'name': self.name,
                'base_value': self.base_value,
                'color1': self.color1,
                'color2' : self.color2,
                'color2_active': self.color2_active,
                'color2_threshold': self.color2_threshold
                }
        return obj

    @staticmethod
    def from_json(json_obj):
        newStyleOptions = BarsStyleOptions(**json_obj)
        return newStyleOptions

class IndicatorStyleOptions(object):
    def __init__(self):
        self.visible = True
        self.plots = []
        self.fills = []
        self.barStyles = []

    def addPlot(self, plotStyleOptions):
        self.plots.append(plotStyleOptions)

    def addFill(self, fillStyleOptions):
        self.fills.append(fillStyleOptions)

    def addBarStyle(self, barsStyleOptions):
        self.barStyles.append(barsStyleOptions)

    def serialize(self):
        plots = [p.serialize() for p in self.plots]
        fills = [f.serialize() for f in self.fills]
        barStyles = [b.serialize() for b in self.barStyles]
        obj = {'visible': self.visible, 'plots': plots, 'fills': fills, 'barStyles': barStyles}
        return obj

    def plot(self, plotName=None):
        if not plotName and len(self.plots) > 0:
            return self.plots[0]
        else:
            for plot in self.plots:
                if plot.name == plotName:
                    return plot
        return None

    def barStyle(self, name=None):
        if not name and len(self.barStyles) > 0:
            return self.barStyles[0]
        else:
            for barStyle in self.barStyles:
                if barStyle.name == name:
                    return barStyle
        return None

    @staticmethod
    def from_json(json_obj):
        newStyleOptions = IndicatorStyleOptions()
        newStyleOptions.visible = json_obj.get('visible', True)
        plot_objs = json_obj.get('plots', [])
        for plot_obj in plot_objs:
            newStyleOptions.addPlot(PlotStyleOptions.from_json(plot_obj))
        if len(plot_objs) == 0:
            newStyleOptions.addPlot(PlotStyleOptions("default"))
        for fill_obj in json_obj.get('fills', []):
            newStyleOptions.addFill(PlotFillStyleOptions.from_json(fill_obj))
        for barStyle_obj in json_obj.get('barStyles', []):
            newStyleOptions.addBarStyle(BarsStyleOptions.from_json(barStyle_obj))  
        return newStyleOptions
