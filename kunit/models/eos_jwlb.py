from __future__ import annotations

from kunit.core.engine import KeywordSpec

CARDS = [
    # eosid a1 a2 a3 a4 a5
    ["eosid", "a1", "a2", "a3", "a4", "a5", "_", "_"],
    # r1 r2 r3 r4 r5
    ["r1", "r2", "r3", "r4", "r5", "_", "_", "_"],
    # al1 al2 al3 al4 al5
    ["al1", "al2", "al3", "al4", "al5", "_", "_", "_"],
    # bl1 bl2 bl3 bl4 bl5
    ["bl1", "bl2", "bl3", "bl4", "bl5", "_", "_", "_"],
    # rl1 rl2 rl3 rl4 rl5
    ["rl1", "rl2", "rl3", "rl4", "rl5", "_", "_", "_"],
    # c omega e v0
    ["c", "omega", "e", "v0", "_", "_", "_", "_"],
]

DIMS = {
    "a1": (1, -1, -2),  # pressure
    "a2": (1, -1, -2),  # pressure
    "a3": (1, -1, -2),  # pressure
    "a4": (1, -1, -2),  # pressure
    "a5": (1, -1, -2),  # pressure
    "c": (1, -1, -2),  # pressure term
    "e": (1, -1, -2),  # energy per volume => pressure
    # r*, al*, rl*, v0, omega => dimensionless
}

SPEC = KeywordSpec(
    name="eos-jwlb",
    keyword_prefix="*EOS_JWLB",
    cards=CARDS,
    dims=DIMS,
)
