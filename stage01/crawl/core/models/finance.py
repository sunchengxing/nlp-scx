"""巨潮资讯网 cninfo 公告数据模型

存储上市公司财报公告信息（年报/半年报/季报等），不含 PDF 正文（PDF 按需下载到本地文件系统）。
"""
import datetime
from peewee import CharField, TextField, DateTimeField, IntegerField, BigIntegerField
from core.models.base import ScxBaseModel


class CninfoAnnouncement(ScxBaseModel):
    """cninfo 财报公告

    对标 EastmoneyClient 拉取的结构化数据：
      - 列表页/详情页 → 此表存公告元信息
      - PDF 正文 → 按需下载到本地文件系统，不存 DB
    """

    # 股票代码（如 "000001"）
    sec_code = CharField(max_length=6, index=True, verbose_name="股票代码")

    # 股票名称（如 "平安银行"）
    sec_name = CharField(max_length=64, default="", verbose_name="股票名称")

    # cninfo 公告 ID（唯一标识）
    announcement_id = CharField(max_length=64, unique=True, index=True, verbose_name="公告ID")

    # 公告标题
    announcement_title = CharField(max_length=512, default="", verbose_name="公告标题")

    # 公告时间（毫秒时间戳）
    announcement_time = BigIntegerField(default=0, verbose_name="公告时间(ms)")

    # 公告时间（格式化后的日期字符串，方便查询）
    announcement_date = CharField(max_length=10, default="", verbose_name="公告日期")

    # PDF 相对路径（如 "finalpage/2026-03-21/1225022887.PDF"）
    adjunct_url = TextField(default="", verbose_name="PDF相对路径")

    # 公告类别（年报/半年报/一季报/三季报等）
    category = CharField(max_length=32, default="年报", verbose_name="公告类别")

    # 本地 PDF 路径（下载后填充）
    local_pdf_path = TextField(default="", verbose_name="本地PDF路径")

    class Meta:
        table_name = "scx_cninfo_announcement"
        indexes = (
            # 按股票代码+公告日期联合索引（常用查询）
            (("sec_code", "announcement_date"), False),
        )

    def __str__(self):
        return f"[{self.sec_code}] {self.announcement_title}"
