import numpy as np
from torch import nn
from torch.nn import functional as F

class Attention(nn.Module):
    def __init__(self, d_k):
        super().__init__()
        self.d_k = d_k  # K 的维度，用来缩放

    def forward(self, Q, K, V):
        # Q: [bs, t_q, d_k]  解码器的查询
        # K: [bs, t_k, d_k]  编码器的键
        # V: [bs, t_k, d_v]  编码器的值
        # 1. Q·K^T 计算相似度 [bs, t_q, t_k]
        similarity = Q @ K.transpose(-2, -1)
        # 2. 除以 √d_k 缩放
        similarity = similarity / (self.d_k ** 0.5)
        # 3. softmax
        atte_softmax = F.softmax(similarity, dim=-1)
        # 4. 加权求和 V Shape： [bs, t_k, d_v]
        attention_out = atte_softmax @ V
        # attention_out: [bs, t, hidden*2]
        # 还需要压缩 t 维度才能送进 Linear
        # 用 mean 或取第一个时刻
        attention_out = attention_out.mean(dim=1)  # [bs, hidden*2]
        return attention_out