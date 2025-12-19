from __future__ import annotations

from kunit.core.engine import FieldTransform, KeywordSpec

CARDS = [
    ["eosid", "a", "b", "xp1", "xp2", "frer", "g", "r1"],
    ["r2", "r3", "r5", "r6", "fmxig", "freq", "grow1", "em"],
    ["ar1", "es1", "cvp", "cvr", "eetal", "ccrit", "enq", "tmp0"],
    ["grow2", "ar2", "es2", "en", "fmxgr", "fmngr", "_", "_"],
]

DIMS = {
    # pressures (e.g., GPa)
    "a": (1, -1, -2),
    "b": (1, -1, -2),
    "r1": (1, -1, -2),
    "r2": (1, -1, -2),
    "cvp": (0, 2, -2),
    "cvr": (0, 2, -2),
    # specific heat (energy per mass)
    "g": (0, 2, -2),
    "r3": (0, 2, -2),
    # rates / frequencies (1/time)
    "freq": (0, 0, -1),
    "grow1": (0, 0, -1),
    "grow2": (0, 0, -1),
}

TRANSFORMS = {
    # 1 / (Pressure^EM * time)
    "grow1": FieldTransform(
        dim=(0, 0, -1),  # base 1/time
        scale_dim=(-1, 1, 2),  # inverse of pressure dim (1,-1,-2)
        scale_power_field="em",
    ),
    # 1 / (Pressure^EN * time)
    "grow2": FieldTransform(
        dim=(0, 0, -1),
        scale_dim=(-1, 1, 2),
        scale_power_field="en",
    ),
}

SPEC = KeywordSpec(
    name="eos-ignition-growth",
    keyword_prefix="*EOS_IGNITION_AND_GROWTH_OF_REACTION_IN_HE",
    cards=CARDS,
    dims=DIMS,
    transforms=TRANSFORMS,
)
