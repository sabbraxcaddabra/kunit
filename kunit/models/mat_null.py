from __future__ import annotations

from kunit.core.engine import KeywordSpec

# MAT_015
CARDS = [
    ["mid", "ro", "pc", "mu", "terod", "cerod", "ym", "pr"],
]

DIMS = {
    "ro": (1, -3, 0),
    "mu": (1, -1, -1),
    "pc": (1, -1, -2),
    "ym": (1, -1, -2),
    "a": (1, -1, -2),
}

SPEC = KeywordSpec(
    name="mat-null",
    keyword_prefix="*MAT_NULL",
    cards=CARDS,
    dims=DIMS,
)
