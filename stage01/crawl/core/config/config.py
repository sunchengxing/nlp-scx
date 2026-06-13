from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env 绝对路径，无论从哪个目录启动都能找到
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")

    # MySQL
    mysql_host: str = "138.201.173.21"
    mysql_port: int = 3360
    mysql_user: str = "root"
    mysql_password: str = "mylife@123"
    mysql_database: str = "crawlee_data"

    # DBUtils Pool
    db_pool_min: int = 3
    db_pool_max: int = 10
    db_pool_maxusage: int = 1000
    db_idle_timeout: int = 3600

    # Crawlee
    crawl_concurrency: int = 10
    crawl_retry_times: int = 3
    crawl_request_delay: float = 0.5

    # Log
    log_level: str = "INFO"
    log_file: str = "core.log"

    # AKShare 东方财富
    akshare_em_cookie: str = ""
    akshare_request_interval: float = 0.5

    # 远程服务器鉴权
    remote_server_url: str = "http://localhost:8900/api"
    remote_server_token: str = ""


settings = Settings()
