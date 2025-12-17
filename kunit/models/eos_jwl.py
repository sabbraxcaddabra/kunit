from __future__ import annotations

from kunit.core.engine import KeywordSpec

CARDS = [
    # eosid a b r1 r2 omeg e0 vo
    ["eosid", "a", "b", "r1", "r2", "omeg", "e0", "vo"],
]

DIMS = {
    "a": (1, -1, -2),  # pressure
    "b": (1, -1, -2),  # pressure
    "e0": (1, -1, -2),  # energy per volume => pressure
    # vo is relative volume => dimensionless => not converted
    # r1,r2,omeg => not converted
}

SPEC = KeywordSpec(
    name="eos-jwl",
    keyword_prefix="*EOS_JWL",
    cards=CARDS,
    dims=DIMS,
)
