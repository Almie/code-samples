from .base import BaseBarDataIndicator, Property

class SmaIndicator(BaseBarDataIndicator):
    indicatorType = "sma"
    displayType = "plot"
    length = Property("length", 7, int, "Length", "Amount of bars to average")
    source = Property("source", "close", str, "Data Source", "Which part of the bar to average",
                        value_choices=["open", "high", "low", "close"])

    def calculate(self, barData, barSize):
        close = barData[self.source.value]
        return close.rolling(self.length.value).mean()
