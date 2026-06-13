from loguru import logger
from core.models.article import Article
from peewee import IntegrityError


class StoragePipeline:

    def __init__(self, batch_size: int = 500):
        self.batch_size = batch_size
        self._buffer: list[dict] = []

    async def process_item(self, item: dict):
        self._buffer.append(item)
        if len(self._buffer) >= self.batch_size:
            await self.flush()

    async def flush(self):
        if not self._buffer:
            return
        saved = 0
        for item in self._buffer:
            try:
                Article.create(**item)
                saved += 1
            except IntegrityError:
                Article.update(**item).where(Article.url == item["url"]).execute()
        logger.info("Storage flush: {} items ({} new, {} updated)", len(self._buffer), saved, len(self._buffer) - saved)
        self._buffer.clear()
