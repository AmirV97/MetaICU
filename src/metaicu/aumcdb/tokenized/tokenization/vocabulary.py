"""Minimal token vocabulary compatible with ETHOS-style safetensor outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl


@dataclass(frozen=True)
class TokenVocabulary:
    """Stable code -> integer token mapping.

    Token IDs are zero-based row positions in the written ``vocab_t*.csv``,
    matching ETHOS's convention.
    """

    codes: tuple[str, ...]

    @property
    def stoi(self) -> dict[str, int]:
        return {code: idx for idx, code in enumerate(self.codes)}

    def __len__(self) -> int:
        return len(self.codes)

    def dump(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        vocab_path = output_dir / f"vocab_t{len(self)}.csv"
        pl.DataFrame({"code": list(self.codes)}).write_csv(vocab_path, include_header=False)
        pl.DataFrame({"word": list(self.codes), "label": list(self.codes)}).write_csv(
            output_dir / "vocab_decoded.csv"
        )
        return vocab_path


def build_lexicographic_vocab(codes: list[str]) -> TokenVocabulary:
    """Build a deterministic vocabulary from observed train codes."""

    return TokenVocabulary(tuple(sorted(set(codes))))

