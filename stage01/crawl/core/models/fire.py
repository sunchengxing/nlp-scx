"""消防法规数据模型

只存元数据 + 下载链接，不存正文内容。
正文/PDF 走文件系统，需要时从数据库取 download_url 再下载。

数据来源：
- flk.npc.gov.cn（国家法律法规数据库）
- mem.gov.cn（应急管理部）
- 各省市政府网站（地方性法规）
- openstd.samr.gov.cn（国标在线）
"""
from peewee import CharField, TextField
from core.models.base import ScxBaseModel


class FireLawRegulation(ScxBaseModel):
    """法律法规索引表（flk/mem/地方性法规通用）

    只存元数据和下载链接，content 不入库。
    通过 source 字段区分数据来源，通过 download_url 获取正文文件。
    """

    # 数据来源标识：flk / mem / local_beijing / local_shanghai / ...
    source = CharField(max_length=32, index=True, verbose_name="数据来源")

    # 源站唯一标识（flk 的 id / mem 的 URL hash / 地方的 doc_id）
    doc_id = CharField(max_length=128, verbose_name="源站ID")

    # 法规标题
    title = CharField(max_length=512, default="", verbose_name="法规标题")

    # 法规类型：法律/行政法规/地方性法规/规范性文件/部门规章/司法解释
    doc_type = CharField(max_length=32, default="", verbose_name="法规类型")

    # 制定机关
    publisher = CharField(max_length=128, default="", verbose_name="制定机关")

    # 发布日期
    publish_date = CharField(max_length=10, default="", verbose_name="发布日期")

    # 施行日期
    effective_date = CharField(max_length=10, default="", verbose_name="施行日期")

    # 效力状态：现行有效/已废止/尚未生效
    status = CharField(max_length=16, default="现行有效", verbose_name="效力状态")

    # 文号（如：中华人民共和国主席令第二十九号）
    document_number = CharField(max_length=128, default="", verbose_name="文号")

    # 法律层级：宪法/法律/行政法规/地方性法规/部门规章/规范性文件
    hierarchy = CharField(max_length=32, default="", verbose_name="法律层级")

    # 原文页面 URL
    source_url = TextField(default="", verbose_name="源站URL")

    # 文件下载链接（DOCX/HTML/PDF 的下载地址）
    download_url = TextField(default="", verbose_name="下载链接")

    # 下载文件类型：WORD/HTML/PDF
    file_type = CharField(max_length=16, default="", verbose_name="文件类型")

    # 本地文件路径（下载后回填）
    local_file_path = TextField(default="", verbose_name="本地文件路径")

    class Meta:
        table_name = "scx_fire_law_regulation"
        indexes = (
            # 联合唯一：同一来源同一 doc_id 不重复
            (("source", "doc_id"), True),
            # 按来源+发布日期查询
            (("source", "publish_date"), False),
        )

    def __str__(self):
        return f"[{self.source}] {self.title}"


class FireIndustryDoc(ScxBaseModel):
    """行业标准/国标文档索引表

    只存元数据和下载链接，content 不入库。
    PDF 下载后回填 local_pdf_path。
    """

    # 数据来源：mem / gb / local
    source = CharField(max_length=32, index=True, verbose_name="数据来源")

    # 唯一标识
    doc_id = CharField(max_length=128, verbose_name="文档ID")

    # 标题
    title = CharField(max_length=512, default="", verbose_name="标题")

    # 标准编号（如 GB 50016-2014、XF/T 999-2012）
    standard_no = CharField(max_length=64, default="", verbose_name="标准编号")

    # 文档类型：国标/行标/团标/地标/通知附件
    doc_type = CharField(max_length=32, default="", verbose_name="文档类型")

    # 发布日期
    publish_date = CharField(max_length=10, default="", verbose_name="发布日期")

    # 效力状态
    status = CharField(max_length=16, default="现行有效", verbose_name="效力状态")

    # 原文 URL
    source_url = TextField(default="", verbose_name="源站URL")

    # PDF 下载链接
    download_url = TextField(default="", verbose_name="下载链接")

    # 本地 PDF 路径（下载后回填）
    local_pdf_path = TextField(default="", verbose_name="本地PDF路径")

    class Meta:
        table_name = "scx_fire_industry_doc"
        indexes = (
            (("source", "doc_id"), True),
            (("standard_no",), False),
        )

    def __str__(self):
        return f"[{self.source}] {self.standard_no or self.title}"