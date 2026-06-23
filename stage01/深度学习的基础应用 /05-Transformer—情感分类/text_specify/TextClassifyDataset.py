from typing import List
import torch
from Tokenizer import Tokenizer
from torch.utils.data import Dataset


class TextClassifyDataset(Dataset):

    def __init__(self, texts: List[str], labels: List[str], tokenizer: Tokenizer):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer

    def __getitem__(self, index):
        out = self.tokenizer(self.texts[index], self.labels[index])
        return {
            "text": out.text,
            "tokens": out.tokens,
            "token_ids": torch.tensor(out.token_ids, dtype=torch.int64),
            "token_masks": torch.ones(len(out.token_ids), dtype=torch.float32),
            "label": out.label,
            "label_id": torch.tensor(out.label_id, dtype=torch.int64),
        }

    def __len__(self):
        return len(self.texts)
