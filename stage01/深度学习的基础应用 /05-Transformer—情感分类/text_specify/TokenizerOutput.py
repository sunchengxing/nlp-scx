from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TokenizerOutput:
    text: str
    tokens: List[str]
    token_ids: List[int]
    label: Optional[str] = None
    label_id: Optional[int] = None