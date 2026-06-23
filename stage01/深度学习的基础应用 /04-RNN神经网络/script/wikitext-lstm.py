from collections import Counter
from datasets import load_dataset
import re
import torch
import time

# 使用colab的TU4 GPU
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'使用设备: {device}')
if device.type == 'cuda':
    print(f'GPU型号: {torch.cuda.get_device_name(0)}')
# 第一步 先做数据加载，将HuggingFace数据集下载之后导入
# 数据集路径 数据集名称
dataset = load_dataset("Salesforce/wikitext", "wikitext-2-raw-v1")
# 将训练文本载入 数据集对象内部的list数据转为了一段超长大文本
raw_text = "\n".join(dataset["train"]["text"])
print(f'数据长度: {len(raw_text)}')
# 先做好分词 做分词之前先做正则格式化
tokens = re.findall(r'\w+|[^\w\s]', raw_text)
# 词频统计 由于第一次训练的时候7万多词表大小会导致参数量级过大导致训练效率低下，所以后续所有训练都考虑做低频词过滤
token_freq = Counter(tokens)
UNK_TOKEN = "<unk>"
filtered_tokens = []
for t in tokens:
    if token_freq[t] < 5:
        filtered_tokens.append(UNK_TOKEN)
    else:
        filtered_tokens.append(t)

# 构建词表
vocab = sorted(set(filtered_tokens))
word2id = {w: i for i, w in enumerate(vocab)}
id2word = {i: w for i, w in enumerate(vocab)}
print(f'词表大小: {len(vocab)}')

# 转 ids + reshape 遍历filtered_tokens数组数据将拿到的每一个元素（就是做完词频控制之后的词）再通过map转换成id
ids = [word2id[w] for w in filtered_tokens]
# bs个样本
bs = 75
# 全量词表id 转为tensor对象
data = torch.tensor(ids)
# 计算全量ids按照75个样本来算，每一个样本最多有多少个token 拿到取整数倍的token
n_tokens = (len(data) // bs) * bs
# 将这个整数倍的全量token-ids的shape做reshape变换 得到一个bs个样本，每一个样本n个token-ids
# shape: (75, seq_len)
data = data[:n_tokens].reshape(bs, -1)
# 使用cpu训练 输入/标签错位构造
x = data[:, :-1].to(device)
y = data[:, 1:].to(device)
print(f'数据形状: x={x.shape}, y={y.shape}')
#
# LSTM 模型定义
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

# 训练配置
criterion = torch.nn.CrossEntropyLoss()
epochs = 100
optimizer = torch.optim.Adam(all_params, lr=0.001)
seq_len = 20
num_windows = (x.shape[1] - seq_len) // seq_len

# 训练
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
