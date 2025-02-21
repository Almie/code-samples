import pandas as pd

from ..config import Config

import os
from sqlalchemy.dialects.sqlite import insert
import sqlalchemy as sqla

from ..utils import singleton, timer_func

import pandas_market_calendars as mcal
from pandas.tseries.offsets import YearBegin, CustomBusinessDay

from .types import *

@singleton
class MarketDataCache(object):
    SQLITE_FILE = "%LOCALAPPDATA%\\StonX\\cache.sqlite"
    def __init__(self):
        self._db = sqla.create_engine('sqlite:///{}'.format(os.path.expandvars(self.SQLITE_FILE)))
        self.config = Config()
        self.twsTimezone = self.config.get_property("timezone_tws", "US/Pacific")

    @timer_func
    def addData(self, symbol, dataType, dataframe, data_source):
        with self._db.connect() as connection:
            chunk_size = 2000
            for start in range(0, dataframe.shape[0], chunk_size):
                df_subset = dataframe.iloc[start:start + chunk_size]
                self._save_sql(symbol, dataType, df_subset, connection)
            chunks = self._get_chunks_for_range(dataframe.index[0], dataframe.index[-1], dataType)
            self._add_chunks(symbol, dataType, chunks, data_source, connection)

    @timer_func
    def _add_chunks(self, symbol, dataType, chunkDates, data_source, connection):
        chunk_db_name = f'{symbol}_{dataType}_chunks'
        if not sqla.inspect(self._db).has_table(chunk_db_name):
            self._create_table_chunks(symbol, dataType)
        chunkDates = chunkDates.tz_convert('US/Eastern')

        #don't mark today as cached
        now = pd.Timestamp.now(tz='US/Eastern')
        chunkDates = chunkDates[now - chunkDates >= pd.Timedelta('1d')]
        if chunkDates.empty:
            return

        metadata = sqla.MetaData()
        chunk_table = sqla.Table(chunk_db_name, metadata, autoload_with=self._db)
        chunk_stmt = insert(chunk_table).values([{'date': date, 'data_source': data_source} for date in chunkDates.tolist()])
        chunk_stmt = chunk_stmt.on_conflict_do_update(
            index_elements=['date'],
            set_=dict(data_source=data_source)
            )
        connection.execute(chunk_stmt)

    @timer_func
    def getData(self, symbol, dataType, startTime, endTime):
        with self._db.connect() as connection:
            db_name = f'{symbol}_{dataType}'
            if not sqla.inspect(self._db).has_table(db_name):
                self._create_table(symbol, dataType)
                return None
            startTime = startTime.tz_convert('UTC')
            endTime = endTime.tz_convert('UTC')
            dataframe = pd.read_sql(f"SELECT * FROM {db_name} WHERE datetime(date) BETWEEN '{startTime.strftime('%Y-%m-%d %X')}' AND '{endTime.strftime('%Y-%m-%d %X')}'",
                                    connection.connection,
                                    index_col='date',
                                    parse_dates={'date': {'errors': 'ignore',
                                                            'infer_datetime_format': True,
                                                            'utc' : True
                                                            }})
            dataframe.index = dataframe.index.tz_convert(self.twsTimezone)
            return dataframe

    def getMissingRange(self, symbol, dataType, startTime, endTime):
        db_name = f'{symbol}_{dataType}_chunks'
        chunks = self._get_chunks_for_range(startTime, endTime, dataType)
        end_offset = pd.Timedelta('1d') if is_intraday(dataType) else YearBegin()

        if not sqla.inspect(self._db).has_table(db_name):
            self._create_table_chunks(symbol, dataType)
            return chunks[0], chunks[-1] + end_offset
        print(f"SELECT * FROM {db_name} WHERE datetime(date) BETWEEN '{startTime.strftime('%Y-%m-%d')}' AND '{endTime.strftime('%Y-%m-%d')}'")
        with self._db.connect() as connection:
            existing_chunks = pd.read_sql(f"SELECT * FROM {db_name} WHERE datetime(date) BETWEEN '{startTime.strftime('%Y-%m-%d')}' AND '{endTime.strftime('%Y-%m-%d')}'",
                                            connection.connection,
                                            index_col='date',
                                            parse_dates={'date': {'errors': 'ignore',
                                                            'infer_datetime_format': True,
                                                            'utc' : False
                                                            }}
                                            )
            existing_chunks.index = existing_chunks.index.tz_localize('US/Eastern')
            print('EXISTING CHUNKS: ', existing_chunks.index)
            missing_chunks = chunks.difference(existing_chunks.index)
            print('MISSING CHUNKS: ', missing_chunks)
            if missing_chunks.empty:
                return None, None
            missing_chunks = missing_chunks.tz_convert(self.twsTimezone)
            return missing_chunks[0], missing_chunks[-1] + end_offset

    @timer_func
    def _get_chunks_for_range(self, startTime, endTime, dataType):
        if is_intraday(dataType):
            calendar = mcal.get_calendar('NYSE')
            bDay = CustomBusinessDay(calendar=calendar)
            startTime = startTime.tz_convert('US/Eastern').floor(freq='D')
            endTime = endTime.tz_convert('US/Eastern').floor(freq='D')
            chunks = pd.date_range(startTime, endTime, freq=bDay)
        else:
            yearOffset = YearBegin()
            startTime = yearOffset.rollback(startTime.tz_convert('US/Eastern'))
            endTime = yearOffset.rollback(endTime.tz_convert('US/Eastern'))
            chunks = pd.date_range(startTime, endTime, freq=yearOffset)
        return chunks

    def _create_table(self, symbol, dataType):
        db_name = f'{symbol}_{dataType}'
        metadata_obj = sqla.MetaData(info={'timezone':self.twsTimezone})
        table = sqla.Table(db_name, metadata_obj,
                    sqla.Column('date', sqla.DateTime, index=True, unique=True),
                    sqla.Column('open', sqla.Float),
                    sqla.Column('high', sqla.Float),
                    sqla.Column('low', sqla.Float),
                    sqla.Column('close', sqla.Float),
                    sqla.Column('volume', sqla.Float)
                    )
        table.create(self._db)
    
    def _create_table_chunks(self, symbol, dataType):
        db_name = f'{symbol}_{dataType}_chunks'
        metadata_obj = sqla.MetaData()
        table = sqla.Table(db_name, metadata_obj,
                    sqla.Column('date', sqla.DateTime, index=True, unique=True),
                    sqla.Column('data_source', sqla.String)
                    )
        table.create(self._db)

    def _sql_insert_on_duplicate(self, table, conn, keys, data_iter):
        insert_statement = insert(table.table).values(list(data_iter))
        on_conflict_statement = insert_statement.on_conflict_do_update(
            index_elements=['date'],
            set_=dict(
                    open=insert_statement.excluded.open,
                    high=insert_statement.excluded.high,
                    low=insert_statement.excluded.low,
                    close=insert_statement.excluded.close,
                    volume=insert_statement.excluded.volume
                )
            )
        conn.execute(on_conflict_statement)

    def _sql_insert_on_duplicate_chunk(self, table, conn, keys, data_iter):
        insert_statement = insert(table.table).values(list(data_iter))
        on_conflict_statement = insert_statement.on_conflict_do_update(
            index_elements=['date'],
            set_=dict(
                    data_source=insert_statement.excluded.data_source
                )
            )
        conn.execute(on_conflict_statement)

    @timer_func
    def _save_sql(self, symbol, dataType, data, connection):
        data = data.copy()
        db_name = f'{symbol}_{dataType}'
        if not sqla.inspect(self._db).has_table(db_name):
            self._create_table(symbol, dataType)
        data.index = data.index.tz_convert('UTC')
        data.to_sql(db_name, connection,
                    index_label='date',
                    if_exists='append',
                    method=self._sql_insert_on_duplicate)
