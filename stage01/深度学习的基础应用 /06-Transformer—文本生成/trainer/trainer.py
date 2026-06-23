import math
import torch
import torch.nn as nn
from torch.utils.data import DataLoader


class Trainer:
    def __init__(self, model: nn.Module, cfg, save_path: str = "best_model.pt"):
        self.model = model.to(cfg.DEVICE)
        self.cfg = cfg
        self.save_path = save_path
        self.criterion = nn.CrossEntropyLoss()
        self.optimizer = torch.optim.Adam(model.parameters(), lr=cfg.LEARNING_RATE)
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=cfg.EPOCH
        )
        self.best_ppl = float("inf")

    def _step(self, batch):
        x, y = batch
        x, y = x.to(self.cfg.DEVICE), y.to(self.cfg.DEVICE)
        logits = self.model(x)                        # (B, T, V)
        B, T, V = logits.shape
        loss = self.criterion(logits.view(B * T, V), y.view(B * T))
        return loss

    def train_epoch(self, loader: DataLoader) -> float:
        self.model.train()
        total_loss = 0.0
        for batch in loader:
            self.optimizer.zero_grad()
            loss = self._step(batch)
            loss.backward()
            nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()
            total_loss += loss.item()
        return total_loss / len(loader)

    @torch.no_grad()
    def eval_epoch(self, loader: DataLoader) -> float:
        self.model.eval()
        total_loss = 0.0
        for batch in loader:
            total_loss += self._step(batch).item()
        return total_loss / len(loader)

    def fit(self, train_loader: DataLoader, valid_loader: DataLoader):
        for epoch in range(1, self.cfg.EPOCH + 1):
            train_loss = self.train_epoch(train_loader)
            val_loss = self.eval_epoch(valid_loader)
            val_ppl = math.exp(val_loss)
            self.scheduler.step()

            marker = ""
            if val_ppl < self.best_ppl:
                self.best_ppl = val_ppl
                torch.save(self.model.state_dict(), self.save_path)
                marker = "  ← best"

            print(
                f"Epoch {epoch:02d}/{self.cfg.EPOCH} | "
                f"train_loss={train_loss:.4f} | "
                f"val_loss={val_loss:.4f} | "
                f"val_ppl={val_ppl:.2f}{marker}"
            )
        print(f"\nBest val PPL: {self.best_ppl:.2f}  (saved to {self.save_path})")
