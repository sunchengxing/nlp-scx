"""应急管理部 (mem.gov.cn) 采集服务

编排：MemClient 抓取 → 提取元数据+下载链接 → 存库 (FireLawRegulation + FireIndustryDoc)
入库只存元数据和下载链接，不存正文。
正文/PDF 下载走 download 任务。

断点续传：CheckpointManager 记录 current_section + completed_urls，
重启后跳过已完成栏目和条目，避免重复请求。
"""
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger

from core.client.mem_client import MemClient, SECTIONS
from core.models.fire import FireLawRegulation, FireIndustryDoc
from core.utils.db import db
from core.utils.text_cleaner import TextCleaner
from core.utils.checkpoint import CheckpointManager


class MemService:
    """应急管理部采集服务

    流程：MemClient.fetch_list → MemClient.fetch_detail → 提取元数据+下载链接 → 存库
    """

    def __init__(self, request_delay: float = 1.5):
        self.client = MemClient(request_delay=request_delay)
        self.total_saved = 0
        self.total_failed = 0
        self.cpm = None

    def sync_regulations(
        self,
        sections: list[str] | None = None,
        max_pages: int = 0,
        fire_only: bool = True,
        resume: bool = False,
    ):
        """主入口：抓取各栏目 → 提取元数据+下载链接 → 存库

        Args:
            sections: 栏目代码列表，如 ["bl", "tz"]；None 则使用默认 [bl, tz, yjbgg]
            max_pages: 每栏目最大页数，0=不限
            fire_only: 仅采集消防相关条目
            resume: 是否断点续传
        """
        db.connect()
        db.create_tables([FireLawRegulation, FireIndustryDoc], safe=True)

        if sections is None:
            sections = ["bl", "tz", "yjbgg"]

        # 初始化 CheckpointManager
        self.cpm = CheckpointManager(
            "checkpoints/mem.json",
            crawler_name="mem",
            source="mem.gov.cn",
        )
        if not resume:
            self.cpm.reset()

        # 读取断点
        cp = self.cpm.load()
        completed_urls = set(cp.get("completed_urls", [])) if resume else set()
        done_sections = set(cp.get("done_sections", [])) if resume else set()

        logger.info("📋 MEM 采集开始: sections={}, max_pages={}, fire_only={}, resume={}",
                     sections, max_pages, fire_only, resume)

        for section_code in sections:
            # 断点续传：跳过已完成的栏目
            if section_code in done_sections:
                logger.info("⏭️ MEM 栏目已完成: {}", section_code)
                continue

            section_info = SECTIONS.get(section_code)
            if not section_info:
                logger.warning("⚠️ MEM 未知栏目: {}", section_code)
                continue

            logger.info("=" * 50)
            logger.info("📂 MEM 栏目: {} ({})", section_info["name"], section_info["description"])

            # 抓取列表页
            entries = self.client.fetch_list(section_code, page=0)

            # 自动探测后续页
            if max_pages != 1:
                for p in range(1, max_pages if max_pages > 0 else 20):
                    more = self.client.fetch_list(section_code, page=p)
                    if not more:
                        break
                    entries.extend(more)
                    if max_pages > 0 and p >= max_pages - 1:
                        break

            # 消防相关过滤
            if fire_only:
                entries = [e for e in entries if MemClient.is_fire_related(e["title"])]
                logger.info("🔥 MEM 消防相关: {} 条", len(entries))

            # 逐条抓详情
            for i, entry in enumerate(entries):
                entry_url = entry["url"]

                # 断点续传：跳过已处理的条目
                if entry_url in completed_urls:
                    logger.debug("⏭️ MEM 跳过已完成: {}", entry["title"][:40])
                    continue

                logger.info("[{}/{}] {}", i + 1, len(entries), entry["title"][:60])
                try:
                    detail = self.client.fetch_detail(entry_url)
                    if detail:
                        self._save_regulation(detail, section_code)
                    else:
                        self.total_failed += 1

                    # 标记该条目已完成（无论详情是否成功，避免卡死循环）
                    completed_urls.add(entry_url)
                    self.cpm.save({"completed_urls": list(completed_urls)})

                except Exception as e:
                    logger.error("❌ MEM 详情抓取失败: {} — {}", entry_url, e)
                    self.total_failed += 1

            # 标记该栏目已完成
            done_sections.add(section_code)
            self.cpm.save({"done_sections": list(done_sections)})

        logger.info("✅ MEM 采集完成: 入库 {} 条, 失败 {} 条",
                     self.total_saved, self.total_failed)

    def _save_regulation(self, detail: dict, section_code: str):
        """保存法规元数据+下载链接到数据库"""
        source_url = detail.get("source_url", "")
        doc_id = MemClient.hash_url(source_url)

        metadata = detail.get("metadata", {})
        document_number = metadata.get("索引号", metadata.get("文号", ""))
        publisher = metadata.get("发文单位", metadata.get("制定机关", "应急管理部"))
        effective_date = metadata.get("施行日期", "")

        pdf_urls = detail.get("pdf_urls", [])
        main_download_url = pdf_urls[0] if pdf_urls else ""

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "source": f"mem_{section_code}",
            "doc_id": doc_id,
            "title": detail.get("title", ""),
            "doc_type": "部门规章" if section_code == "bl" else "规范性文件",
            "publisher": publisher,
            "publish_date": detail.get("publish_date", ""),
            "effective_date": effective_date,
            "status": "现行有效",
            "document_number": document_number,
            "hierarchy": "部门规章" if section_code == "bl" else "规范性文件",
            "source_url": source_url,
            "download_url": main_download_url,
            "file_type": "PDF" if pdf_urls else "HTML",
            "local_file_path": "",
            "created_at": now,
            "updated_at": now,
            "fetched_at": now,
        }

        if self._raw_upsert_law(row):
            self.total_saved += 1
            logger.info("✅ MEM 入库: {}", row["title"])

        # PDF 附件 → FireIndustryDoc
        for pdf_url in pdf_urls:
            self._save_industry_doc(pdf_url, section_code)

    def _save_industry_doc(self, pdf_url: str, section_code: str):
        """保存 PDF 附件的下载链接到 FireIndustryDoc"""
        doc_id = MemClient.hash_url(pdf_url)

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "source": f"mem_{section_code}",
            "doc_id": doc_id,
            "title": Path(pdf_url).stem,
            "standard_no": "",
            "doc_type": "通知附件",
            "publish_date": "",
            "status": "现行有效",
            "source_url": pdf_url,
            "download_url": pdf_url,
            "local_pdf_path": "",
            "created_at": now,
            "updated_at": now,
            "fetched_at": now,
        }

        try:
            table = FireIndustryDoc._meta.table_name
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
        except Exception as e:
            logger.warning("⚠️ MEM IndustryDoc upsert 失败: {}", e)

    def _raw_upsert_law(self, row: dict) -> bool:
        """MySQL upsert"""
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
            logger.warning("⚠️ MEM upsert 失败: {}", e)
            return False
