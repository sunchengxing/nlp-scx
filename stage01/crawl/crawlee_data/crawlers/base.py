import asyncio
from crawlee.crawlers import HttpCrawler, HttpCrawlingContext
from crawlee.router import Router
from loguru import logger
from crawlee_data.config import settings
from crawlee_data.pipelines.storage import StoragePipeline
from crawlee_data.utils.db import db


class BaseCrawler:
    """Base crawler with Crawlee routing + Peewee storage."""

    def __init__(self, name: str, start_urls: list[str]):
        self.name = name
        self.start_urls = start_urls
        self.router = Router()
        self.storage = StoragePipeline()
        self._setup_routes()

    def _setup_routes(self):
        @self.router.default_handler
        async def default_handler(context: HttpCrawlingContext):
            logger.info("Default handler: {}", context.request.url)

        self.default_handler = default_handler

    async def run(self):
        logger.info("Starting crawler [{}] with {} start URLs", self.name, len(self.start_urls))

        crawler = HttpCrawler(
            router=self.router,
            max_requests_per_crawl=0,
            max_concurrency=settings.crawl_concurrency,
        )

        try:
            await crawler.run(self.start_urls)
        finally:
            await self.storage.flush()

        logger.info("Crawler [{}] finished", self.name)


async def init_db():
    from crawlee_data.models.article import Article
    db.create_tables([Article], safe=True)
    logger.info("Database tables ensured")
