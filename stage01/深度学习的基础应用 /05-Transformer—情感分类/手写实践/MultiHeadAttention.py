import torch
from torch import nn


class MultiHeadAttention(nn.Module):
    def __init__(self, d_model, num_heads):
        super().__init__()
        self.num_heads = num_heads
        self.d_k = d_model // num_heads  # 每个头的维度

        # 每个头共用一个大 Linear，通过 reshape 拆分
        # 三个完全不同的参数表示
        self.W_Q = nn.Linear(d_model, d_model)
        # 不同的参数表示
        self.W_K = nn.Linear(d_model, d_model)
        # 不同的参数表示
        self.W_V = nn.Linear(d_model, d_model)
        # 不同的参数表示
        self.W_O = nn.Linear(d_model, d_model)  # 输出投影

    def forward(self, Q, K, V):
        # 1. 线性变换
        bs = Q.size(0)
        # Q.shape[0]  # 取形状元组的第0个元素
        # 先做线性转换得到三个不同的参数表示
        # 那么问题来了原来的qkv参数表示是一样的吗，我是指qkv的d_model？
        Q = self.W_Q(Q)
        K = self.W_K(K)
        V = self.W_V(V)
        # 2. reshape 拆分多头 self.num_heads个头 然后每一个头分配到 self.d_k数量的维度
        Q = Q.reshape(bs, -1, self.num_heads, self.d_k).transpose(1, 2)
        K = K.reshape(bs, -1, self.num_heads, self.d_k).transpose(1, 2)
        V = V.reshape(bs, -1, self.num_heads, self.d_k).transpose(1, 2)
        # 3. 计算score
        scores = torch.matmul(Q, K.transpose(-2, -1)) / (self.d_k ** 0.5)
        # 计算权重
        weights = torch.softmax(scores, dim=-1)
        # [bs, heads, t, d_k]
        out = torch.matmul(weights, V)

        # 4. 合并多头
        # 现在 out: [bs, heads, t, d_k]
        # 需要变回 [bs, t, d_model]

        out = out.transpose(1, 2)  # [bs, t, heads, d_k]
        out = out.reshape(bs, -1, self.num_heads * self.d_k)  # [bs, t, d_model]
        return self.W_O(out)


if __name__ == '__main__':
    mha = MultiHeadAttention(d_model=128, num_heads=4)
    x = torch.randn(2, 10, 128)  # [bs=2, t=10, d_model=128]
    out = mha(x, x, x)           # Self-Attention
    print(out.shape)             # 应该输出 torch.Size([2, 10, 128])