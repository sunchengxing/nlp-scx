import torch.nn as nn
import torch.nn.functional as F
import torch



class Attention(nn.Module):
    def __init__(self, hidden_size):
        super().__init__()
        self.hidden_size = hidden_size
        self.attention_layer = nn.Linear(hidden_size, 1)

    def forward_within_lstm(self, lstm_output):
        # lstm_output: [bs, t, hidden*2]
        # 1. 每个词打分: [bs, t, hidden*2] → [bs, t, 1]
        score = self.attention_layer(lstm_output)
        # 2. squeeze 掉最后维度: [bs, t, 1] → [bs, t]
        score = score.squeeze(-1)
        # 3. softmax 归一化: [bs, t] → [bs, t]  权重加起来=1
        weights = F.softmax(score, dim=1)  # [bs, t]
        # 4. 加权求和: weights[bs,t] × lstm_output[bs,t,hidden*2] → [bs, hidden*2]
        weights = weights.unsqueeze(1)  # [bs, 1, t]
        out = torch.bmm(weights, lstm_output)  # [bs, 1, hidden*2]
        out = out.squeeze(1)  # [bs, hidden*2]
        return out
