class CharUtils:

    @staticmethod
    def is_chinese(s) -> bool:
        return all('\u4e00' <= c <= '\u9fff' for c in s)