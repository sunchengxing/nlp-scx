from abc import ABC, abstractmethod


class BaseStockService(ABC):
    """
    股票服务抽象类
    由于市场不一样，具体实现由各个市场决定
    """

    @abstractmethod
    def sync_stock_list(self):
        """同步股票代码列表到数据库"""
        pass

    @abstractmethod
    def sync_kline_daily(self, symbol, period, start_date, end_date, adjust):
        """拉取并存储日/周/月K线"""
        pass

    @abstractmethod
    def sync_kline_minute(self, symbol, period, start_date, end_date, adjust):
        """拉取并存储分钟K线"""
        pass

    @abstractmethod
    def sync_lhb_detail(self, start_date, end_date):
        """拉取并存储龙虎榜详情"""
        pass

    @abstractmethod
    def sync_capital_flow_stock(self, symbol, market):
        """拉取并存储个股资金流"""
        pass
