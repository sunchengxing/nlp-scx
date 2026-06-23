from torch.utils.data import DataLoader

from .vocab import load_wikitext
from .dataset import WikitextDataset


def get_dataloaders(cfg):
    vocab, train_tokens, valid_tokens = load_wikitext(
        cfg.DATASET_NAME, cfg.DATASET_VERSION, cfg.MAX_VOCABULARY_SIZE
    )
    train_ds = WikitextDataset(train_tokens, cfg.SEQ_LEN)
    valid_ds = WikitextDataset(valid_tokens, cfg.SEQ_LEN)

    train_loader = DataLoader(train_ds, batch_size=cfg.BATCH_SIZE, shuffle=True, drop_last=True)
    valid_loader = DataLoader(valid_ds, batch_size=cfg.BATCH_SIZE, shuffle=False, drop_last=True)
    return vocab, train_loader, valid_loader
