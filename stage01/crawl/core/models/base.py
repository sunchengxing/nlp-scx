import datetime
from peewee import Model, DateTimeField, CharField, AutoField
from core.utils.db import db


class ScxBaseModel(Model):
    """所有 Model 的公共基类"""

    class Meta:
        database = db

    id = AutoField()                                            # 自增主键
    created_at = DateTimeField(default=datetime.datetime.now)   # 创建时间
    updated_at = DateTimeField(default=datetime.datetime.now)   # 更新时间
    source = CharField(max_length=32, default="eastmoney")      # 数据来源
    fetched_at = DateTimeField(default=datetime.datetime.now)    # 采集时间

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super().save(*args, **kwargs)




