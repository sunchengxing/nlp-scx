"""
WikiText-2 RNN 语言模型 - Colab GPU 版本
使用方法：
1. 打开 Google Colab → 运行时 → 更改运行时类型 → T4 GPU
2. 将此文件上传或粘贴到 Colab 中运行
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
    print(f'GPU显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB')

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
print(f'数据形状: {data.shape}')

# ============ 模型定义 ============
embeddings = torch.nn.Embedding(len(vocab), 128).to(device)
x_linear = torch.nn.Linear(128, 256).to(device)
h_linear = torch.nn.Linear(256, 256).to(device)
output_linear = torch.nn.Linear(256, len(vocab)).to(device)

# ============ 构建x与y ============
x = data[:, :-1].to(device)
y = data[:, 1:].to(device)

# ============ 训练配置 ============
criterion = torch.nn.CrossEntropyLoss()
epochs = 100
Parameters = [
    {'params': embeddings.parameters()},
    {'params': x_linear.parameters()},
    {'params': h_linear.parameters()},
    {'params': output_linear.parameters()}
]
optimizer = torch.optim.Adam(Parameters, lr=0.001)
num_windows = x.shape[1] // 20

# ============ 训练 ============
total_start = time.time()
for epoch in range(epochs):
    epoch_start = time.time()
    h_t = torch.zeros(bs, 256, device=device)
    epoch_loss = 0

    for window_id, i in enumerate(range(0, x.shape[1] - 20, 20)):
        loss_all = torch.tensor(0.0, device=device)
        optimizer.zero_grad()
        h_t = h_t.detach()

        for j in range(i, i + 20):
            x_input = embeddings(x[:, j])
            h_t = torch.tanh(x_linear(x_input) + h_linear(h_t))
            y_pred = output_linear(h_t)
            loss_all += criterion(y_pred, y[:, j])

        loss_all.backward()
        torch.nn.utils.clip_grad_norm_(embeddings.parameters(), 0.25)
        optimizer.step()
        epoch_loss += loss_all.item()

        if window_id % 200 == 0:
            print(f'epoch {epoch+1}/{epochs} | 窗口 {window_id}/{num_windows} | '
                  f'loss {loss_all.item():.2f}')

    epoch_time = time.time() - epoch_start
    avg_loss = epoch_loss / num_windows
    ppl = torch.exp(torch.tensor(avg_loss / 20)).item()
    print(f'=== epoch {epoch+1} 完成 | 平均loss {avg_loss:.2f} | '
          f'perplexity {ppl:.1f} | 耗时 {epoch_time:.0f}s ===')

total_time = time.time() - total_start
print(f'\n训练总耗时: {total_time/3600:.1f} 小时')

# ============ 保存模型 ============
torch.save({
    'embeddings': embeddings.state_dict(),
    'x_linear': x_linear.state_dict(),
    'h_linear': h_linear.state_dict(),
    'output_linear': output_linear.state_dict(),
    'word2id': word2id,
    'id2word': id2word,
    'vocab_size': len(vocab),
}, 'rnn_wiki-text_model_gpu.pt')
print('模型已保存')
