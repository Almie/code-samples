import pandas as pd
import numpy as np
from pandas._libs.tslibs.offsets import BaseOffset, apply_wraps
from pandas.tseries.offsets import MonthBegin, Week, CustomBusinessDay
from pandas.tseries.holiday import USFederalHolidayCalendar
import pandas_market_calendars as mcal
from time import time
import math
from functools import cache

def get_market_hours(tz='US/Eastern', format='%H:%M'):
    eastCoastTimes = ["04:00", "09:30", "16:00", "20:00"]
    convertedTimes = [pd.Timestamp(t).tz_localize('US/Eastern').tz_convert(tz).strftime(format) for t in eastCoastTimes]
    return tuple(convertedTimes)

def trading_offset_factory(barSize='1m', start='04:00', end='20:00'):
    class TradingOffset(BaseOffset):
        _barSize = barSize
        _start = start
        _end = end
        calendar = mcal.get_calendar('NYSE')
        bDay = CustomBusinessDay(holidays=calendar.holidays().holidays)
        __init__ = BaseOffset.__init__

        def barSizeToPandasFreq(self, bSize):
            freq = bSize.replace('m', 'T')
            return freq

        def _round(self, t, freq):
            if 'M' in freq:
                monthBegin = MonthBegin()
                new = t.floor(freq='1D')
                if monthBegin.is_on_offset(new):
                    return new
                else:
                    return new - monthBegin
            elif 'W' in freq:
                week = Week(weekday=0)
                new = t.floor(freq='1D')
                if week.is_on_offset(new):
                    return new
                else:
                    return new - week
            else:
                return t.floor(freq=freq)

        def nextDay(self, other):
            freq = self.barSizeToPandasFreq(self._barSize)
            new = self._round(other, freq)
            openTime = pd.Timestamp(self._start).floor(freq=freq)
            new = new + self.bDay
            new = new.replace(hour=openTime.hour,
                            minute=openTime.minute,
                            second=openTime.second)
            return new

        def previousDay(self, other):
            freq = self.barSizeToPandasFreq(self._barSize)
            new = self._round(other, freq)
            closeTime = pd.Timestamp(self._end).floor(freq=freq) - pd.Timedelta(freq)
            new = new - self.bDay
            new = new.replace(hour=closeTime.hour,
                            minute=closeTime.minute,
                            second=closeTime.second)
            return new

        @cache
        def seconds_per_day(self):
            return (self.closeTime() - self.openTime()).total_seconds()

        @cache
        def openTime(self):
            freq = self.barSizeToPandasFreq(self._barSize)
            return pd.Timestamp(self._start).floor(freq=freq)

        @cache
        def closeTime(self):
            freq = self.barSizeToPandasFreq(self._barSize)
            return pd.Timestamp(self._end).floor(freq=freq)

        def timestamp(self, timestamp):
            rolledBack = self.rollback(timestamp)
            epochTime = self.rollforward(pd.Timestamp("1970-01-01 00:00:00").tz_localize('UTC').tz_convert(timestamp.tz))
            days = np.busday_count(epochTime.strftime('%Y-%m-%d'), rolledBack.strftime('%Y-%m-%d'), holidays=self.calendar.holidays().holidays)

            seconds_per_day = self.seconds_per_day()

            openTime = self.openTime()
            dayStartTime = rolledBack.replace(hour=openTime.hour, minute=openTime.minute, second=openTime.second)
            seconds = (rolledBack - dayStartTime).total_seconds()

            final_timestamp = days*seconds_per_day + seconds
            return final_timestamp

        def fromtimestamp(self, timestamp, tz='UTC'):
            epochTime = self.rollforward(pd.Timestamp("1970-01-01 00:00:00").tz_localize('UTC').tz_convert(tz))
            epochDate = epochTime.strftime('%Y-%m-%d')

            seconds_per_day = self.seconds_per_day()
            days = math.floor(timestamp / seconds_per_day)
            date = np.busday_offset(epochDate, days, roll='forward', holidays=self.calendar.holidays().holidays)

            openTime = self.openTime()
            dayStartTime = pd.Timestamp(date).replace(hour=openTime.hour, minute=openTime.minute, second=openTime.second)
            daySeconds = timestamp % seconds_per_day
            finalTime = dayStartTime + pd.Timedelta(f'{daySeconds}s')
            return finalTime



        @apply_wraps
        def _apply(self, other):
            freq = self.barSizeToPandasFreq(self._barSize)
            if 'D' in freq or 'W' in freq or 'M' in freq:
                return self._apply_multiday(other, freq)
            else:
                return self._apply_intraday(other, freq)

        def _apply_multiday(self, other, freq):
            new = self._round(other, freq)
            openTime = pd.Timestamp(self._start).floor(freq=freq)
            closeTime = pd.Timestamp(self._end).floor(freq=freq)
            n = self.n
            if not self.bDay.is_on_offset(new):
                if n > 0:
                    new = new + self.bDay
                    n -= 1
                if n < 0:
                    new = new - self.bDay
                    n += 1

            for i in range(abs(n)):
                if n > 0:
                    new += self.bDay
                    n -= 1
                else:
                    new -= self.bDay
                    n += 1
            return new

        def _apply_intraday(self, other, freq):
            new = self._round(other, freq)
            openTime = pd.Timestamp(self._start).floor(freq=freq)
            closeTime = pd.Timestamp(self._end).floor(freq=freq) - pd.Timedelta(freq)
            n = self.n
            if not self.bDay.is_on_offset(new):
                if n > 0:
                    new = new + self.bDay
                    new = new.replace(hour=openTime.hour,
                                    minute=openTime.minute,
                                    second=openTime.second)
                    if n > 1:
                        n -= 1
                    else:
                        return new
                else:
                    new = new - self.bDay
                    new = new.replace(hour=closeTime.hour,
                                    minute=closeTime.minute,
                                    second=closeTime.second)
                    if n < -1:
                        n += 1
                    else:
                        return new
            dayOpenTime = openTime.replace(year=new.year,month=new.month,day=new.day)
            dayCloseTime = closeTime.replace(year=new.year,month=new.month,day=new.day)
            for i in range(abs(n)):
                if n > 0:
                    new = new + pd.Timedelta(freq)
                    if (new - dayOpenTime) < pd.Timedelta(0):
                        new = dayOpenTime
                    elif (new - dayCloseTime) > pd.Timedelta(0):
                        new = dayOpenTime + self.bDay
                        dayOpenTime += self.bDay
                        dayCloseTime += self.bDay
                else:
                    new = new - pd.Timedelta(freq)
                    if (new - dayOpenTime) < pd.Timedelta(0):
                        new = dayCloseTime - self.bDay
                        dayOpenTime -= self.bDay
                        dayCloseTime -= self.bDay
                    elif (new - dayCloseTime) > pd.Timedelta(0):
                        new = dayCloseTime

            return new
    return TradingOffset()

