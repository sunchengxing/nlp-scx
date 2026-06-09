# -*- coding: utf-8 -*-
import asyncio
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
import logging

logging.getLogger("crawlee").setLevel(logging.WARNING)


async def main():
    crawler = PlaywrightCrawler(
        max_requests_per_crawl=1,
        headless=True,
    )

    @crawler.router.default_handler
    async def request_handler(context: PlaywrightCrawlingContext):

        await context.page.wait_for_load_state("networkidle")

        items = context.page.locator("ul#hotsearch-content-wrapper > li.hotsearch-item")
        count = await items.count()

        results = []
        for i in range(count):
            li = items.nth(i)

            rank = await li.get_attribute("data-index")
            title = await li.locator("span.title-content-title").text_content()
            link = await li.locator("a.title-content").get_attribute("href")

            tag_el = li.locator("span.c-text-hot, span.c-text-new")
            tag = await tag_el.text_content() if await tag_el.count() > 0 else ""

            results.append({
                "rank": int(rank) if rank else None,
                "title": title.strip() if title else "",
                "link": link.strip() if link else "",
                "tag": tag.strip() if tag else "",
            })

        for item in sorted(results, key=lambda x: x["rank"] or 0):
            tag_str = f"  [{item['tag']}]" if item['tag'] else ""
            print(f"{(item['rank'] + 1):>2}. {item['title']}{tag_str}")
            print(f"    {item['link']}")

    await crawler.run(["https://www.baidu.com/"])


if __name__ == "__main__":
    asyncio.run(main())
