# ── 依赖：pip install datasets torch
import math                          # 计算 log/exp，PPL = exp(loss) 需要
import torch                         # PyTorch 主库
import torch.nn as nn                # 神经网络模块
import torch.nn.functional as F      # 激活/softmax 等函数
from collections import Counter      # 统计词频，用于构建词表
from datasets import load_dataset    # HuggingFace datasets，加载 wikitext
from torch.utils.data import Dataset, DataLoader  # 数据集抽象与批加载器

# ══════════════════════════════════════════════
# 1. Config
# ══════════════════════════════════════════════
class Config:
    DATASET_NAME        = "Salesforce/wikitext"   # HuggingFace 数据集名称
    DATASET_VERSION     = "wikitext-103-raw-v1"      # wikitext-103-raw-v1 原始格式版本 1亿
    MAX_VOCABULARY_SIZE = 50000                    # 词表最大词数（含 4 个特殊 token）
    SEQ_LEN             = 128                      # 每条训练样本的序列长度
    EMBED_DIM           = 256                      # Token Embedding 维度 d_model
    HIDDEN_SIZE         = 512                      # FFN 隐层宽度（实际 FF = 256*2）
    NUM_LAYERS          = 4                        # Transformer Block 堆叠层数
    DROPOUT             = 0.2                      # Dropout 概率，防止过拟合
    BATCH_SIZE          = 64                       # 每批样本数
    EPOCH               = 30                       # 训练总轮数
    LEARNING_RATE       = 0.001                    # Adam 初始学习率
    DEVICE              = "cuda" if torch.cuda.is_available() else "cpu"  # 自动选 GPU/CPU
    SAVE_PATH           = "transformer_lm_best-e30.pt" # 验证 PPL 最优时保存路径

cfg = Config()                                     # 实例化全局配置
print(f"Device: {cfg.DEVICE}")                     # 打印当前运行设备

# ══════════════════════════════════════════════
# 2. Data
# ══════════════════════════════════════════════
PAD, UNK = "<pad>", "<unk>"                        # 填充 token 和未登录词 token
SPECIALS  = [PAD, UNK, "<bos>", "<eos>"]           # 4 个特殊 token，固定占编号 0~3

def build_vocab(texts, max_size):
    counter = Counter()
    for t in texts: counter.update(t.split())          # 按空格拆词并统计词频
    vocab = {tok: i for i, tok in enumerate(SPECIALS)} # 特殊 token 先占位 0~3
    for w, _ in counter.most_common(max_size - len(SPECIALS)):
        vocab[w] = len(vocab)                          # 按词频从高到低填入，超出截断
    return vocab                                       # 返回 word->id 字典

def tokenize(texts, vocab):
    unk = vocab[UNK]                                   # 未登录词统一映射到 <unk>
    ids = []
    for t in texts: ids.extend(vocab.get(w, unk) for w in t.split())  # 逐词转 id
    return ids                                         # 返回整个语料拼接后的 id 列表

class WikitextDataset(Dataset):
    def __init__(self, tokens, seq_len):
        n = (len(tokens) - 1) // seq_len              # 能切出多少个完整样本
        self.seq_len = seq_len
        self.data = torch.tensor(tokens[:n * seq_len + 1], dtype=torch.long)  # 保留整数倍部分
    def __len__(self): return (len(self.data) - 1) // self.seq_len  # 样本总数
    def __getitem__(self, i):
        s = i * self.seq_len                           # 当前样本起始位置
        c = self.data[s: s + self.seq_len + 1]         # 取 seq_len+1 个 token
        return c[:-1], c[1:]                           # input=前 seq_len，target=后 seq_len（错位1）

def get_dataloaders(cfg):
    raw = load_dataset(cfg.DATASET_NAME, cfg.DATASET_VERSION)    # 下载/缓存 wikitext-2
    train_txt = [t for t in raw["train"]["text"] if t.strip()]   # 过滤空行
    valid_txt = [t for t in raw["validation"]["text"] if t.strip()]
    vocab = build_vocab(train_txt, cfg.MAX_VOCABULARY_SIZE)      # 只用训练集建词表
    tr = DataLoader(WikitextDataset(tokenize(train_txt, vocab), cfg.SEQ_LEN),
                    batch_size=cfg.BATCH_SIZE, shuffle=True,  drop_last=True)  # 训练集打乱
    va = DataLoader(WikitextDataset(tokenize(valid_txt, vocab), cfg.SEQ_LEN),
                    batch_size=cfg.BATCH_SIZE, shuffle=False, drop_last=True)  # 验证集不打乱
    return vocab, tr, va

# ══════════════════════════════════════════════
# 3. Model
# ══════════════════════════════════════════════
class PositionalEncoding(nn.Module):
    def __init__(self, d, max_len=512, dropout=0.1):
        super().__init__()
        self.drop = nn.Dropout(dropout)                # 位置编码后的 dropout
        pe = torch.zeros(max_len, d)                   # 预计算位置编码矩阵 (max_len, d)
        pos = torch.arange(max_len).unsqueeze(1).float()  # 位置向量 (max_len, 1)
        div = torch.exp(torch.arange(0, d, 2).float() * (-math.log(10000.0) / d))  # 频率
        pe[:, 0::2] = torch.sin(pos * div)             # 偶数维度用 sin
        pe[:, 1::2] = torch.cos(pos * div)             # 奇数维度用 cos
        self.register_buffer("pe", pe.unsqueeze(0))    # 注册为非参数 buffer，(1, max_len, d)
    def forward(self, x):
        return self.drop(x + self.pe[:, :x.size(1)])   # 叠加位置编码后 dropout

