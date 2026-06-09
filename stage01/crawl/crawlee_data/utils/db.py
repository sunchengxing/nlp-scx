from dbutils.pooled_db import PooledDB
import pymysql
from peewee import MySQLDatabase
from loguru import logger
from crawlee_data.config import settings


class PooledMySQLDatabase(MySQLDatabase):

    def __init__(self):
        self._pool = None
        super().__init__("", register_tables=False)

    def _ensure_pool(self):
        if self._pool is not None:
            return
        self._pool = PooledDB(
            creator=pymysql,
            maxconnections=settings.db_pool_max,
            mincached=settings.db_pool_min,
            maxusage=settings.db_pool_maxusage,
            blocking=True,
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            charset="utf8mb4",
        )
        logger.info(
            "DB pool initialized: {}:{} / {} (min={}, max={})",
            settings.mysql_host,
            settings.mysql_port,
            settings.mysql_database,
            settings.db_pool_min,
            settings.db_pool_max,
        )

    def _connect(self):
        self._ensure_pool()
        conn = self._pool.connection()
        logger.debug("DB connection acquired from pool")
        return conn

    def close(self):
        if self._pool is not None:
            self._pool.close()
            logger.info("DB pool closed")


db = PooledMySQLDatabase()
