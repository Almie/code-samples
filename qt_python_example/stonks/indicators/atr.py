from .base import BaseBarDataIndicator, Property
from ta.volatility import average_true_range

class ATRIndicator(BaseBarDataIndicator):
    indicatorType = "ATR"
    displayType = "plot"
    plotLocation = "ATR"
    length = Property("length", 14, int, "Length", "Amount of bars to average")

    def calculate(self, barData, barSize):
        return average_true_range(barData["high"], barData["low"], barData["close"], self.length.value, False).dropna()
