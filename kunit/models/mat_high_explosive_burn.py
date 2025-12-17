from __future__ import annotations

from kunit.core.engine import KeywordSpec

CARDS = [
    # mid ro d pcj beta k g sigy
    ["mid", "ro", "d", "pcj", "beta", "k", "g", "sigy"],
]

DIMS = {
    "ro": (1, -3, 0),  # density
    "d": (0, 1, -1),  # detonation velocity L/T
    "pcj": (1, -1, -2),  # pressure
    "sigy": (1, -1, -2),  # yield stress => pressure (если у вас иначе — скажи)
    # beta,k,g are typically dimensionless or model-specific => not converted
}

SPEC = KeywordSpec(
    name="mat-he-burn",
    keyword_prefix="*MAT_HIGH_EXPLOSIVE_BURN",
    cards=CARDS,
    dims=DIMS,
)
