import time
from loguru import logger
from core.config import settings
from core.utils.request import HttpRequest, ContentType, HttpHeaders, UserAgent


class EastmoneyClient:
    """东方财富 AKShare 远程接口客户端"""

    def __init__(self):
        self.base_url = settings.remote_server_url  # http://138.201.173.21:8900/api
        self.cookie = settings.akshare_em_cookie
        self.interval = settings.akshare_request_interval
        self._last_request_time = 0.0
        self.http = HttpRequest(
            headers={HttpHeaders.USER_AGENT.value: UserAgent.CHROME.value},
            cookies={},
            bearer_token=settings.remote_server_token,
            content_type=ContentType.JSON,
        )

    def _rate_limit(self):
        """请求间隔控制"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self._last_request_time = time.time()

    def post_api(self, endpoint: str, json_data: dict = None):
        """统一请求方法：base_url + / + endpoint"""
        self._rate_limit()
        url = f"{self.base_url}/{endpoint}"
        try:
            resp = self.http.do_post(url, json=json_data or {})
            logger.info("✅ POST {}/{} → OK", self.base_url, endpoint)
            return resp
        except Exception as e:
            logger.error("❌ POST {}/{} → {}", self.base_url, endpoint, e)
            raise


    """获取所有A股代码"""
    def fetch_stock_list(self):
        """获取所有A股代码"""
        return self.post_api("stock_info_a_code_name")

    """日/周/月K线"""
    def fetch_kline_daily(self, symbol, period="daily",
                          start_date="19700101", end_date="20500101", adjust="qfq"):
        """日/周/月K线"""
        return self.post_api("stock_zh_a_hist", {
            "symbol": symbol, "period": period,
            "start_date": start_date, "end_date": end_date, "adjust": adjust,
        })


    def fetch_kline_minute(self, symbol, period="5",
                           start_date="1979-09-01 09:32:00",
                           end_date="2222-01-01 09:32:00", adjust=""):
        """分钟K线"""
        return self.post_api("stock_zh_a_hist_min_em", {
            "symbol": symbol, "period": period,
            "start_date": start_date, "end_date": end_date, "adjust": adjust,
        })



    def fetch_lhb_detail(self, start_date, end_date):
        """龙虎榜详情"""
        return self.post_api("stock_lhb_detail_em", {
            "start_date": start_date, "end_date": end_date,
        })

    def fetch_lhb_seat_detail(self, symbol, date, flag="卖出"):
        """席位买卖明细"""
        return self.post_api("stock_lhb_stock_detail_em", {
            "symbol": symbol, "date": date, "flag": flag,
        })


    def fetch_capital_flow_stock(self, symbol, market="sz"):
        """个股资金流"""
        return self.post_api("stock_individual_fund_flow", {
            "stock": symbol, "market": market,
        })

    def fetch_capital_flow_market(self):
        """大盘资金流"""
        return self.post_api("stock_market_fund_flow")

    def fetch_capital_flow_main(self, symbol="全部股票"):
        """主力净流入排名"""
        return self.post_api("stock_main_fund_flow", {"symbol": symbol})
