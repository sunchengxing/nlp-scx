from typing import Dict, Optional
import TokenizerOutput
import split_tokens as sp


class Tokenizer:
    def __init__(self, token2ids: Dict[str, int], label2ids: Dict[str, int],
                 unk_token="<UNK>", pad_token="<PAD>"):
        self.token2ids = token2ids
        self.label2ids = label2ids
        self.unk_token_id = token2ids[unk_token]
        self.pad_token_id = token2ids[pad_token]

    def __call__(self, text: str, label: Optional[str] = None) -> TokenizerOutput:
        tokens = sp.SplitTokensTools(text)
        token_ids = [self.token2ids.get(t, self.unk_token_id) for t in tokens]
        label_id = self.label2ids[label] if label is not None else None
        return TokenizerOutput(text, tokens, token_ids, label, label_id)