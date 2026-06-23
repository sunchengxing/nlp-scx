from dataclasses import dataclass
from typing import List
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import jieba as jb


class SplitTokensTools:

    @staticmethod
    def split_text_to_tokens_with_jieba(text: str) -> List[str]:
        # 先判空
        if text is None | len(text) == 0:
            return []
        # 返回分词后的结果
        return jb.lcut(text)

    """
    将text文本转tokens
    将字符串直接拆成[]
    """
    @staticmethod
    def  split_text_to_tokens_with_char(char_text: str) -> List[str]:
        if char_text is None | len(char_text) == 0:
            return []
        return list(char_text)

    def split_text_to_tokens(self, text:str) -> List[str]:
        tokens = self.split_text_to_tokens_with_jieba(text)
        return [t.lower() for t in tokens]