"""地方政府网站法规采集服务

编排：LocalGovClient 抓取 → 提取元数据+下载链接 → 存库 (FireLawRegulation)
入库只存元数据和下载链接，不存正文。
正文下载走 download 任务。

断点续传：CheckpointManager 记录 done_sites + completed_urls，
重启后跳过已完成站点和条目，避免重复请求。

站点配置从 scripts/sites_config.json 加载
"""
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger

from core.client.local_gov_client import LocalGovClient, SiteConfig
from core.models.fire import FireLawRegulation
from core.utils.db import db
from core.utils.checkpoint import CheckpointManager


# 默认配置文件路径（相对于 crawl 项目根目录）
DEFAULT_CONFIG_PATH = str(Path(__file__).resolve().parents[3] / "scripts" / "sites_config.json")


class LocalGovService:
    """地方政府网站法规采集服务

    流程：LocalGovClient.fetch_list → LocalGovClient.fetch_detail → 提取元数据+下载链接 → 存库
    """

    def __init__(self, request_delay: float = 1.5, config_path: str = ""):
        self.client = LocalGovClient(request_delay=request_delay)
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.total_saved = 0
        self.total_failed = 0
        self.cpm = None

    def sync_regulations(
        self,
        config_path: str = "",
        site_ids: list[str] | None = None,
        keyword: str = "消防",
        resume: bool = False,
    ):
        """主入口：按配置抓取地方性法规 → 存库

        Args:
            config_path: 站点配置文件路径（覆盖初始化时的路径）
            site_ids: 指定采集的 site_id，None=全部启用站点
            keyword: 标题关键词过滤（空=不过滤）
            resume: 是否断点续传
        """
        db.connect()
        db.create_tables([FireLawRegulation], safe=True)

        path = config_path or self.config_path
        sites = LocalGovClient.load_sites_config(path)
        if not sites:
            logger.error("❌ 无可用站点配置: {}", path)
            return

        if site_ids:
            sites = [s for s in sites if s.site_id in site_ids]

        # 初始化 CheckpointManager
        self.cpm = CheckpointManager(
            "checkpoints/local_gov.json",
            crawler_name="local_gov",
            source="各省市政府网站",
        )
        if not resume:
            self.cpm.reset()

        # 读取断点
        cp = self.cpm.load()
        completed_urls = set(cp.get("completed_urls", [])) if resume else set()
        done_sites = set(cp.get("done_sites", [])) if resume else set()

        logger.info("📋 LocalGov 采集开始: {} 个站点, keyword='{}', resume={}",
                     len(sites), keyword, resume)

        for site in sites:
            # 断点续传：跳过已完成的站点
            if site.site_id in done_sites:
                logger.info("⏭️ LocalGov 站点已完成: {}", site.site_id)
                continue

            logger.info("=" * 50)
            logger.info("📂 站点: {} ({})", site.source_name, site.site_id)

            try:
                entries = self.client.fetch_list(site, keyword_filter=keyword)
                if not entries:
                    logger.info("📊 {} 无匹配条目", site.site_id)
                    # 无条目也标记完成，避免下次重试空站点
                    done_sites.add(site.site_id)
                    self.cpm.save({"done_sites": list(done_sites)})
                    continue

                logger.info("📊 {} 发现 {} 条", site.site_id, len(entries))

                for i, entry in enumerate(entries):
                    entry_url = entry["url"]

                    # 断点续传：跳过已处理的条目
                    if entry_url in completed_urls:
                        logger.debug("⏭️ LocalGov 跳过已完成: {}", entry["title"][:40])
                        continue

                    logger.info("[{}/{}] {}", i + 1, len(entries), entry["title"][:60])
                    try:
                        detail = self.client.fetch_detail(
                            entry["url"], site.detail_template
                        )
                        if detail:
                            self._save_regulation(detail, site, entry)
                        else:
                            self.total_failed += 1

                        # 标记该条目已完成
                        completed_urls.add(entry_url)
                        self.cpm.save({"completed_urls": list(completed_urls)})

                    except Exception as e:
                        logger.error("❌ LocalGov 详情失败: {} — {}", entry["url"], e)
                        self.total_failed += 1

                # 标记该站点已完成
                done_sites.add(site.site_id)
                self.cpm.save({"done_sites": list(done_sites)})

            except Exception as e:
                logger.error("❌ LocalGov 站点采集失败: {} — {}", site.site_id, e)

        logger.info("✅ LocalGov 采集完成: 入库 {} 条, 失败 {} 条",
                     self.total_saved, self.total_failed)

    def _save_regulation(self, detail: dict, site: SiteConfig, entry: dict):
        """保存法规元数据+下载链接到数据库"""
        source_url = detail.get("source_url", entry.get("url", ""))
        doc_id = LocalGovClient.hash_url(source_url)

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "source": f"local_{site.site_id}",
            "doc_id": doc_id,
            "title": detail.get("title", entry.get("title", "")),
            "doc_type": site.regulation_type,
            "publisher": detail.get("issuing_authority", ""),
            "publish_date": detail.get("publish_date", entry.get("date", "")),
            "effective_date": "",
            "status": "现行有效",
            "document_number": detail.get("document_number", ""),
            "hierarchy": site.regulation_type,
            "source_url": source_url,
            "download_url": source_url,
            "file_type": "HTML",
            "local_file_path": "",
            "created_at": now,
            "updated_at": now,
            "fetched_at": now,
        }

        if self._raw_upsert(row):
            self.total_saved += 1
            logger.info("✅ LocalGov 入库: {}", row["title"])
        else:
            self.total_failed += 1

    def _raw_upsert(self, row: dict) -> bool:
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
            logger.warning("⚠️ LocalGov upsert 失败: {}", e)
            return False
