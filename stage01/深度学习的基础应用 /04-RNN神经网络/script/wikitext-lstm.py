"""
WikiText-2 LSTM 语言模型 - 单文件版（服务器/GPU训练用）
"""
from collections import Counter
from datasets import load_dataset
import re
import torch
import time

# ============ 设备自动检测 ============
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'使用设备: {device}')
if device.type == 'cuda':
    print(f'GPU型号: {torch.cuda.get_device_name(0)}')

# ============ 数据加载 ============
dataset = load_dataset("Salesforce/wikitext", "wikitext-2-raw-v1")
raw_text = "\n".join(dataset["train"]["text"])

# ============ 分词 ============
tokens = re.findall(r'\w+|[^\w\s]', raw_text)

# ============ 低频词过滤 ============
token_freq = Counter(tokens)
UNK_TOKEN = "<unk>"
filtered_tokens = []
for t in tokens:
    if token_freq[t] < 5:
        filtered_tokens.append(UNK_TOKEN)
    else:
        filtered_tokens.append(t)

# ============ 构建词表 ============
vocab = sorted(set(filtered_tokens))
word2id = {w: i for i, w in enumerate(vocab)}
id2word = {i: w for i, w in enumerate(vocab)}
print(f'词表大小: {len(vocab)}')

# ============ 转 ids + reshape ============
ids = [word2id[w] for w in filtered_tokens]
bs = 75
data = torch.tensor(ids)
n_tokens = (len(data) // bs) * bs
data = data[:n_tokens].reshape(bs, -1)
x = data[:, :-1].to(device)
y = data[:, 1:].to(device)
print(f'数据形状: x={x.shape}, y={y.shape}')

# ============ LSTM 模型定义 ============
embedding = torch.nn.Embedding(len(vocab), 128).to(device)
# 输入门
input_gate_x = torch.nn.Linear(128, 256).to(device)
input_gate_h = torch.nn.Linear(256, 256).to(device)
# 遗忘门
forget_gate_x = torch.nn.Linear(128, 256).to(device)
forget_gate_h = torch.nn.Linear(256, 256).to(device)
# 候选记忆
candidate_x = torch.nn.Linear(128, 256).to(device)
candidate_h = torch.nn.Linear(256, 256).to(device)
# 输出门
output_gate_x = torch.nn.Linear(128, 256).to(device)
output_gate_h = torch.nn.Linear(256, 256).to(device)
# 最终输出
output_linear = torch.nn.Linear(256, len(vocab)).to(device)

# 参数量
all_params = list(embedding.parameters()) + list(input_gate_x.parameters()) + list(input_gate_h.parameters()) + \
             list(forget_gate_x.parameters()) + list(forget_gate_h.parameters()) + \
             list(candidate_x.parameters()) + list(candidate_h.parameters()) + \
             list(output_gate_x.parameters()) + list(output_gate_h.parameters()) + \
             list(output_linear.parameters())
print(f'模型参数量: {sum(p.numel() for p in all_params):,}')

# ============ 训练配置 ============
criterion = torch.nn.CrossEntropyLoss()
epochs = 100
optimizer = torch.optim.Adam(all_params, lr=0.001)
seq_len = 20
num_windows = (x.shape[1] - seq_len) // seq_len

# ============ 训练 ============
total_start = time.time()
for epoch in range(epochs):
    epoch_start = time.time()
    h_t = torch.zeros(bs, 256, device=device)
    c_t = torch.zeros(bs, 256, device=device)
    epoch_loss = 0

    for window_id, start in enumerate(range(0, x.shape[1] - seq_len, seq_len)):
        x_window = x[:, start:start + seq_len]
        y_window = y[:, start:start + seq_len]

        loss = torch.tensor(0.0, device=device)
        optimizer.zero_grad()
        h_t = h_t.detach()
        c_t = c_t.detach()

        for t in range(seq_len):
            x_input = embedding(x_window[:, t])
            i = torch.sigmoid(input_gate_x(x_input) + input_gate_h(h_t))
            f = torch.sigmoid(forget_gate_x(x_input) + forget_gate_h(h_t))
            g = torch.tanh(candidate_x(x_input) + candidate_h(h_t))
            o = torch.sigmoid(output_gate_x(x_input) + output_gate_h(h_t))
            c_t = f * c_t + i * g
            h_t = o * torch.tanh(c_t)
            y_pred = output_linear(h_t)
            loss += criterion(y_pred, y_window[:, t])

        loss.backward()
        torch.nn.utils.clip_grad_norm_(all_params, 0.25)
        optimizer.step()
        epoch_loss += loss.item()

        if window_id % 200 == 0:
            print(f'epoch {epoch+1}/{epochs} | 窗口 {window_id}/{num_windows} | loss {loss.item():.2f}')

    epoch_time = time.time() - epoch_start
    avg_loss = epoch_loss / num_windows
    ppl = torch.exp(torch.tensor(avg_loss / seq_len)).item()
    print(f'=== epoch {epoch+1} 完成 | 平均loss {avg_loss:.2f} | perplexity {ppl:.1f} | 耗时 {epoch_time:.0f}s ===')

total_time = time.time() - total_start
print(f'\n训练总耗时: {total_time/3600:.1f} 小时')

# ============ 保存模型 ============
torch.save({
    'embedding': embedding.state_dict(),
    'input_gate_x': input_gate_x.state_dict(),
    'input_gate_h': input_gate_h.state_dict(),
    'forget_gate_x': forget_gate_x.state_dict(),
    'forget_gate_h': forget_gate_h.state_dict(),
    'candidate_x': candidate_x.state_dict(),
    'candidate_h': candidate_h.state_dict(),
    'output_gate_x': output_gate_x.state_dict(),
    'output_gate_h': output_gate_h.state_dict(),
    'output_linear': output_linear.state_dict(),
    'word2id': word2id,
    'id2word': id2word,
}, 'lstm_wiki-text_model.pt')
print('模型已保存到 lstm_wiki-text_model.pt')
