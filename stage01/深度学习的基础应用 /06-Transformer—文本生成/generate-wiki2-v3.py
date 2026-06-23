import math, argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
from collections import Counter
from datasets import load_dataset


# 1. Config（必须与 train-wiki2-v3.py 完全一致）
class Config:
    DATASET_NAME        = "Salesforce/wikitext"
    DATASET_VERSION     = "wikitext-2-raw-v1"
    MAX_VOCABULARY_SIZE = 50000
    SEQ_LEN             = 128
    EMBED_DIM           = 128
    HIDDEN_SIZE         = 256
    NUM_LAYERS          = 2
    DROPOUT             = 0.2
    DEVICE              = "cuda" if torch.cuda.is_available() else "cpu"
    MODEL_PATH          = "./file/transformer_lm_best-wiki2-v3.pt"

cfg = Config()


# 2. 词表重建（与训练时完全一致）
PAD, UNK = "<pad>", "<unk>"
SPECIALS  = [PAD, UNK, "<bos>", "<eos>"]

def build_vocab(texts, max_size):
    counter = Counter()
    for t in texts: counter.update(t.split())
    vocab = {tok: i for i, tok in enumerate(SPECIALS)}
    for w, _ in counter.most_common(max_size - len(SPECIALS)):
        vocab[w] = len(vocab)
    return vocab

def load_vocab():
    print("重建词表...")
    raw = load_dataset(cfg.DATASET_NAME, cfg.DATASET_VERSION)
    train_txt = [t for t in raw["train"]["text"] if t.strip()]
    return build_vocab(train_txt, cfg.MAX_VOCABULARY_SIZE)

# 3. 模型（与 train-wiki2-v3.py 完全一致）
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


# 4. generate
@torch.no_grad()
def generate(model, vocab, prompt, max_len=100, top_k=5, temperature=1.0):
    idx2word = {v: k for k, v in vocab.items()}
    unk_id   = vocab.get("<unk>", 0)
    eos_id   = vocab.get("<eos>", -1)
    model.eval()
    ids = [vocab.get(w, unk_id) for w in prompt.split()]
    ctx = torch.tensor([ids], dtype=torch.long, device=cfg.DEVICE)
    for _ in range(max_len):
        window = ctx[:, -cfg.SEQ_LEN:]
        logits = model(window)[:, -1, :] / temperature
        if top_k > 1:
            vals, _ = torch.topk(logits, top_k)
            logits  = logits.masked_fill(logits < vals[:, -1:], float("-inf"))
            nxt     = torch.multinomial(F.softmax(logits, dim=-1), num_samples=1)
        else:
            nxt = logits.argmax(dim=-1, keepdim=True)
        ctx = torch.cat([ctx, nxt], dim=1)
        if nxt.item() == eos_id:
            break
    out_ids = ctx[0, len(ids):].tolist()
    return " ".join(idx2word.get(i, "<unk>") for i in out_ids)

# 5. main
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",       default=cfg.MODEL_PATH,  help=".pt model path")
    parser.add_argument("--prompt",      default="The history of")
    parser.add_argument("--max_len",     type=int,   default=100)
    parser.add_argument("--top_k",       type=int,   default=5)
    parser.add_argument("--temperature", type=float, default=0.8)
    args = parser.parse_args()

    vocab = load_vocab()
    print(f"Vocab: {len(vocab)}  |  Device: {cfg.DEVICE}")

    model = TransformerLM(
        vocab_size=len(vocab), d=cfg.EMBED_DIM, nhead=4,
        layers=cfg.NUM_LAYERS, ff=cfg.HIDDEN_SIZE * 2,
        max_len=cfg.SEQ_LEN + 10, dropout=cfg.DROPOUT,
    ).to(cfg.DEVICE)
    model.load_state_dict(torch.load(args.model, map_location=cfg.DEVICE))
    print(f"Model loaded: {args.model}")

    result = generate(model, vocab, args.prompt, args.max_len, args.top_k, args.temperature)
    print(f"\nPrompt : {args.prompt}")
    print(f"Output : {result}")
