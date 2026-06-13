"""股吧帖子与评论数据模型"""
import datetime
from peewee import (
    CharField, TextField, DateTimeField, IntegerField, DecimalField,
    SmallIntegerField, ForeignKeyField, TextField,
)
from core.models.base import ScxBaseModel
from core.utils.db import db


class GubaPost(ScxBaseModel):
    """股吧帖子 — 建表 scx_guba_post"""

    class Meta:
        table_name = "scx_guba_post"
        indexes = (
            (("stock_code", "post_id"), True),  # 股票+帖子ID 联合唯一
        )

    stock_code = CharField(max_length=6, index=True)       # "600519"
    post_id = CharField(max_length=20, index=True)          # 帖子ID "1724770672"
    title = CharField(max_length=512, default="")           # 帖子标题
    content = TextField(default="")                         # 正文纯文本
    content_html = TextField(default="")                    # 正文HTML（保留图片等）
    author = CharField(max_length=128, default="")          # 作者名
    post_time = DateTimeField(null=True, default=None)      # 发帖时间
    read_count = IntegerField(default=0)                    # 阅读数
    comment_count = IntegerField(default=0)                 # 评论数
    url = CharField(max_length=512, default="")             # 详情页URL
    # AI标注字段（后续填入）
    label = SmallIntegerField(null=True, default=None)      # 0=看空 1=看多 2=中性
    confidence = DecimalField(max_digits=4, decimal_places=3, null=True, default=None)  # AI置信度 0~1
    label_reason = TextField(default="")                    # AI标注理由
    label_reviewed = SmallIntegerField(default=0)           # 0=未审核 1=已审核


class GubaComment(ScxBaseModel):
    """股吧评论 — 建表 scx_guba_comment"""

    class Meta:
        table_name = "scx_guba_comment"
        indexes = (
            (("stock_code", "reply_id"), True),  # 股票+评论ID 联合唯一
        )

    stock_code = CharField(max_length=6, index=True)       # "600519"
    post_id = CharField(max_length=20, index=True)          # 关联帖子ID
    reply_id = CharField(max_length=20, index=True)         # 评论ID
    parent_reply_id = CharField(max_length=20, default="")  # 父评论ID（二级评论时有值）
    content = TextField(default="")                         # 评论内容
    author = CharField(max_length=128, default="")          # 评论者
    comment_time = DateTimeField(null=True, default=None)   # 评论时间
    like_count = IntegerField(default=0)                    # 点赞数
    region = CharField(max_length=32, default="")           # 来自地域
    is_sub = SmallIntegerField(default=0)                   # 0=一级评论 1=二级评论
