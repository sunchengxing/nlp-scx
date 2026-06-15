import torch


class RNNModel(torch.nn.Module):

    """
    RNN模型
    """
    def __init__(self, vocab_size, embedding_dim, hidden_dim):
        super().__init__()
        self.embedding = torch.nn.Embedding(vocab_size, embedding_dim)
        self.x_linear =torch.nn.Linear(embedding_dim, hidden_dim)
        self.h_linear = torch.nn.Linear(hidden_dim, hidden_dim)
        self.output_linear = torch.nn.Linear(hidden_dim, vocab_size)

    def forward(self, x, h_t):
        # x shape: (bs, seq_len)
        # h_t shape: (bs, hidden_dim)

        outputs = []
        for t in range(x.shape[1]):
            x_input = self.embedding(x[:, t])
            h_t = torch.tanh(self.x_linear(x_input) + self.h_linear(h_t))
            y_pred = self.output_linear(h_t)
            outputs.append(y_pred)

        return outputs, h_t

    # def forward(self, x, y, bs):
    #     # 损失
    #     criterion = torch.nn.CrossEntropyLoss()
    #     # 训练多少轮次
    #     epochs = 2
    #     # 创建优化器
    #     Parameters = [
    #         {'params': self.embeddings.parameters()},
    #         {'params': self.x_linear.parameters()},
    #         {'params': self.h_linear.parameters()},
    #         {'params': self.output_linear.parameters()}
    #     ]
    #     optimizer = torch.optim.SGD(Parameters, lr=0.01)
    #     num_windows = x.shape[1] // 20
    #     for epoch in range(epochs):
    #         h_t = torch.zeros(bs, 256, dtype=torch.float32, device=torch.device('cpu'))
    #         epoch_loss = 0
    #         for window_id, i in enumerate(range(0, x.shape[1] - 20, 20)):
    #             loss_all = torch.tensor(0.0, dtype=torch.float32, device=torch.device('cpu'))
    #             optimizer.zero_grad()
    #             h_t = h_t.detach()
    #             for j in range(i, i + 20):
    #                 # 所有行的第i列
    #                 x_input = self.embeddings(x[:, j])  # shape：75,128
    #                 h_t = torch.tanh(self.x_linear(x_input) + self.h_linear(h_t))
    #                 y_pred = self.output_linear(h_t)
    #                 # 计算损失
    #                 loss_all += criterion(y_pred, y[:, j])
    #             loss_all.backward()
    #             optimizer.step()
    #             epoch_loss += loss_all.item()
    #             # 每200个窗口打印一次进度
    #             if window_id % 200 == 0:
    #                 print(
    #                     f'epoch {epoch + 1}/{epochs} | 窗口 {window_id}/{num_windows} | 当前窗口loss {loss_all.item():.2f}')
    #         print(f'=== epoch {epoch + 1} 完成 | 平均loss {epoch_loss / num_windows:.2f} ===')
