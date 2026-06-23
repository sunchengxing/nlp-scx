from collections import Counter
from datasets import load_dataset


PAD, UNK, BOS, EOS = "<pad>", "<unk>", "<bos>", "<eos>"
SPECIALS = [PAD, UNK, BOS, EOS]


def build_vocab(texts: list[str], max_size: int) -> dict[str, int]:
    counter: Counter = Counter()
    for text in texts:
        counter.update(text.split())
    vocab = {tok: idx for idx, tok in enumerate(SPECIALS)}
    for word, _ in counter.most_common(max_size - len(SPECIALS)):
        vocab[word] = len(vocab)
    return vocab


def tokenize(texts: list[str], vocab: dict[str, int]) -> list[int]:
    unk_id = vocab[UNK]
    tokens: list[int] = []
    for text in texts:
        tokens.extend(vocab.get(w, unk_id) for w in text.split())
    return tokens


def load_wikitext(dataset_name: str, version: str, max_vocab: int):
    raw = load_dataset(dataset_name, version)
    train_texts = [t for t in raw["train"]["text"] if t.strip()]
    valid_texts = [t for t in raw["validation"]["text"] if t.strip()]

    vocab = build_vocab(train_texts, max_vocab)
    train_tokens = tokenize(train_texts, vocab)
    valid_tokens = tokenize(valid_texts, vocab)
    return vocab, train_tokens, valid_tokens