class Block(nn.Module):
    def __init__(self, d, nhead, ff, dropout):
        super().__init__()
        self.attn = nn.MultiheadAttention(d, nhead, dropout=dropout, batch_first=True)  # 多头注意力
        self.ff   = nn.Sequential(nn.Linear(d, ff), nn.GELU(), nn.Dropout(dropout), nn.Linear(ff, d))  # FFN
        self.ln1  = nn.LayerNorm(d)                    # 注意力后的 LayerNorm
        self.ln2  = nn.LayerNorm(d)                    # FFN 后的 LayerNorm
        self.drop = nn.Dropout(dropout)                # 残差连接前的 dropout
    def forward(self, x, mask):
        a, _ = self.attn(x, x, x, attn_mask=mask, is_causal=True)  # Causal 自注意力
        x = self.ln1(x + self.drop(a))                 # 残差 + LayerNorm
        return self.ln2(x + self.drop(self.ff(x)))     # FFN 残差 + LayerNorm

class TransformerLM(nn.Module):
    def __init__(self, vocab_size, d, nhead, layers, ff, max_len, dropout):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, d)       # token -> 向量，词表大小 × d
        self.pos   = PositionalEncoding(d, max_len, dropout)  # 注入位置信息
        self.blocks= nn.ModuleList([Block(d, nhead, ff, dropout) for _ in range(layers)])  # N 层 Block
        self.ln    = nn.LayerNorm(d)                   # 最终输出前的 LayerNorm
        self.head  = nn.Linear(d, vocab_size, bias=False)  # 投影到词表，输出 logits
        for p in self.parameters():
            if p.dim() > 1: nn.init.xavier_uniform_(p)  # Xavier 初始化，稳定训练
    def forward(self, x):
        T    = x.size(1)                               # 序列长度
        mask = torch.triu(torch.full((T, T), float("-inf"), device=x.device), diagonal=1)  # 因果掩码
        x    = self.pos(self.embed(x))                 # Embedding + 位置编码
        for b in self.blocks: x = b(x, mask)           # 依次通过 N 个 Block
        return self.head(self.ln(x))                   # LM Head 输出 (B, T, vocab_size)

# ══════════════════════════════════════════════
# 4. Train / Eval
# ══════════════════════════════════════════════
def train_epoch(model, loader, criterion, optimizer, device):
    model.train()                                      # 开启训练模式（dropout 生效）
    total = 0.0
    for x, y in loader:
        x, y = x.to(device), y.to(device)             # 数据移到 GPU/CPU
        optimizer.zero_grad()                          # 清空梯度
        logits = model(x)                              # 前向：(B, T, V)
        B, T, V = logits.shape
        loss = criterion(logits.view(B*T, V), y.view(B*T))  # 展平后计算交叉熵
        loss.backward()                                # 反向传播
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)   # 梯度裁剪，防梯度爆炸
        optimizer.step()                               # 更新参数
        total += loss.item()
    return total / len(loader)                         # 返回平均 loss

@torch.no_grad()
def eval_epoch(model, loader, criterion, device):
    model.eval()                                       # 关闭 dropout
    total = 0.0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        logits = model(x)
        B, T, V = logits.shape
        total += criterion(logits.view(B*T, V), y.view(B*T)).item()
    return total / len(loader)                         # 返回平均验证 loss

# ══════════════════════════════════════════════
# 5. Main
# ══════════════════════════════════════════════
if __name__ == "__main__":
    print("Loading data...")
    vocab, train_loader, valid_loader = get_dataloaders(cfg)   # 加载数据 + 构建词表
    print(f"Vocab: {len(vocab)}  train: {len(train_loader)}  valid: {len(valid_loader)}")

    model = TransformerLM(                             # 构建模型
        vocab_size=len(vocab), d=cfg.EMBED_DIM, nhead=8,       # nhead=8，d=256 可整除
        layers=cfg.NUM_LAYERS, ff=cfg.HIDDEN_SIZE*2,           # FF = 1024
        max_len=cfg.SEQ_LEN+10, dropout=cfg.DROPOUT            # max_len 留余量
    ).to(cfg.DEVICE)
    print(f"Params: {sum(p.numel() for p in model.parameters()):,}")  # 打印参数量

    criterion = nn.CrossEntropyLoss()                  # 多分类交叉熵损失
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg.LEARNING_RATE)  # Adam 优化器
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=cfg.EPOCH)  # 余弦退火

    best_ppl = float("inf")                            # 记录最优 PPL
    for epoch in range(1, cfg.EPOCH + 1):
        tr_loss = train_epoch(model, train_loader, criterion, optimizer, cfg.DEVICE)
        va_loss = eval_epoch(model, valid_loader, criterion, cfg.DEVICE)
        ppl     = math.exp(va_loss)                    # PPL = exp(avg_loss)
        scheduler.step()                               # 更新学习率
        mark = ""
        if ppl < best_ppl:                             # 验证 PPL 改善则保存模型
            best_ppl = ppl
            torch.save(model.state_dict(), cfg.SAVE_PATH)
            mark = "  <- best"
        print(f"Epoch {epoch:02d}/{cfg.EPOCH} | train={tr_loss:.4f} | val={va_loss:.4f} | ppl={ppl:.2f}{mark}")

    print(f"\nDone. Best PPL: {best_ppl:.2f}  model saved -> {cfg.SAVE_PATH}")
