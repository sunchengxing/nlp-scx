import asyncio
from crawlee.crawlers import HttpCrawlingContext
from parsel import Selector
from loguru import logger
from crawlee_data.crawlers.base import BaseCrawler, init_db
from crawlee_data.parsers.extractor import extract_field


class ExampleCrawler(BaseCrawler):

    def __init__(self, start_urls: list[str] | None = None):
        super().__init__(
            name="example",
            start_urls=start_urls or ["https://books.toscrape.com"],
        )

    def _setup_routes(self):
        self.router.handler("catalogue")(self.detail_handler)
        self.router.default_handler(self.list_handler)

    async def list_handler(self, context: HttpCrawlingContext):
        logger.info("List page: {}", context.request.loaded_url)
        sel = Selector(text=context.http_response.read().decode())

        for link in sel.css("article.product_pod h3 a::attr(href)").getall():
            await context.add_requests([context.request.loaded_url.rsplit("/", 1)[0] + "/" + link])

        next_page = sel.css("li.next a::attr(href)").get()
        if next_page:
            await context.add_requests([context.request.loaded_url.rsplit("/", 1)[0] + "/" + next_page])

    async def detail_handler(self, context: HttpCrawlingContext):
        sel = Selector(text=context.http_response.read().decode())

        item = {
            "url": context.request.loaded_url,
            "title": extract_field(sel, "h1::text"),
            "source": "books.toscrape.com",
        }
        await self.storage.process_item(item)


async def main():
    await init_db()
    crawler = ExampleCrawler()
    await crawler.run()


if __name__ == "__main__":
    asyncio.run(main())
