from pathlib import Path

from kunit.api import convert_string
from kunit.core.fixed import format_lsdyna_10
from kunit.materials_store import MaterialStore


def _write_material(tmp_path: Path, content: str) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "library.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_tags_parsed_from_comma_separated_string(tmp_path: Path):
    _write_material(
        tmp_path,
        """
[[materials]]
id = "sample"
name = "Sample"
model = "mat-jc"
units = "mm-mg-us"
tags = "alpha, beta , ,gamma "
text = "*MAT_JOHNSON_COOK"
""",
    )

    store = MaterialStore(tmp_path)
    materials = store.list_materials()

    assert len(materials) == 1
    assert materials[0].tags == ["alpha", "beta", "gamma"]


def test_tags_list_is_preserved(tmp_path: Path):
    _write_material(
        tmp_path,
        """
[[materials]]
id = "sample-list"
name = "List"
model = "mat-jc"
units = "mm-mg-us"
tags = ["one", "two", "three"]
text = "*MAT_JOHNSON_COOK"
""",
    )

    store = MaterialStore(tmp_path)
    materials = store.list_materials()

    assert len(materials) == 1
    assert materials[0].tags == ["one", "two", "three"]


def test_multi_block_material_conversion(tmp_path: Path):
    _write_material(
        tmp_path,
        '''
[[materials]]
id = "multi-block"
name = "HE with EOS"
model = "mat-he-burn"
units = "mm-mg-us"
text = """*MAT_HIGH_EXPLOSIVE_BURN
$#     mid        ro         d       pcj      beta         k         g      sigy
        1       1.2       2.0       3.0       0.0       0.0       0.0       4.0
*EOS_JWL
$#   eosid         a         b        r1        r2      omeg        e0        vo
        1      10.0      20.0       1.0       2.0       3.0      60.0       0.5
"""
''',
    )

    store = MaterialStore(tmp_path)
    material = store.list_materials()[0]

    assert material.models == ["mat-he-burn", "eos-jwl"]

    converted = convert_string(
        material.payload,
        src=material.units,
        dst="m-kg-s",
        models=material.models,
    )

    assert format_lsdyna_10(1.2 * 1000) in converted  # density
    assert format_lsdyna_10(3.0 * 1e9) in converted  # pressure in MAT
    assert format_lsdyna_10(10.0 * 1e9) in converted  # pressure in EOS
