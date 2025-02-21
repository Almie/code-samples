from .base import Property, BaseIndicator, IndicatorStyleOptions, PlotStyleOptions, PlotFillStyleOptions, BarsStyleOptions
from .sma import SmaIndicator
from .ema import EmaIndicator
from .vwap import VwapIndicator
from .ichimoku import IchimokuCloudIndicator
from .rsi import RsiIndicator
from .atr import ATRIndicator
from .rvol import RVOLIndicator
from .relative_strength import RelativeStrengthIndicator
#from .algo_lines import AlgoLinesIndicator
import sys
import inspect

def available_indicators():
    indicators = []
    for varName in dir(sys.modules[__name__]):
        var = globals()[varName]
        if not inspect.isclass(var):
            continue
        if var == BaseIndicator:
            continue
        if issubclass(var, BaseIndicator):
            indicators.append(var)
    return indicators

def Indicator(indicatorType, name, styleOptions=None, **options):
    for indicator in available_indicators():
        if indicator.indicatorType == indicatorType:
            return indicator(name, styleOptions, **options)
    return None
