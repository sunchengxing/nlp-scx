import torch
import torch.nn.functional as F


class TextGenerator:
    def __init__(self, model, vocab: dict[str, int], cfg):
        self.model = model.to(cfg.DEVICE)
        self.vocab = vocab
        self.idx2word = {v: k for k, v in vocab.items()}
        self.cfg = cfg
        self.unk_id = vocab.get("<unk>", 0)

    def _encode(self, prompt: str) -> list[int]:
        return [self.vocab.get(w, self.unk_id) for w in prompt.split()]

    def generate(self, prompt: str, max_len: int | None = None,
                 top_k: int | None = None, temperature: float = 1.0) -> str:
        max_len = max_len or self.cfg.MAX_GEN_LEN
        top_k = top_k or self.cfg.TOP_K
        temperature = temperature or self.cfg.TEMPERATURE

        self.model.eval()
        ids = self._encode(prompt)
        ctx = torch.tensor([ids], dtype=torch.long, device=self.cfg.DEVICE)

        with torch.no_grad():
            for _ in range(max_len):
                # 只取最近 SEQ_LEN 个 token 作为上下文
                window = ctx[:, -self.cfg.SEQ_LEN:]
                logits = self.model(window)          # (1, T, V)
                logits = logits[:, -1, :] / temperature  # 取最后一步

                if top_k and top_k > 1:
                    # top-k sampling
                    values, _ = torch.topk(logits, top_k)
                    threshold = values[:, -1].unsqueeze(-1)
                    logits = logits.masked_fill(logits < threshold, float("-inf"))
                    probs = F.softmax(logits, dim=-1)
                    next_id = torch.multinomial(probs, num_samples=1)
                else:
                    # greedy
                    next_id = logits.argmax(dim=-1, keepdim=True)

                ctx = torch.cat([ctx, next_id], dim=1)
                if next_id.item() == self.vocab.get("<eos>", -1):
                    break

        generated = ctx[0, len(ids):].tolist()
        return " ".join(self.idx2word.get(i, "<unk>") for i in generated)
