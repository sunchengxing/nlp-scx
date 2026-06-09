from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
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
    log_file: str = "crawlee_data.log"


settings = Settings()
