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
    "fmxig": (1, -1, -2),
    "cvp": (1, -1, -2),
    "cvr": (1, -1, -2),
    # specific heat (energy per mass)
    "g": (0, 2, -2),
    "r3": (0, 2, -2),
    # rates / frequencies (1/time)
    "freq": (0, 0, -1),
    "grow1": (0, 0, -1),
    "grow2": (0, 0, -1),
    "fmxgr": (0, 0, -1),
    "fmngr": (0, 0, -1),
    # remaining fields are dimensionless
}

TRANSFORMS = {
    # Pressure^ES1 / time
    "grow1": FieldTransform(
        dim=(0, 0, -1), scale_dim=(1, -1, -2), scale_power_field="es1"
    ),
    # Pressure^ES2 / time
    "grow2": FieldTransform(
        dim=(0, 0, -1), scale_dim=(1, -1, -2), scale_power_field="es2"
    ),
}

SPEC = KeywordSpec(
    name="eos-ignition-growth",
    keyword_prefix="*EOS_IGNITION_AND_GROWTH_OF_REACTION_IN_HE",
    cards=CARDS,
    dims=DIMS,
    transforms=TRANSFORMS,
)
