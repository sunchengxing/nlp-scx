from collections import Counter
from datasets import load_dataset
from torch.utils.data import Dataset, DataLoader
import torch


class WikitextDataset(Dataset):
    def __init__(self, tokens: list[int], seq_len: int):
        self.seq_len = seq_len
        # 每个样本是 seq_len+1 个 token，input=[:seq_len], target=[1:]
        n = (len(tokens) - 1) // seq_len
        self.data = torch.tensor(tokens[: n * seq_len + 1], dtype=torch.long)

    def __len__(self):
        return (len(self.data) - 1) // self.seq_len

    def __getitem__(self, idx):
        start = idx * self.seq_len
        chunk = self.data[start : start + self.seq_len + 1]
        return chunk[:-1], chunk[1:]
