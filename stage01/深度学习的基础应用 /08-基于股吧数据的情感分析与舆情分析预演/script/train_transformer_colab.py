from datasets import load_dataset
from collections import Counter
from torch import nn
import torch
import math
from torch.utils.data import Dataset, DataLoader


# ============================================
# 1. 数据加载与EDA
# ============================================
dataset = load_dataset("HikasaHana/eastmoney_guba_title")
train_labels = dataset['train']['label']
print(Counter(train_labels))
lengths = [len(t) for t in dataset['train']['title']]
print(f'最短: {min(lengths)}, 最长: {max(lengths)}, 平均: {sum(lengths)/len(lengths):.1f}')
# 标签分布: Counter({2: 3581, 0: 2529, 1: 2406}) 基本均衡
# 文本长度: 最短1, 最长79, 平均20.6, max_len=64绰绰有余


# ============================================
# 2. 字级别分词 + 构建词表
# ============================================
# 中文按字切分: "下周看涨" → ['下', '周', '看', '涨']
# 不依赖外部tokenizer，字级别词表小（~8000），数据量够用

special_tokens = ['<pad>', '<unk>']
char_counter = Counter()
for text in dataset['train']['title']:
    char_counter.update(list(text))

# 过滤低频字（出现<3次的用<unk>替代）
vocab = special_tokens + [c for c, cnt in char_counter.items() if cnt >= 3]
word2id = {w: i for i, w in enumerate(vocab)}
id2word = {i: w for i, w in enumerate(vocab)}
vocab_size = len(vocab)
print(f'词表大小: {vocab_size}')

PAD_ID = word2id['<pad>']
UNK_ID = word2id['<unk>']


# ============================================
# 3. 数据集与DataLoader
# ============================================
MAX_LEN = 64

class GubaDataset(Dataset):
    def __init__(self, texts, labels, word2id, max_len):
        self.texts = texts
        self.labels = labels
        self.word2id = word2id
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        # 字级别分词
        chars = list(self.texts[idx])[:self.max_len]
        # 转 id，未知字用 <unk>
        ids = [self.word2id.get(c, UNK_ID) for c in chars]
        # padding 到 max_len
        pad_len = self.max_len - len(ids)
        ids = ids + [PAD_ID] * pad_len
        return torch.tensor(ids), torch.tensor(self.labels[idx])


# 划分 train / validation（train 的 90% / 10%）
train_texts = dataset['train']['title']
train_labels_list = dataset['train']['label']
split_idx = int(len(train_texts) * 0.9)

train_dataset = GubaDataset(train_texts[:split_idx], train_labels_list[:split_idx], word2id, MAX_LEN)
val_dataset = GubaDataset(train_texts[split_idx:], train_labels_list[split_idx:], word2id, MAX_LEN)
test_dataset = GubaDataset(dataset['test']['title'], dataset['test']['label'], word2id, MAX_LEN)

print(f'训练集: {len(train_dataset)}, 验证集: {len(val_dataset)}, 测试集: {len(test_dataset)}')


# ============================================
# 4. 模型组件
# ============================================

class SelfAttention(nn.Module):
    def __init__(self, d_model, d_k):
        super().__init__()
        self.d_k = d_k
        self.W_q = nn.Linear(d_model, d_k)
        self.W_k = nn.Linear(d_model, d_k)
        self.W_v = nn.Linear(d_model, d_k)

    def forward(self, x):
        # x: (batch, seq_len, d_model)
        q = self.W_q(x)  # (batch, seq_len, d_k)
        k = self.W_k(x)
        v = self.W_v(x)
        # 相似度 → softmax → 加权求和
        scores = q @ k.transpose(-2, -1) / math.sqrt(self.d_k)
        weights = torch.softmax(scores, dim=-1)
        context = weights @ v  # (batch, seq_len, d_k)
        return context


class MultiHeadAttention(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        d_k = d_model // n_heads
        self.attentions = nn.ModuleList([SelfAttention(d_model, d_k) for _ in range(n_heads)])
        self.fc = nn.Linear(d_model, d_model)

    def forward(self, x):
        # 每个头各自跑，拼接后 fc 融合
        x = torch.cat([att(x) for att in self.attentions], dim=-1)
        return self.fc(x)


class FeedForward(nn.Module):
    def __init__(self, d_model, d_ff):
        super().__init__()
        self.fc1 = nn.Linear(d_model, d_ff)   # 升维
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(d_ff, d_model)   # 降回来

    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x


class TransformerBlock(nn.Module):
    def __init__(self, d_model, n_heads, d_ff, dropout):
        super().__init__()
        self.attention = MultiHeadAttention(d_model, n_heads)
        self.ffn = FeedForward(d_model, d_ff)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, mask=None):
        # Multi-Head Attention + 残差 + LayerNorm
        attn_out = self.attention(x)
        if mask is not None:
            attn_out = attn_out.masked_fill(mask.unsqueeze(-1), 0)
        x = self.norm1(x + self.dropout(attn_out))
        # FeedForward + 残差 + LayerNorm
        ffn_out = self.ffn(x)
        x = self.norm2(x + self.dropout(ffn_out))
        return x


