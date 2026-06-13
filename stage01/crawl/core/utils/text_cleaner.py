"""文本清洗工具

从 fire_rag/crawler_base.py 的 TextCleaner 提取，
供 flk/mem/local_gov 等爬虫复用。

核心能力：
- HTML → 纯文本（去除脚本/样式/导航/广告）
- 文本规范化（换行/空白/全角半角）
- 日期提取（YYYY-MM-DD / YYYY年MM月DD日）
- 章节信息提取（第X章 / 第X条）
- 内容哈希（SHA256 去重）
- 水印/页眉页脚去除
"""
import hashlib
import re
from typing import Optional

from bs4 import BeautifulSoup


class TextCleaner:
    """文本清洗工具函数集"""

    @staticmethod
    def clean_html(html_content: str, preserve_links: bool = False) -> str:
        """从 HTML 中提取纯文本，去除脚本、样式、导航等非正文元素

        Args:
            html_content: 原始 HTML 字符串
            preserve_links: 是否保留链接 URL（在括号中追加）

        Returns:
            清洗后的纯文本
        """
        soup = BeautifulSoup(html_content, "lxml")

        # 移除不需要的元素
        for tag_name in ["script", "style", "nav", "footer", "header", "noscript"]:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # 移除常见非正文 class/id
        skip_patterns = [
            "nav", "menu", "sidebar", "footer", "header", "banner",
            "breadcrumb", "pagination", "comment", "advertisement",
            "copyright", "toolbar", "search",
        ]
        for pattern in skip_patterns:
            for tag in soup.find_all(class_=re.compile(pattern, re.I)):
                tag.decompose()
            for tag in soup.find_all(id=re.compile(pattern, re.I)):
                tag.decompose()

        if preserve_links:
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                a_tag.append(f" [{href}]")

        text = soup.get_text(separator="\n")
        return TextCleaner.normalize_text(text)

    @staticmethod
    def normalize_text(text: str) -> str:
        """文本规范化：统一换行/合并空白行/去除首尾空白"""
        # 将连续3个以上换行压缩为2个换行（保留段落间距）
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 去除每行首尾空格
        lines = [line.strip() for line in text.split("\n")]
        # 去除前导空行
        while lines and not lines[0]:
            lines.pop(0)
        # 去除尾部空行
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)

    @staticmethod
    def extract_date(text: str) -> Optional[str]:
        """从文本中提取日期（YYYY-MM-DD 或 YYYY年MM月DD日）

        Returns:
            'YYYY-MM-DD' 格式字符串，未找到返回 None
        """
        patterns = [
            r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?",
            r"(\d{4})(\d{2})(\d{2})",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                year, month, day = m.group(1), m.group(2), m.group(3)
                return f"{year}-{int(month):02d}-{int(day):02d}"
        return None

    @staticmethod
    def extract_chapter_info(text: str) -> Optional[dict]:
        """从一行文本中提取章节信息

        支持格式：
        - "第一章 总则"
        - "第1章 总则"
        - "1 范围"（GB 标准）

        Returns:
            {"number": "一", "title": "总则"} 或 None
        """
        patterns = [
            r"第([一二三四五六七八九十百零\d]+)章\s*(.*)",
            r"^(\d+)\s+(.*)",
        ]
        for pattern in patterns:
            m = re.match(pattern, text.strip())
            if m:
                return {"number": m.group(1), "title": m.group(2).strip()}
        return None

    @staticmethod
    def extract_article_info(text: str) -> Optional[dict]:
        """从一行文本中提取条款信息

        支持格式：
        - "第一条 为了..."
        - "第1条 为了..."
        - "1.1 范围"

        Returns:
            {"number": "一", "content": "为了..."} 或 None
        """
        patterns = [
            r"第([一二三四五六七八九十百零\d]+)条\s*(.*)",
            r"^(\d+\.\d+\.\d+)\s+(.*)",
            r"^(\d+\.\d+)\s+(.*)",
        ]
        for pattern in patterns:
            m = re.match(pattern, text.strip())
            if m:
                return {"number": m.group(1), "content": m.group(2).strip()}
        return None

    @staticmethod
    def compute_content_hash(text: str) -> str:
        """计算内容的 SHA256 哈希（用于去重和变更检测）"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def remove_watermark_text(text: str) -> str:
        """去除常见水印文字和页眉页脚干扰"""
        watermarks = [
            r"国家标准全文公开系统",
            r"GB\s*\d+[\.-]\d+",
            r"第\s*\d+\s*页.*共\s*\d+\s*页",
            r"ICS\s*\d+\.\d+",
            r"版权所有.*侵权必究",
            r"—\s*\d+\s*—",
        ]
        for pat in watermarks:
            text = re.sub(pat, "", text, flags=re.IGNORECASE)
        return TextCleaner.normalize_text(text)

    @staticmethod
    def clean_law_text(text: str) -> str:
        """针对法律法规文本的专项清洗：保留条款结构，去除多余空白"""
        return TextCleaner.normalize_text(text)

    @staticmethod
    def clean_docx_text(text: str) -> str:
        """清洗 DOCX 提取的文本"""
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        return text.strip()

    @staticmethod
    def clean_html_text(html: str) -> str:
        """从 HTML 中提取纯文本，保留段落结构（用于正文区域已确定的场景）"""
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "meta", "link"]):
            tag.decompose()

        # 将块级元素替换为换行
        for tag in soup.find_all(["p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"]):
            tag.insert_before("\n")

        text = soup.get_text()
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(line for line in lines if line)