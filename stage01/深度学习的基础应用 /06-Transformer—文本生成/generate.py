# ── 使用方式：python generate.py --model transformer_lm_best-20000.pt --prompt "The history of"
# ── 依赖：pip install datasets torch
import math, argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
from collections import Counter
from datasets import load_dataset

# ══════════════════════════════════════════════
# 1. Config（必须与 train-wiki-origin.py 完全一致）
# ══════════════════════════════════════════════
class Config:
    DATASET_NAME        = "Salesforce/wikitext"   # HuggingFace 数据集名
    DATASET_VERSION     = "wikitext-2-raw-v1"      # 数据集版本
    MAX_VOCABULARY_SIZE = 50000                    # 词表大小上限（必须与训练时一致）
    SEQ_LEN             = 128                      # 训练时的序列长度，推理时作为上下文窗口
    EMBED_DIM           = 128                      # Embedding 维度
    HIDDEN_SIZE         = 256                      # FFN 隐层维度（FF = HIDDEN_SIZE*2）
    NUM_LAYERS          = 2                        # Transformer Block 层数
    DROPOUT             = 0.3                      # Dropout 概率（推理时 eval 模式自动关闭）
    DEVICE              = "cuda" if torch.cuda.is_available() else "cpu"

cfg = Config()

# ══════════════════════════════════════════════
# 2. 重建词表（必须与训练时完全一致）
# ══════════════════════════════════════════════
PAD, UNK = "<pad>", "<unk>"
SPECIALS  = [PAD, UNK, "<bos>", "<eos>"]

def build_vocab(texts, max_size):
    counter = Counter()
    for t in texts: counter.update(t.split())          # 统计词频
    vocab = {tok: i for i, tok in enumerate(SPECIALS)} # 先放特殊 token
    for w, _ in counter.most_common(max_size - len(SPECIALS)):
        vocab[w] = len(vocab)                          # 按词频填入普通词
    return vocab

def load_vocab():
    print("重建词表（加载 wikitext-2 train split）...")
    raw = load_dataset(cfg.DATASET_NAME, cfg.DATASET_VERSION)
    train_txt = [t for t in raw["train"]["text"] if t.strip()]
    return build_vocab(train_txt, cfg.MAX_VOCABULARY_SIZE)

# ══════════════════════════════════════════════
# 3. 模型定义（与 train-wiki-origin.py 完全一致）
# ══════════════════════════════════════════════
class PositionalEncoding(nn.Module):
    def __init__(self, d, max_len=512, dropout=0.1):
        super().__init__()
        self.drop = nn.Dropout(dropout)
        pe = torch.zeros(max_len, d)
        pos = torch.arange(max_len).unsqueeze(1).float()
        div = torch.exp(torch.arange(0, d, 2).float() * (-math.log(10000.0) / d))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0))
    def forward(self, x):
        return self.drop(x + self.pe[:, :x.size(1)])

class Block(nn.Module):
    def __init__(self, d, nhead, ff, dropout):
        super().__init__()
        self.attn = nn.MultiheadAttention(d, nhead, dropout=dropout, batch_first=True)
        self.ff   = nn.Sequential(nn.Linear(d, ff), nn.GELU(), nn.Dropout(dropout), nn.Linear(ff, d))
        self.ln1  = nn.LayerNorm(d); self.ln2 = nn.LayerNorm(d)
        self.drop = nn.Dropout(dropout)
    def forward(self, x, mask):
        a, _ = self.attn(x, x, x, attn_mask=mask, is_causal=True)
        x = self.ln1(x + self.drop(a))
        return self.ln2(x + self.drop(self.ff(x)))

class TransformerLM(nn.Module):
    def __init__(self, vocab_size, d, nhead, layers, ff, max_len, dropout):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, d)
        self.pos   = PositionalEncoding(d, max_len, dropout)
        self.blocks= nn.ModuleList([Block(d, nhead, ff, dropout) for _ in range(layers)])
        self.ln    = nn.LayerNorm(d)
        self.head  = nn.Linear(d, vocab_size, bias=False)
        for p in self.parameters():
            if p.dim() > 1: nn.init.xavier_uniform_(p)
    def forward(self, x):
        T    = x.size(1)
        mask = torch.triu(torch.full((T, T), float("-inf"), device=x.device), diagonal=1)
        x    = self.pos(self.embed(x))
        for b in self.blocks: x = b(x, mask)
        return self.head(self.ln(x))

# ══════════════════════════════════════════════
# 4. 生成函数
# ══════════════════════════════════════════════
@torch.no_grad()
def generate(model, vocab, prompt, max_len=100, top_k=5, temperature=1.0):
    idx2word = {v: k for k, v in vocab.items()}           # id -> word 反查表
    unk_id   = vocab.get("<unk>", 0)                       # 未登录词 id
    eos_id   = vocab.get("<eos>", -1)                      # 句尾 token id

    model.eval()                                           # 关闭 dropout
    ids = [vocab.get(w, unk_id) for w in prompt.split()]  # prompt 编码为 id 列表
    ctx = torch.tensor([ids], dtype=torch.long, device=cfg.DEVICE)  # 初始上下文

    for _ in range(max_len):
        window = ctx[:, -cfg.SEQ_LEN:]                    # 滑动窗口，防止超长
        logits = model(window)[:, -1, :] / temperature    # 取最后一步 logits，温度缩放

        if top_k > 1:                                      # top-k 采样
            vals, _ = torch.topk(logits, top_k)
            logits  = logits.masked_fill(logits < vals[:, -1:], float("-inf"))
            probs   = F.softmax(logits, dim=-1)
            nxt     = torch.multinomial(probs, num_samples=1)
        else:                                              # greedy 解码
            nxt = logits.argmax(dim=-1, keepdim=True)

        ctx = torch.cat([ctx, nxt], dim=1)                # 将新词追加到上下文
        if nxt.item() == eos_id:                          # 遇到 <eos> 停止
            break

    out_ids = ctx[0, len(ids):].tolist()                  # 去掉 prompt 部分
    return " ".join(idx2word.get(i, "<unk>") for i in out_ids)  # 转回文字

# ══════════════════════════════════════════════
# 5. 主程序
# ══════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transformer LM 文本生成")
    # parser.add_argument("--model",       default="./file/transformer_lm_best-20000.pt", help=".pt 模型文件路径")
    parser.add_argument("--model",       default="./file/transformer_lm_best-50000.pt", help=".pt 模型文件路径")
    parser.add_argument("--prompt",      default="The history of",          help="生成起始文本")
    parser.add_argument("--max_len",     type=int,   default=100,           help="最多生成词数")
    parser.add_argument("--top_k",       type=int,   default=5,             help="top-k 采样，1=greedy")
    parser.add_argument("--temperature", type=float, default=1.0,           help="温度，越低越保守")
    args = parser.parse_args()

    # 重建词表（必须与训练时一致）
    vocab = load_vocab()
    print(f"Vocab size: {len(vocab)}")

    # 加载模型
    model = TransformerLM(
        vocab_size=len(vocab), d=cfg.EMBED_DIM, nhead=4,
        layers=cfg.NUM_LAYERS, ff=cfg.HIDDEN_SIZE * 2,
        max_len=cfg.SEQ_LEN + 10, dropout=cfg.DROPOUT,
    ).to(cfg.DEVICE)
    model.load_state_dict(torch.load(args.model, map_location=cfg.DEVICE))
    print(f"Model loaded: {args.model}")

    # 生成
    result = generate(model, vocab, args.prompt, args.max_len, args.top_k, args.temperature)
    print(f"\nPrompt : {args.prompt}")
    print(f"Output : {result}")
