from datasets import load_dataset
import re
import torch
from torch.nn.modules import loss

# 数据加载 这里需要考虑文本分词场景的必要性，这里是英文语料 不适合jieba分词
dataset = load_dataset("Salesforce/wikitext", "wikitext-2-raw-v1")
# 所以直接考虑正则分词
# print(dataset)
# print(len(dataset["train"]))
# token分词
# print(dataset["train"][0])        # 看第一条
# print(dataset["train"][:3])       # 看前几条

# 把所有文本拼起来，过滤掉空行
raw_text = "\n".join(dataset["train"]["text"])

# 打印前500个字符
# print(raw_text[:500])

# 测试分词
# input_str = input("请输入：英文字符串")
# print(re.findall(r'\w+|[^\w\s]', input_str))
# 基于数据集做分词处理
tokens = re.findall(r'\w+|[^\w\s]', raw_text)
# 分词没有"绝对正确"，只有"对任务是否合理"：


#拿到分词结果之后构建词表 先去重复
vocab = set(tokens)
# 排序
vocab = sorted(vocab)
print(f'词表大小为{len(vocab)}')

# word2vector
word2id = {w : i for i, w in enumerate(vocab)}
id2word = {i : w for i, w in enumerate(vocab)}
print(f'转为字典之后的大小为{len(word2id)}')
# 前25个token
# print(vocab[:25])

# 拿到每一个token在字典中的ids
ids = [word2id[w] for w in tokens]
print(ids[:25])
print([id2word[i] for i in ids[:20]])

# torch.reshape(torch.tensor(ids), (1013, 75))
bs = 75
# 完整输入
data = torch.tensor(ids)
# 每一个token
n_tokens = (len(data) // bs) * bs
data = data[:n_tokens].reshape(bs, -1)
print(data.shape)
# 直接使用torch的embedding做id转俄embedding
embeddings = torch.nn.Embedding(len(vocab), 128)
x_linear = torch.nn.Linear(128, 256, dtype=torch.float32, device=torch.device('cpu'))
h_linear = torch.nn.Linear(256, 256, dtype=torch.float32, device=torch.device('cpu'))
output_linear = torch.nn.Linear(256, len(vocab), dtype=torch.float32, device=torch.device('cpu'))
# 构建x 与 y 错位切片
x = data[:, :-1]
y = data[:, 1:]
# 损失
criterion = torch.nn.CrossEntropyLoss()
# 训练多少轮次
epochs = 2
# 创建优化器
Parameters = [
    {'params': embeddings.parameters()},
    {'params': x_linear.parameters()},
    {'params': h_linear.parameters()},
    {'params': output_linear.parameters()}
]
optimizer = torch.optim.SGD(Parameters, lr=0.01)
num_windows = x.shape[1] // 20
for epoch in range(epochs):
    h_t = torch.zeros(bs, 256, dtype=torch.float32, device=torch.device('cpu'))
    epoch_loss = 0
    for window_id, i in enumerate(range(0, x.shape[1] - 20, 20)):
        loss_all = torch.tensor(0.0, dtype=torch.float32, device=torch.device('cpu'))
        optimizer.zero_grad()
        h_t = h_t.detach()
        for j in range(i, i + 20):
            # 所有行的第i列
            x_input = embeddings(x[:, j]) # shape：75,128
            h_t = torch.tanh(x_linear(x_input) + h_linear(h_t))
            y_pred = output_linear(h_t)
            # 计算损失
            loss_all += criterion(y_pred, y[:, j])
        loss_all.backward()
        optimizer.step()
        epoch_loss += loss_all.item()
        # 每200个窗口打印一次进度
        if window_id % 200 == 0:
            print(f'epoch {epoch+1}/{epochs} | 窗口 {window_id}/{num_windows} | 当前窗口loss {loss_all.item():.2f}')
    print(f'=== epoch {epoch+1} 完成 | 平均loss {epoch_loss/num_windows:.2f} ===')


torch.save({
    'embeddings': embeddings.state_dict(),
    'x_linear': x_linear.state_dict(),
    'h_linear': h_linear.state_dict(),
    'output_linear': output_linear.state_dict(),
    'word2id': word2id,
    'id2word': id2word,
}, 'rnn_wiki-text_model.pt')