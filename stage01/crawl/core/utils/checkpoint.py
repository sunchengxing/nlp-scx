import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from loguru import logger


class CheckpointManager:
    """断点续传管理器

    从 fire_rag/crawler_base.py 的 CheckpointManager 提取，
    供所有爬虫复用，避免中断后重复采集。

    用法：
        cpm = CheckpointManager("checkpoints/flk.json", crawler_name="flk", source="flk.npc.gov.cn")
        cpm.save({"last_page": 5, "completed_ids": ["a", "b"]})
        data = cpm.load()
        cpm.mark_complete("item_001")
        pending = cpm.get_pending_ids(all_ids)
    """
    """
    基于 JSON 文件的断点续传管理器

    存储结构：
        {
            "crawler": "flk_crawler",
            "source": "flk.npc.gov.cn",
            "created_at": "2026-06-12T10:00:00Z",
            "updated_at": "2026-06-12T11:30:00Z",
            "total_items": 150,
            "completed_items": 87,
            "completed_ids": ["id1", "id2", ...],
            "last_page": 8,
            "stats": {"success": 85, "failed": 2, "skipped": 0}
        }
    """

    def __init__(self, checkpoint_path: str, crawler_name: str = "", source: str = ""):
        self.path = Path(checkpoint_path)
        self.crawler_name = crawler_name
        self.source = source

    def load(self) -> Dict[str, Any]:
        """加载检查点数据。不存在则返回空字典。"""
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("CheckpointManager: 加载失败 {}", self.path)
                return {}
        return {}

    def save(self, progress: Dict[str, Any]):
        """保存检查点数据（增量合并）"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.load()

        existing.update(progress)
        existing.setdefault("crawler", self.crawler_name)
        existing.setdefault("source", self.source)
        existing.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()

        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        logger.debug("CheckpointManager: 已保存 {}", self.path.name)

    def mark_complete(self, item_id: str):
        """标记单个条目已完成"""
        data = self.load()
        completed: List[str] = data.get("completed_ids", [])
        if item_id not in completed:
            completed.append(item_id)
        stats = data.get("stats", {})
        stats["success"] = stats.get("success", 0) + 1
        self.save({
            "completed_ids": completed,
            "completed_items": len(completed),
            "stats": stats,
        })

    def mark_failed(self, item_id: str):
        """标记单个条目失败"""
        data = self.load()
        stats = data.get("stats", {})
        stats["failed"] = stats.get("failed", 0) + 1
        failed_ids: List[Dict[str, str]] = data.get("failed_items", [])
        failed_ids.append({"id": item_id, "time": datetime.now(timezone.utc).isoformat()})
        self.save({"stats": stats, "failed_items": failed_ids})

    def get_pending_ids(self, all_ids: List[str]) -> List[str]:
        """返回尚未完成的 ID 列表"""
        data = self.load()
        completed = set(data.get("completed_ids", []))
        return [i for i in all_ids if i not in completed]

    def is_completed(self, item_id: str) -> bool:
        """判断某个条目是否已完成"""
        data = self.load()
        return item_id in data.get("completed_ids", [])

    def reset(self):
        """重置检查点（删除文件）"""
        if self.path.exists():
            self.path.unlink()
            logger.info("CheckpointManager: 已重置 {}", self.path.name)