def pre_post_market_offset_factory(preMarketOpen='04:00', marketOpen='09:30', marketClose='16:00', postMarketClose='20:00'):
    class PrePostMarketOffset(BaseOffset):
        _offsetTimes = [preMarketOpen, marketOpen, marketClose, postMarketClose]
        bDay = CustomBusinessDay(calendar=USFederalHolidayCalendar())
        __init__ = BaseOffset.__init__

        @apply_wraps
        def _apply(self, other):
            n = self.n
            new = other
            offsetTimes = [pd.Timestamp(t) for t in self._offsetTimes]

            # Make sure timestamp is on business day
            if not self.bDay.is_on_offset(other):
                if n > 0:
                    new += self.bDay
                    new = new.replace(hour=offsetTimes[0].hour, minute=offsetTimes[0].minute, second=offsetTimes[0].second)
                    n -= 1
                if n < 0:
                    new -= self.bDay
                    new = new.replace(hour=offsetTimes[-1].hour, minute=offsetTimes[-1].minute, second=offsetTimes[-1].second)
                    n += 1

            # Make sure timestamp is on offset time
            dayOffsetTimes = [t.replace(year=new.year, month=new.month, day=new.day) for t in offsetTimes]
            method = 'ffill' if n < 0 else 'bfill'
            dayOffsetIndex = pd.DatetimeIndex(dayOffsetTimes).get_indexer([new], method=method)[0]
            if dayOffsetIndex == -1:
                if n < 0:
                    new -= self.bDay
                    dayOffsetTimes = [t.replace(year=new.year, month=new.month, day=new.day) for t in offsetTimes]
                    new = dayOffsetTimes[-1]
                if n > 0:
                    new += self.bDay
                    dayOffsetTimes = [t.replace(year=new.year, month=new.month, day=new.day) for t in offsetTimes]
                    new = dayOffsetTimes[0]
            elif new != dayOffsetTimes[dayOffsetIndex]:
                new = dayOffsetTimes[dayOffsetIndex]
                if n > 0:
                    n -= 1
                if n < 0:
                    n += 1

            #Add additional offsets
            while abs(n) > 0:
                if n > 0:
                    n -= 1
                    dayOffsetIndex += 1
                    if dayOffsetIndex > len(dayOffsetTimes) - 1:
                        dayOffsetIndex = 0
                        new += self.bDay
                if n < 0:
                    n += 1
                    dayOffsetIndex -= 1
                    if dayOffsetIndex < 0:
                        dayOffsetIndex = len(dayOffsetTimes) - 1
                        new -= self.bDay
                new = new.replace(hour=dayOffsetTimes[dayOffsetIndex].hour,
                            minute=dayOffsetTimes[dayOffsetIndex].minute,
                            second=dayOffsetTimes[dayOffsetIndex].second)
            return new
    return PrePostMarketOffset()

def infer_freq(barData):
        return barData.index.to_series().diff().median()

def singleton(class_):
    instances = {}
    def getinstance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]
    return getinstance

def timer_func(func):
    # This function shows the execution time of
    # the function object passed
    def wrap_func(*args, **kwargs):
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        print(f'Function {func.__qualname__!r} executed in {(t2-t1):.4f}s')
        return result
    return wrap_func
