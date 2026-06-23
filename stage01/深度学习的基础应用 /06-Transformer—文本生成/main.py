import argparse
import torch

from config.config import Config
from data import get_dataloaders
from model import TransformerLM
from trainer import Trainer
from inference import TextGenerator

MODEL_PATH = "transformer_lm_best-20000.pt"


def build_model(cfg, vocab_size: int) -> TransformerLM:
    nhead = 4
    dim_ff = cfg.HIDDEN_SIZE * 2
    return TransformerLM(
        vocab_size=vocab_size,
        d_model=cfg.EMBED_DIM,
        nhead=nhead,
        num_layers=cfg.NUM_LAYERS,
        dim_ff=dim_ff,
        max_len=cfg.SEQ_LEN + 10,
        dropout=cfg.DROPOUT,
    )


def train(cfg: Config):
    print("Loading dataset...")
    vocab, train_loader, valid_loader = get_dataloaders(cfg)
    print(f"Vocab size: {len(vocab)}  |  train batches: {len(train_loader)}")

    model = build_model(cfg, len(vocab))
    total = sum(p.numel() for p in model.parameters())
    print(f"Model params: {total:,}")

    trainer = Trainer(model, cfg, save_path=MODEL_PATH)
    trainer.fit(train_loader, valid_loader)


def generate(cfg: Config, prompt: str, top_k: int, temperature: float):
    print("Loading dataset (vocab only)...")
    vocab, _, _ = get_dataloaders(cfg)

    model = build_model(cfg, len(vocab))
    model.load_state_dict(torch.load(MODEL_PATH, map_location=cfg.DEVICE))
    print(f"Model loaded from {MODEL_PATH}")

    gen = TextGenerator(model, vocab, cfg)
    result = gen.generate(prompt, top_k=top_k, temperature=temperature)
    print(f"\nPrompt : {prompt}")
    print(f"Output : {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["train", "generate"])
    parser.add_argument("--prompt", default="The history of")
    parser.add_argument("--top_k", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    args = parser.parse_args()

    cfg = Config()
    if args.mode == "train":
        train(cfg)
    else:
        generate(cfg, args.prompt, args.top_k, args.temperature)
