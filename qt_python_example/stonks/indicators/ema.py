from .base import BaseBarDataIndicator, Property

class EmaIndicator(BaseBarDataIndicator):
    indicatorType = "ema"
    displayType = "plot"
    length = Property("length", 7, int, "Length", "Amount of bars to average")
    source = Property("source", "close", str, "Data Source", "Which part of the bar to average",
                        value_choices=["open", "high", "low", "close"])

    def calculate(self, barData, barSize):
        close = barData[self.source.value]
        return close.ewm(span=self.length.value, min_periods=self.length.value, adjust=False).mean().dropna()
