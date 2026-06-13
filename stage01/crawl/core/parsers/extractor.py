from parsel import Selector


def extract_field(sel: Selector, css: str, default: str = ""):
    val = sel.css(css).get()
    return val.strip() if val else default


def extract_list(sel: Selector, css: str):
    return [v.strip() for v in sel.css(css).getall() if v.strip()]
