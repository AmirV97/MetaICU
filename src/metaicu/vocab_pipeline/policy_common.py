"""Shared helpers for vocabulary key normalization and policy replay."""

from __future__ import annotations

import pandas as pd


NULL_TEXT_LITERALS = {"nan", "none", "null"}


def norm_key(value: object) -> str:
    """Normalize source/evidence join keys without changing meaningful labels."""

    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.casefold() in NULL_TEXT_LITERALS:
        return ""
    if text.endswith(".0"):
        try:
            return str(int(float(text)))
        except ValueError:
            return text
    return text


def norm_label_key(value: object) -> str:
    """Normalize labels for exact, non-fuzzy context matching."""

    return " ".join(norm_key(value).casefold().split())