class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=512):
        super().__init__()
        # 预计算位置编码，不需要学习
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()  # (max_len, 1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)  # 偶数位用 sin
        pe[:, 1::2] = torch.cos(position * div_term)  # 奇数位用 cos
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer('pe', pe)  # 不算参数，但会跟随模型移动设备

    def forward(self, x):
        # x: (batch, seq_len, d_model)
        return x + self.pe[:, :x.size(1)]


class TransformerClassifier(nn.Module):
    def __init__(self, vocab_size, d_model, n_heads, n_layers, d_ff, max_len, num_classes, dropout):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model, padding_idx=PAD_ID)
        self.pos_encoding = PositionalEncoding(d_model, max_len)
        self.layers = nn.ModuleList([
            TransformerBlock(d_model, n_heads, d_ff, dropout) for _ in range(n_layers)
        ])
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(d_model, num_classes)  # 分类头

    def forward(self, x):
        # x: (batch, seq_len) 整数id
        # 构建 padding mask: True 的位置要被遮住
        mask = (x == PAD_ID)  # (batch, seq_len)

        x = self.embedding(x)        # (batch, seq_len, d_model)
        x = self.pos_encoding(x)     # 加位置信息
        x = self.dropout(x)

        for layer in self.layers:
            x = layer(x, mask=mask)  # (batch, seq_len, d_model)

        # Global Average Pooling: 对 seq_len 维度取平均，忽略 padding
        mask_expanded = mask.unsqueeze(-1).expand_as(x)  # (batch, seq_len, d_model)
        x = x.masked_fill(mask_expanded, 0)  # padding 位置填 0
        lengths = (~mask).sum(dim=1, keepdim=True).float()  # 实际长度 (batch, 1)
        x = x.sum(dim=1) / lengths  # (batch, d_model)

        x = self.dropout(x)
        logits = self.fc(x)  # (batch, num_classes)
        return logits


# ============================================
# 5. 训练配置
# ============================================
D_MODEL = 128
N_HEADS = 4
N_LAYERS = 2
D_FF = 512
DROPOUT = 0.3
BATCH_SIZE = 32
EPOCHS = 30
LR = 0.001
NUM_CLASSES = 3  # 看空(0)/看多(1)/中性(2)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'使用设备: {device}')

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)
test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE)

model = TransformerClassifier(
    vocab_size=vocab_size,
    d_model=D_MODEL,
    n_heads=N_HEADS,
    n_layers=N_LAYERS,
    d_ff=D_FF,
    max_len=MAX_LEN,
    num_classes=NUM_CLASSES,
    dropout=DROPOUT
).to(device)

print(f'模型参数量: {sum(p.numel() for p in model.parameters()):,}')

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=LR)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)


# ============================================
# 6. 训练循环
# ============================================
best_val_f1 = 0
patience = 5
patience_counter = 0

for epoch in range(EPOCHS):
    # --- 训练 ---
    model.train()
    train_loss = 0
    train_correct = 0
    train_total = 0

    for batch_x, batch_y in train_loader:
        batch_x, batch_y = batch_x.to(device), batch_y.to(device)
        logits = model(batch_x)
        loss = criterion(logits, batch_y)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        train_loss += loss.item() * batch_x.size(0)
        train_correct += (logits.argmax(dim=1) == batch_y).sum().item()
        train_total += batch_x.size(0)

    scheduler.step()

    # --- 验证 ---
    model.eval()
    val_loss = 0
    val_correct = 0
    val_total = 0
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for batch_x, batch_y in val_loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            logits = model(batch_x)
            loss = criterion(logits, batch_y)
            val_loss += loss.item() * batch_x.size(0)
            preds = logits.argmax(dim=1)
            val_correct += (preds == batch_y).sum().item()
            val_total += batch_x.size(0)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(batch_y.cpu().tolist())

    train_acc = train_correct / train_total
    val_acc = val_correct / val_total

    # 计算 F1-macro
    from sklearn.metrics import f1_score
    val_f1 = f1_score(all_labels, all_preds, average='macro')

    print(f'Epoch {epoch+1}/{EPOCHS} | Train Loss: {train_loss/train_total:.4f} Acc: {train_acc:.4f} | Val Loss: {val_loss/val_total:.4f} Acc: {val_acc:.4f} F1-macro: {val_f1:.4f}')

    # Early Stopping
    if val_f1 > best_val_f1:
        best_val_f1 = val_f1
        patience_counter = 0
        torch.save(model.state_dict(), 'best_transformer_model.pt')
        print(f'  → 保存最佳模型 (F1: {val_f1:.4f})')
    else:
        patience_counter += 1
        if patience_counter >= patience:
            print(f'Early stopping! 连续 {patience} 轮无提升')
            break

# ============================================
# 7. 测试集评估
# ============================================
from sklearn.metrics import classification_report, confusion_matrix

model.load_state_dict(torch.load('best_transformer_model.pt'))
model.eval()
all_preds = []
all_labels = []

with torch.no_grad():
    for batch_x, batch_y in test_loader:
        batch_x = batch_x.to(device)
        logits = model(batch_x)
        preds = logits.argmax(dim=1)
        all_preds.extend(preds.cpu().tolist())
        all_labels.extend(batch_y.tolist())

print('\n=== 测试集评估报告 ===')
print(classification_report(all_labels, all_preds, target_names=['看空', '看多', '中性']))
print('混淆矩阵:')
print(confusion_matrix(all_labels, all_preds))
