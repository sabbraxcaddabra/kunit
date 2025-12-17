from __future__ import annotations

from kunit.core.engine import KeywordSpec

# MAT_015
CARDS = [
    ["mid", "ro", "g", "e", "pr", "dtf", "vp", "rateop"],
    ["a", "b", "n", "c", "m", "tm", "tr", "epso"],
    ["cp", "pc", "spall", "it", "d1", "d2", "d3", "d4"],
    ["d5", "c2/p/xnp", "erod", "efmin", "numint", "_", "_", "dmodel"],
]

DIMS = {
    "ro": (1, -3, 0),
    "g": (1, -1, -2),
    "e": (1, -1, -2),
    "a": (1, -1, -2),
    "b": (1, -1, -2),
    "pc": (1, -1, -2),
    "cp": (0, 2, -2),  # energy/volume per K effectively; K unchanged
    "epso": (0, 0, -1),
    # all others omitted => not converted
}

SPEC = KeywordSpec(
    name="mat-jc",
    keyword_prefix="*MAT_JOHNSON_COOK",
    cards=CARDS,
    dims=DIMS,
)
