from .base import BaseBarDataIndicator, Property
from ta.momentum import rsi

class RsiIndicator(BaseBarDataIndicator):
    indicatorType = "rsi"
    displayType = "plot"
    plotLocation = "rsi"
    length = Property("length", 14, int, "Length", "Amount of bars to average")
    source = Property("source", "close", str, "Data Source", "Which part of the bar to average",
                        value_choices=["open", "high", "low", "close"])

    def calculate(self, barData, barSize):
        close = barData[self.source.value]
        return rsi(close, self.length.value).dropna()
