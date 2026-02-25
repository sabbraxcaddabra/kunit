from __future__ import annotations

from kunit.core.engine import KeywordSpec

# MAT_010 / *MAT_ELASTIC_PLASTIC_HYDRO (base variant)
CARDS = [
    ["mid", "ro", "g", "sig0", "eh", "pc", "fs", "charl"],
    ["eps1", "eps2", "eps3", "eps4", "eps5", "eps6", "eps7", "eps8"],
    ["eps9", "eps10", "eps11", "eps12", "eps13", "eps14", "eps15", "eps16"],
    ["es1", "es2", "es3", "es4", "es5", "es6", "es7", "es8"],
    ["es9", "es10", "es11", "es12", "es13", "es14", "es15", "es16"],
]

DIMS = {
    "ro": (1, -3, 0),
    "g": (1, -1, -2),
    "sig0": (1, -1, -2),
    "eh": (1, -1, -2),
    "pc": (1, -1, -2),
    "charl": (0, 1, 0),
    "es1": (1, -1, -2),
    "es2": (1, -1, -2),
    "es3": (1, -1, -2),
    "es4": (1, -1, -2),
    "es5": (1, -1, -2),
    "es6": (1, -1, -2),
    "es7": (1, -1, -2),
    "es8": (1, -1, -2),
    "es9": (1, -1, -2),
    "es10": (1, -1, -2),
    "es11": (1, -1, -2),
    "es12": (1, -1, -2),
    "es13": (1, -1, -2),
    "es14": (1, -1, -2),
    "es15": (1, -1, -2),
    "es16": (1, -1, -2),
    # fs, eps*, mid are dimensionless/IDs => not converted
}

SPEC = KeywordSpec(
    name="mat-elastic-plastic-hydro",
    keyword_prefix="*MAT_ELASTIC_PLASTIC_HYDRO",
    cards=CARDS,
    dims=DIMS,
)
