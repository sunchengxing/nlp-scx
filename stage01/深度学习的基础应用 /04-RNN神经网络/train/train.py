import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import torch
from config import WikiTextConfig
from model.model import RNNModel, LSTMModel


def train_with_rnn(model: RNNModel, x: torch.Tensor, y: torch.Tensor, config: WikiTextConfig):
    """
    训练RNN语言模型
    :param model: RNN模型
    :param x: 输入数据 shape: (bs, seq_len)
    :param y: 目标数据 shape: (bs, seq_len)
    :param config: 配置
    """
    device = torch.device(config.device)

    # 创建优化器，传入模型所有参数
    optimizer = torch.optim.SGD(model.parameters(), lr=config.learning_rate)
    criterion = torch.nn.CrossEntropyLoss()

    num_windows = (x.shape[1] - config.seq_length) // config.seq_length

    for epoch in range(config.num_epochs):
        # 每个epoch开始，隐藏状态清零
        h_t = torch.zeros(x.shape[0], config.hidden_dim, dtype=torch.float32, device=device)
        epoch_loss = 0

        for window_id, start in enumerate(range(0, x.shape[1] - config.seq_length, config.seq_length)):
            # 当前窗口的输入和目标
            x_window = x[:, start:start + config.seq_length]
            y_window = y[:, start:start + config.seq_length]

            optimizer.zero_grad()
            h_t = h_t.detach()

            # 前向传播
            outputs, h_t = model(x_window, h_t)

            # 计算损失：outputs是列表，每个元素对应一个时间步
            loss = 0
            for t, y_pred in enumerate(outputs):
                loss += criterion(y_pred, y_window[:, t])

            # 反向传播 + 更新参数
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()

            # 每200个窗口打印一次进度
            if window_id % 200 == 0:
                print(f'epoch {epoch + 1}/{config.num_epochs} | '
                      f'窗口 {window_id}/{num_windows} | '
                      f'当前窗口loss {loss.item():.2f}')

        avg_loss = epoch_loss / num_windows
        print(f'=== epoch {epoch + 1} 完成 | 平均loss {avg_loss:.2f} ===')

    # 训练结束，保存模型
    torch.save({
        'model_state_dict': model.state_dict(),
        'config': config,
    }, config.model_save_path)
    print(f'模型已保存到 {config.model_save_path}')


def train_with_lstm(model: LSTMModel, x: torch.Tensor, y: torch.Tensor, config: WikiTextConfig):
    """
    训练LSTM语言模型
    :param model: LSTM模型
    :param x: 输入数据 shape: (bs, seq_len)
    :param y: 目标数据 shape: (bs, seq_len)
    :param config: 配置
    """
    device = torch.device(config.device)

    # 创建优化器，传入模型所有参数
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate_adam)
    criterion = torch.nn.CrossEntropyLoss()

    num_windows = (x.shape[1] - config.seq_length) // config.seq_length

    for epoch in range(config.num_epochs):
        # 每个epoch开始，隐藏状态清零
        h_t = torch.zeros(x.shape[0], config.hidden_dim, dtype=torch.float32, device=device)
        c_t = torch.zeros(x.shape[0], config.hidden_dim, dtype=torch.float32, device=device)
        epoch_loss = 0

        for window_id, start in enumerate(range(0, x.shape[1] - config.seq_length, config.seq_length)):
            # 当前窗口的输入和目标
            x_window = x[:, start:start + config.seq_length]
            y_window = y[:, start:start + config.seq_length]

            optimizer.zero_grad()
            h_t = h_t.detach()
            c_t = c_t.detach()
            # 前向传播
            outputs, h_t, c_t = model(x_window, h_t, c_t)

            # 计算损失：outputs是列表，每个元素对应一个时间步
            loss = torch.tensor(0.0)
            for t, y_pred in enumerate(outputs):
                loss += criterion(y_pred, y_window[:, t])

            # 反向传播 + 更新参数
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()

            # 每200个窗口打印一次进度
            if window_id % 200 == 0:
                print(f'epoch {epoch + 1}/{config.num_epochs} | '
                      f'窗口 {window_id}/{num_windows} | '
                      f'当前窗口loss {loss.item():.2f}')

        avg_loss = epoch_loss / num_windows
        print(f'=== epoch {epoch + 1} 完成 | 平均loss {avg_loss:.2f} ===')

    # 训练结束，保存模型
    torch.save({
        'model_state_dict': model.state_dict(),
        'config': config,
    }, config.model_save_path)
    print(f'模型已保存到 {config.model_save_path}')
