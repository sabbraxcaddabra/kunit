import textwrap
from pathlib import Path

from kunit.api import convert_string
from kunit.core.fixed import format_lsdyna_10, join_fixed
from kunit.materials_store import MaterialStore, convert_materials, export_materials


def _write_material(tmp_path: Path, content: str) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "library.toml"
    path.write_text(content, encoding="utf-8")
    return path


def _fixed_line(values):
    return join_fixed([format_lsdyna_10(v) for v in values])


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


def test_multi_section_material_conversion(tmp_path: Path):
    _write_material(
        tmp_path,
        '''
[[materials]]
id = "hmx"
name = "HMX"

[materials.material]
model = "mat-he-burn"
units = "mm-mg-us"
payload = """*MAT_HIGH_EXPLOSIVE_BURN_TITLE
hmx
$#     mid        ro         d       pcj      beta         k         g      sigy
        22     1.891      9.11      42.0       0.0       0.0       0.0       0.0
"""

[materials.eos]
model = "eos-jwl"
units = "mm-mg-us"
payload = """*EOS_JWL_TITLE
hmx
$#   eosid         a         b        r1        r2      omeg        e0        vo
        22     778.3     7.071       4.2       1.0       0.3      10.5       0.0
"""
''',
    )

    store = MaterialStore(tmp_path)
    material = store.list_materials()[0]

    assert material.models == ["mat-he-burn", "eos-jwl"]

    converted = convert_string(
        material.to_k(),
        src=material.units,
        dst="m-kg-s",
        models=material.models,
    )

    assert "*MAT_HIGH_EXPLOSIVE_BURN_TITLE" in converted
    assert "*EOS_JWL_TITLE" in converted
    assert format_lsdyna_10(42.0 * 1e9) in converted  # pressure in MAT
    assert format_lsdyna_10(778.3 * 1e9) in converted  # pressure in EOS


def test_export_materials_rewrites_identifiers(tmp_path: Path):
    _write_material(
        tmp_path,
        textwrap.dedent(
            '''
            [[materials]]
            id = "alpha"
            name = "Alpha"
            model = "mat-he-burn"
            units = "mm-mg-us"
            text = """*MAT_HIGH_EXPLOSIVE_BURN
            $#     mid        ro         d       pcj      beta         k         g      sigy
                    10       1.2       2.0       3.0       0.0       0.0       0.0       4.0
            *EOS_JWL
            $#   eosid         a         b        r1        r2      omeg        e0        vo
                    10      10.0      20.0       1.0       2.0       3.0      60.0       0.5
            """

            [[materials]]
            id = "beta"
            name = "Beta"
            model = "mat-he-burn"
            units = "mm-mg-us"
            text = """*MAT_HIGH_EXPLOSIVE_BURN
            $#     mid        ro         d       pcj      beta         k         g      sigy
                    10       1.5       2.5       3.5       0.0       0.0       0.0       4.5
            *EOS_JWL
            $#   eosid         a         b        r1        r2      omeg        e0        vo
                    10      11.0      21.0       1.5       2.5       3.5      61.0       0.8
            """
            '''
        ),
    )

    store = MaterialStore(tmp_path)
    materials = store.list_materials()

    exported = export_materials(materials)
    lines = exported.splitlines()

    mat1 = lines.index("*MAT_HIGH_EXPLOSIVE_BURN")
    mat2 = lines.index("*MAT_HIGH_EXPLOSIVE_BURN", mat1 + 1)

    assert lines[mat1 + 2][:10].strip() == "1"
    assert lines[mat2 + 2][:10].strip() == "2"
    assert "*EOS_JWL" in lines[mat1 + 3]
    assert lines[mat1 + 5][:10].strip() == "1"
    assert "*EOS_JWL" in lines[mat2 + 3]
    assert lines[mat2 + 5][:10].strip() == "2"


