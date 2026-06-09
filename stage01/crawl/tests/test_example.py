import pytest
from crawlee_data.config import Settings


def test_settings_defaults():
    s = Settings()
    assert s.mysql_host == "localhost"
    assert s.db_pool_min == 3
    assert s.crawl_concurrency == 10


def test_article_model():
    from crawlee_data.models.article import Article
    assert Article._meta.table_name == "scx_articles"


def test_extract_field():
    from parsel import Selector
    from crawlee_data.parsers.extractor import extract_field

    sel = Selector(text="<html><h1>Hello</h1></html>")
    assert extract_field(sel, "h1::text") == "Hello"
    assert extract_field(sel, "h2::text") == ""


def test_extract_list():
    from parsel import Selector
    from crawlee_data.parsers.extractor import extract_list

    sel = Selector(text="<ul><li>A</li><li>B</li></ul>")
    assert extract_list(sel, "li::text") == ["A", "B"]
