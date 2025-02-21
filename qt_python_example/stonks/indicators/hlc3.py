from .base import BaseBarDataIndicator, Property

class Hlc3Indicator(BaseBarDataIndicator):
    indicatorType = "hlc3"

    def calculate(self, barData, barSize):
        return (barData["high"]+barData["low"]+barData["close"])/3
