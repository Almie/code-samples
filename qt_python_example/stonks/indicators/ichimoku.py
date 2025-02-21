from .base import BaseBarDataIndicator, Property

class IchimokuCloudIndicator(BaseBarDataIndicator):
    indicatorType = "ichimokuCloud"
    displayType = "multi_plot"
    plots = ["tenkan", "kijun", "senkou_A", "senkou_B", "chikou"]
    fills = [("senkou_A", "senkou_B")]
    tenkan_len = Property("tenkan_len", 9, int, "Tenkan Length", "Conversion line (tenkan sen) length")
    kijun_len = Property("kijun_len", 26, int, "Kijun Length", "Base line (kijun sen) length")
    senkou_len = Property("senkou_len", 52, int, "Senkou Length", "Leading span (senkou span) length")
    chikou_len = Property("chikou_len", 26, int, "Chikou Length", "Lagging span (chikou span) length")

    def donchian(self, barData, len):
        high = barData["high"].rolling(len).max()
        low = barData["low"].rolling(len).min()
        return (high + low) / 2

    def infer_freq(self, barData):
        return barData.index.to_series().diff().median()

    def calculate(self, barData, barSize):
        freq = self.infer_freq(barData)
        tenkan = self.donchian(barData, self.tenkan_len.value)
        kijun = self.donchian(barData, self.kijun_len.value)
        senkou_A = (tenkan + kijun) / 2
        senkou_A = senkou_A.shift(self.chikou_len.value, freq=freq).dropna()
        senkou_B = self.donchian(barData, self.senkou_len.value).shift(self.chikou_len.value, freq=freq).dropna()
        chikou = barData["close"].shift(-self.chikou_len.value, freq=freq).dropna()
        return tenkan, kijun, senkou_A, senkou_B, chikou
