import math

import torch
from torch import nn


class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=512):
        super().__init__()
        pe = torch.zeros(max_len, d_model)        # [max_len, d_model]
        position = torch.arange(0, max_len).unsqueeze(1).float()  # [max_len, 1]
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * -(math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)                      # [1, max_len, d_model]
        self.register_buffer('pe', pe)

    def forward(self, x):
        return x + self.pe[:, :x.size(1), :]
        # 词向量 + 对应位置的那一行


if __name__ == '__main__':
    pe = PositionalEncoding(d_model=128)
    x = torch.zeros(2, 10, 128)  # [bs=2, t=10, d_model=128]
    out = pe(x)
    print(out.shape)  # 期望 torch.Size([2, 10, 128])