def test_export_materials_enforces_shared_auto_increment_ids(tmp_path: Path):
    _write_material(
        tmp_path,
        textwrap.dedent(
            '''
            [[materials]]
            id = "gamma"
            name = "Gamma"

            [materials.material]
            model = "mat-he-burn"
            units = "mm-mg-us"
            payload = """*MAT_HIGH_EXPLOSIVE_BURN
            $#     mid        ro         d       pcj      beta         k         g      sigy
                    7       1.2       2.0       3.0       0.0       0.0       0.0       4.0
            """

            [materials.eos]
            model = "eos-jwl"
            units = "mm-mg-us"
            payload = """*EOS_JWL
            $#   eosid         a         b        r1        r2      omeg        e0        vo
                   42      10.0      20.0       1.0       2.0       3.0      60.0       0.5
            """

            [[materials]]
            id = "delta"
            name = "Delta"

            [materials.material]
            model = "mat-he-burn"
            units = "mm-mg-us"
            payload = """*MAT_HIGH_EXPLOSIVE_BURN
            $#     mid        ro         d       pcj      beta         k         g      sigy
                   99       1.5       2.5       3.5       0.0       0.0       0.0       4.5
            """

            [materials.eos]
            model = "eos-jwl"
            units = "mm-mg-us"
            payload = """*EOS_JWL
            $#   eosid         a         b        r1        r2      omeg        e0        vo
                    5      11.0      21.0       1.5       2.5       3.5      61.0       0.8
            """
            '''
        ),
    )

    store = MaterialStore(tmp_path)
    materials = store.list_materials()

    exported = export_materials(materials)
    lines = exported.splitlines()

    first_mat_idx = lines.index("*MAT_HIGH_EXPLOSIVE_BURN")
    second_mat_idx = lines.index("*MAT_HIGH_EXPLOSIVE_BURN", first_mat_idx + 1)

    assert lines[first_mat_idx + 2][:10].strip() == "1"
    first_eos_idx = lines.index("*EOS_JWL", first_mat_idx + 1)
    assert lines[first_eos_idx + 2][:10].strip() == "1"

    assert lines[second_mat_idx + 2][:10].strip() == "2"
    second_eos_idx = lines.index("*EOS_JWL", second_mat_idx + 1)
    assert lines[second_eos_idx + 2][:10].strip() == "2"


def test_convert_materials_rewrites_identifiers(tmp_path: Path):
    _write_material(
        tmp_path,
        textwrap.dedent(
            f'''
            [[materials]]
            id = "first"
            name = "First"
            model = "mat-he-burn"
            units = "mm-mg-us"
            text = """*MAT_HIGH_EXPLOSIVE_BURN
            $#     mid        ro         d       pcj      beta         k         g      sigy
            {_fixed_line([22, 1.891, 0.911, 0.42, 0.0, 0.0, 0.0, 0.0])}
            *EOS_JWL
            $#   eosid         a         b        r1        r2      omeg        e0        vo
            {_fixed_line([23, 7.783, 0.07871, 4.2, 4.0, 0.3, 1.0, 1.05])}
            """

            [[materials]]
            id = "second"
            name = "Second"
            model = "mat-he-burn"
            units = "mm-mg-us"
            text = """*MAT_HIGH_EXPLOSIVE_BURN
            $#     mid        ro         d       pcj      beta         k         g      sigy
            {_fixed_line([105, 2.0, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0])}
            *EOS_JWL
            $#   eosid         a         b        r1        r2      omeg        e0        vo
            {_fixed_line([205, 8.0, 0.07, 4.5, 4.4, 0.31, 1.4, 1.1])}
            """
            '''
        ),
    )

    store = MaterialStore(tmp_path)
    materials = store.list_materials()

    converted = convert_materials(materials, "cm-g-us")
    lines = converted.splitlines()

    first_mat_idx = lines.index("*MAT_HIGH_EXPLOSIVE_BURN")
    second_mat_idx = lines.index("*MAT_HIGH_EXPLOSIVE_BURN", first_mat_idx + 1)

    assert lines[first_mat_idx + 2][:10].strip() == "1"
    first_eos_idx = lines.index("*EOS_JWL", first_mat_idx + 1)
    assert lines[first_eos_idx + 2][:10].strip() == "1"

    assert lines[second_mat_idx + 2][:10].strip() == "2"
    second_eos_idx = lines.index("*EOS_JWL", second_mat_idx + 1)
    assert lines[second_eos_idx + 2][:10].strip() == "2"
