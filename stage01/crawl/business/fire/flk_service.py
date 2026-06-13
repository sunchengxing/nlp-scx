"""国家法律法规数据库 (flk.npc.gov.cn) 采集服务

编排：FlkClient 搜索 → 提取元数据+下载链接 → 存库 (FireLawRegulation)
入库只存元数据和下载链接，不存正文。
正文下载走 download 任务。

断点续传：CheckpointManager 记录 last_page + completed_ids，
重启后跳过已完成页和已入库条目，避免重复请求。
"""
from datetime import datetime, timezone
from loguru import logger

from core.client.flk_client import FlkClient
from core.models.fire import FireLawRegulation
from core.utils.db import db
from core.utils.text_cleaner import TextCleaner
from core.utils.checkpoint import CheckpointManager


class FlkService:
    """国家法律法规数据库采集服务

    流程：FlkClient.search_laws → FlkClient.get_detail → 提取元数据+下载链接 → 存库
    """

    def __init__(self, request_delay: float = 1.5):
        self.client = FlkClient(request_delay=request_delay)
        self.total_saved = 0
        self.total_failed = 0
        self.cpm = None  # CheckpointManager，sync_laws 时初始化

    def sync_laws(
        self,
        keyword: str = "消防",
        law_type: str = "",
        max_pages: int = 0,
        resume: bool = False,
    ):
        """主入口：搜索法规 → 获取详情（元数据+下载链接）→ 存库

        Args:
            keyword: 搜索关键词
            law_type: 法规类型代码 (flfg/xzfg/dfxfg/sfjs/jcfg)，空=全部
            max_pages: 最大页数，0=不限
            resume: 是否断点续传（跳过已完成页和条目）
        """
        db.connect()
        db.create_tables([FireLawRegulation], safe=True)

        # 初始化 CheckpointManager
        cp_key = f"flk_{keyword}_{law_type}" if law_type else f"flk_{keyword}"
        self.cpm = CheckpointManager(
            f"checkpoints/{cp_key}.json",
            crawler_name="flk",
            source="flk.npc.gov.cn",
        )

        # 如果不是续传模式，重置检查点
        if not resume:
            self.cpm.reset()

        # 读取断点
        cp = self.cpm.load()
        start_page = cp.get("last_page", 1) if resume else 1
        completed_ids = set(cp.get("completed_ids", [])) if resume else set()

        logger.info("📋 FLK 采集开始: keyword='{}', type='{}', max_pages={}, resume={} (从第{}页继续)",
                     keyword, law_type or "全部", max_pages, resume, start_page)

        # 搜索第 1 页获取总数（必须请求，拿到 totalSizes）
        first_page = self.client.search_laws(keyword=keyword, law_type=law_type, page=1)
        if first_page is None:
            logger.error("❌ FLK 搜索失败，退出")
            return

        result = first_page.get("result", {})
        total = result.get("totalSizes", 0)
        size = result.get("size", 20)
        total_pages = (total + size - 1) // size if total > 0 else 1

        if max_pages > 0:
            total_pages = min(total_pages, max_pages)

        logger.info("📊 FLK 共 {} 条结果, {} 页, 从第 {} 页开始", total, total_pages, start_page)

        # 处理各页
        for p in range(start_page, total_pages + 1):
            if p == start_page and start_page == 1:
                page_data = first_page  # 第 1 页已获取
            else:
                page_data = self.client.search_laws(keyword=keyword, law_type=law_type, page=p)
                if page_data is None:
                    logger.warning("⚠️ FLK 第 {} 页获取失败，跳过", p)
                    continue

            items = page_data.get("result", {}).get("data", [])
            self._process_items(items, completed_ids)

            # 每页处理完保存进度
            self.cpm.save({"last_page": p + 1, "total_items": total})

        logger.info("✅ FLK 采集完成: 入库 {} 条, 失败 {} 条",
                     self.total_saved, self.total_failed)

    def _process_items(self, items: list, completed_ids: set):
        """处理一页的法律条目：跳过已完成的 → 获取详情 → 存元数据+下载链接"""
        for item in items:
            law_id = item.get("id", "")

            # 断点续传：跳过已入库的条目
            if law_id in completed_ids:
                logger.debug("⏭️ FLK 跳过已完成: {}", item.get("title", ""))
                continue

            title = item.get("title", "未知标题")

            # 获取详情（含下载路径）
            detail = self.client.get_detail(law_id)
            if not detail:
                self._save_summary(item)
                self.cpm.mark_complete(law_id)
                continue

            detail_result = detail.get("result", {})

            # 提取下载链接（优先 WORD → HTML）
            download_url = ""
            file_type = ""
            body_files = detail_result.get("body", [])
            for doc_type in ("WORD", "HTML", "HTM"):
                for f in body_files:
                    if f.get("type", "").upper() == doc_type and f.get("path"):
                        download_url = self.client.FILE_BASE_URL + f["path"]
                        file_type = doc_type
                        break
                if download_url:
                    break

            self._save_law(item, detail_result, download_url, file_type)
            self.cpm.mark_complete(law_id)

    def _save_law(self, item: dict, detail_result: dict,
                  download_url: str, file_type: str):
        """保存法规元数据+下载链接到数据库"""
        law_id = item.get("id", "")

        title = detail_result.get("title", item.get("title", ""))
        office = detail_result.get("office", item.get("office", ""))
        publish = detail_result.get("publish", item.get("publish", ""))

        type_code = item.get("type", "")
        doc_type = self.client.resolve_type_name(type_code) if type_code else "法律"
        publish_date = TextCleaner.extract_date(publish) or publish

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "source": "flk",
            "doc_id": law_id,
            "title": title,
            "doc_type": doc_type,
            "publisher": office,
            "publish_date": publish_date,
            "effective_date": "",
            "status": item.get("status", "现行有效"),
            "document_number": "",
            "hierarchy": doc_type,
            "source_url": f"https://flk.npc.gov.cn/detail2.html?{law_id}",
            "download_url": download_url,
            "file_type": file_type,
            "local_file_path": "",
            "created_at": now,
            "updated_at": now,
            "fetched_at": now,
        }

        if self._raw_upsert(row):
            self.total_saved += 1
            logger.info("✅ FLK 入库: {} [{}]", title, file_type or "无下载")
        else:
            self.total_failed += 1

    def _save_summary(self, item: dict):
        """详情获取失败时，用搜索结果的基本信息存库"""
        type_code = item.get("type", "")
        doc_type = self.client.resolve_type_name(type_code) if type_code else "法律"
        publish_date = TextCleaner.extract_date(item.get("publish", "")) or item.get("publish", "")

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "source": "flk",
            "doc_id": item.get("id", ""),
            "title": item.get("title", ""),
            "doc_type": doc_type,
            "publisher": item.get("office", ""),
            "publish_date": publish_date,
            "effective_date": "",
            "status": item.get("status", "现行有效"),
            "document_number": "",
            "hierarchy": doc_type,
            "source_url": f"https://flk.npc.gov.cn/detail2.html?{item.get('id', '')}",
            "download_url": "",
            "file_type": "",
            "local_file_path": "",
            "created_at": now,
            "updated_at": now,
            "fetched_at": now,
        }

        if self._raw_upsert(row):
            self.total_saved += 1

    def _raw_upsert(self, row: dict) -> bool:
        """MySQL upsert: INSERT ... ON DUPLICATE KEY UPDATE"""
        try:
            table = FireLawRegulation._meta.table_name
            fields = list(row.keys())
            cols = ", ".join(f"`{f}`" for f in fields)
            placeholders = ", ".join(["%s"] * len(fields))
            update_cols = ", ".join(
                f"`{f}`=VALUES(`{f}`)" for f in fields if f not in ("source", "doc_id")
            )
            sql = (
                f"INSERT INTO `{table}` ({cols}) VALUES ({placeholders}) "
                f"ON DUPLICATE KEY UPDATE {update_cols}"
            )
            values = tuple(row[f] for f in fields)

            conn = db.connection()
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            return True
        except Exception as e:
            logger.warning("⚠️ FLK upsert 失败: {}", e)
            return False
