import datetime
from peewee import Model, CharField, TextField, DateTimeField, IntegerField
from crawlee_data.utils.db import db


class Article(Model):
    url = CharField(max_length=2048, unique=True, index=True)
    title = CharField(max_length=512, default="")
    content = TextField(default="")
    author = CharField(max_length=128, default="")
    publish_time = DateTimeField(null=True, default=None)
    source = CharField(max_length=128, default="")
    status = IntegerField(default=0)  # 0=raw, 1=parsed, 2=cleaned
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        database = db
        table_name = "scx_articles"

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super().save(*args, **kwargs)
