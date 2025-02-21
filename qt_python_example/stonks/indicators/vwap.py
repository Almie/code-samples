from .base import BaseBarDataIndicator, Property
from .hlc3 import Hlc3Indicator

class VwapIndicator(BaseBarDataIndicator):
    indicatorType = "vwap"
    displayType = "plot"

    def hlc3(self, barData):
        return (barData["high"]+barData["low"]+barData["close"])/3

    def calculate(self, barData, barSize):
        hlc3 = self.hlc3(barData)
        sumPriceVol = (hlc3 * barData["volume"]).cumsum()
        sumVol = barData["volume"].cumsum()
        vwap = sumPriceVol / sumVol
        return vwap
