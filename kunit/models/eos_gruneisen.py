from __future__ import annotations

from kunit.core.engine import KeywordSpec

CARDS = [
    # eosid c s1 s2 s3 gamma0 a e0
    ["eosid", "c", "s1", "s2", "s3", "gamma0", "a", "e0"],
    # v0 - lcid  (вторая колонка пустая)
    ["v0", "_", "lcid", "_", "_", "_", "_", "_"],
]

DIMS = {
    "c": (0, 1, -1),  # velocity L/T
    "e0": (1, -1, -2),  # energy per volume => pressure
    # v0 is relative volume => dimensionless => not converted
    # s1,s2,s3,gamma0,a,lcid => not converted
}

SPEC = KeywordSpec(
    name="eos-gruneisen",
    keyword_prefix="*EOS_GRUNEISEN",
    cards=CARDS,
    dims=DIMS,
)
