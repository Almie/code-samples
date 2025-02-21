from .base import BaseBarDataIndicator, Property

class RVOLIndicator(BaseBarDataIndicator):
    indicatorType = "RVOL"
    displayType = "bars"
    plotLocation = "RVOL"
    length = Property("length", 50, int, "Length", "Amount of bars to average")
    avgType = Property("avgType", "SMA", str, "Average Type", "Type of averaging to use to calculate relative volume",
                        value_choices=["SMA", "EMA"])

    def calculate(self, barData, barSize):
        if self.avgType.value == "SMA":
            rvol = barData["volume"] / barData["volume"].rolling(self.length.value).mean()
        else:
            rvol = barData["volume"] / barData["volume"].ewm(span=self.length.value, min_periods=self.length.value, adjust=False).mean()
        return rvol
