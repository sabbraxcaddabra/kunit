import textwrap
from pathlib import Path

import pytest

from kunit.api import convert_string
from kunit.core.fixed import format_lsdyna_10, join_fixed
from kunit.materials_store import (
    AssignedMaterialIds,
    MaterialStore,
    StructuredMaterialGroupRequest,
    build_materials_export,
    convert_materials,
    export_materials,
    parse_structured_material_group_request,
    render_structured_material_groups,
)


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
name = { ru = "Пример", en = "Sample" }
comment = { ru = "Описание", en = "Description" }
model = "mat-jc"
units = "mm-mg-us"
tags = { ru = "alpha, beta , ,gamma ", en = "one, two" }
text = "*MAT_JOHNSON_COOK"
""",
    )

    store = MaterialStore(tmp_path)
    materials = store.list_materials()

    assert len(materials) == 1
    assert materials[0].tags == ["alpha", "beta", "gamma"]
    assert materials[0].display_tags("en") == ["one", "two"]


def test_tags_list_is_preserved(tmp_path: Path):
    _write_material(
        tmp_path,
        """
[[materials]]
id = "sample-list"
name = { ru = "Список", en = "List" }
comment = { ru = "Описание", en = "Description" }
model = "mat-jc"
units = "mm-mg-us"
tags = { ru = ["one", "two", "three"], en = ["uno", "dos", "tres"] }
text = "*MAT_JOHNSON_COOK"
""",
    )

    store = MaterialStore(tmp_path)
    materials = store.list_materials()

    assert len(materials) == 1
    assert materials[0].tags == ["one", "two", "three"]
    assert materials[0].display_tags("en") == ["uno", "dos", "tres"]


def test_i18n_fields_require_ru_and_en(tmp_path: Path):
    _write_material(
        tmp_path,
        """
[[materials]]
id = "bad"
name = { ru = "Плохой", en = "" }
comment = { ru = "Описание", en = "Description" }
tags = { ru = ["a"], en = ["b"] }
model = "mat-jc"
units = "mm-mg-us"
text = "*MAT_JOHNSON_COOK"
""",
    )

    store = MaterialStore(tmp_path)
    with pytest.raises(ValueError, match="name\\.en"):
        store.list_materials()


def test_legacy_reference_is_converted_to_references(tmp_path: Path):
    _write_material(
        tmp_path,
        """
[[materials]]
id = "legacy-ref"
name = { ru = "Пример", en = "Sample" }
comment = { ru = "Описание", en = "Description" }
model = "mat-jc"
units = "mm-mg-us"
tags = { ru = ["alpha"], en = ["alpha"] }
reference = "https://example.com/ref"
text = "*MAT_JOHNSON_COOK"
""",
    )

    material = MaterialStore(tmp_path).list_materials()[0]

    assert material.reference == "https://example.com/ref"
    assert len(material.references) == 1
    assert material.references[0]["url"] == "https://example.com/ref"
    assert material.references[0]["title"] == {
        "ru": "https://example.com/ref",
        "en": "https://example.com/ref",
    }


def test_references_table_parsed_with_normalization(tmp_path: Path):
    _write_material(
        tmp_path,
        """
[[materials]]
id = "new-ref"
name = { ru = "Пример", en = "Sample" }
comment = { ru = "Описание", en = "Description" }
model = "mat-jc"
units = "mm-mg-us"
tags = { ru = ["alpha"], en = ["alpha"] }
text = "*MAT_JOHNSON_COOK"

[[materials.references]]
title = { ru = "Статья", en = "Paper" }
url = " https://example.com/paper "
kind = "paper"
publisher = " Elsevier "
authors = [" A. Author ", "", "B. Author"]
year = 2020
doi = " 10.1234/abcd "
accessed = "2025-01-31"
note = { ru = " примечание ", en = " note " }

[[materials.references]]
doi = "10.2222/xyz"
""",
    )

    material = MaterialStore(tmp_path).list_materials()[0]

    assert material.reference == "https://example.com/paper"
    assert len(material.references) == 2

    first = material.references[0]
    assert first["title"] == {"ru": "Статья", "en": "Paper"}
    assert first["url"] == "https://example.com/paper"
    assert first["kind"] == "paper"
    assert first["publisher"] == "Elsevier"
    assert first["authors"] == ["A. Author", "B. Author"]
    assert first["year"] == 2020
    assert first["doi"] == "10.1234/abcd"
    assert first["accessed"] == "2025-01-31"
    assert first["note"] == {"ru": "примечание", "en": "note"}

    second = material.references[1]
    assert second["title"] is None
    assert second["url"] is None
    assert second["doi"] == "10.2222/xyz"


def test_references_validation_errors(tmp_path: Path):
    _write_material(
        tmp_path,
        """
[[materials]]
id = "bad-ref"
name = { ru = "Пример", en = "Sample" }
comment = { ru = "Описание", en = "Description" }
model = "mat-jc"
units = "mm-mg-us"
tags = { ru = ["alpha"], en = ["alpha"] }
text = "*MAT_JOHNSON_COOK"

[[materials.references]]
url = "ftp://example.com/ref"
""",
    )

    with pytest.raises(ValueError, match="http/https"):
        MaterialStore(tmp_path).list_materials()

    _write_material(
        tmp_path,
        """
[[materials]]
id = "bad-ref-2"
name = { ru = "Пример", en = "Sample" }
comment = { ru = "Описание", en = "Description" }
model = "mat-jc"
units = "mm-mg-us"
tags = { ru = ["alpha"], en = ["alpha"] }
text = "*MAT_JOHNSON_COOK"

[[materials.references]]
title = { ru = "", en = "" }
""",
    )
    with pytest.raises(ValueError, match="references\\.title\\.ru"):
        MaterialStore(tmp_path).list_materials()

    _write_material(
        tmp_path,
        """
[[materials]]
id = "bad-ref-3"
name = { ru = "Пример", en = "Sample" }
comment = { ru = "Описание", en = "Description" }
model = "mat-jc"
units = "mm-mg-us"
tags = { ru = ["alpha"], en = ["alpha"] }
text = "*MAT_JOHNSON_COOK"

[[materials.references]]
doi = "10.1111/example"
year = 1500
""",
    )
    with pytest.raises(ValueError, match="references\\.year"):
        MaterialStore(tmp_path).list_materials()


def test_multi_block_material_conversion(tmp_path: Path):
    _write_material(
        tmp_path,
        '''
[[materials]]
id = "multi-block"
name = { ru = "HE with EOS", en = "HE with EOS" }
comment = { ru = "Описание", en = "Description" }
model = "mat-he-burn"
units = "mm-mg-us"
tags = { ru = ["he", "eos"], en = ["he", "eos"] }
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
name = { ru = "HMX", en = "HMX" }
comment = { ru = "Описание", en = "Description" }
tags = { ru = ["he"], en = ["he"] }

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
            name = { ru = "Alpha", en = "Alpha" }
            comment = { ru = "Описание", en = "Description" }
            model = "mat-he-burn"
            units = "mm-mg-us"
            tags = { ru = ["x"], en = ["x"] }
            text = """*MAT_HIGH_EXPLOSIVE_BURN
            $#     mid        ro         d       pcj      beta         k         g      sigy
                    10       1.2       2.0       3.0       0.0       0.0       0.0       4.0
            *EOS_JWL
            $#   eosid         a         b        r1        r2      omeg        e0        vo
                    10      10.0      20.0       1.0       2.0       3.0      60.0       0.5
            """

            [[materials]]
            id = "beta"
            name = { ru = "Beta", en = "Beta" }
            comment = { ru = "Описание", en = "Description" }
            model = "mat-he-burn"
            units = "mm-mg-us"
            tags = { ru = ["y"], en = ["y"] }
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
            name = { ru = "Gamma", en = "Gamma" }
            comment = { ru = "Описание", en = "Description" }
            tags = { ru = ["z"], en = ["z"] }

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
            name = { ru = "Delta", en = "Delta" }
            comment = { ru = "Описание", en = "Description" }
            tags = { ru = ["d"], en = ["d"] }

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
            name = {{ ru = "First", en = "First" }}
            comment = {{ ru = "Описание", en = "Description" }}
            model = "mat-he-burn"
            units = "mm-mg-us"
            tags = {{ ru = ["x"], en = ["x"] }}
            text = """*MAT_HIGH_EXPLOSIVE_BURN
            $#     mid        ro         d       pcj      beta         k         g      sigy
            {_fixed_line([22, 1.891, 0.911, 0.42, 0.0, 0.0, 0.0, 0.0])}
            *EOS_JWL
            $#   eosid         a         b        r1        r2      omeg        e0        vo
            {_fixed_line([23, 7.783, 0.07871, 4.2, 4.0, 0.3, 1.0, 1.05])}
            """

            [[materials]]
            id = "second"
            name = {{ ru = "Second", en = "Second" }}
            comment = {{ ru = "Описание", en = "Description" }}
            model = "mat-he-burn"
            units = "mm-mg-us"
            tags = {{ ru = ["y"], en = ["y"] }}
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


def test_build_materials_export_returns_assigned_mid_and_eosid_map(tmp_path: Path):
    _write_material(
        tmp_path,
        textwrap.dedent(
            '''
            [[materials]]
            id = "with-eos"
            name = { ru = "With EOS", en = "With EOS" }
            comment = { ru = "Описание", en = "Description" }
            tags = { ru = ["he"], en = ["he"] }

            [materials.material]
            model = "mat-he-burn"
            units = "mm-mg-us"
            payload = """*MAT_HIGH_EXPLOSIVE_BURN
            $#     mid        ro         d       pcj      beta         k         g      sigy
                    8       1.2       2.0       3.0       0.0       0.0       0.0       4.0
            """

            [materials.eos]
            model = "eos-jwl"
            units = "mm-mg-us"
            payload = """*EOS_JWL
            $#   eosid         a         b        r1        r2      omeg        e0        vo
                   18      10.0      20.0       1.0       2.0       3.0      60.0       0.5
            """

            [[materials]]
            id = "without-eos"
            name = { ru = "No EOS", en = "No EOS" }
            comment = { ru = "Описание", en = "Description" }
            model = "mat-jc"
            units = "mm-mg-us"
            tags = { ru = ["solid"], en = ["solid"] }
            text = """*MAT_JOHNSON_COOK
            $#     mid        ro         a         b         n         c         m    tmelt
                   77       7.8     500.0      10.0       0.2      0.01       1.0     800.0
            """
            '''
        ),
    )

    materials = MaterialStore(tmp_path).list_materials()

    export = build_materials_export(materials, "mm-mg-us")

    assert export.assigned_ids["with-eos"].mid == 1
    assert export.assigned_ids["with-eos"].eosid == 1
    assert export.assigned_ids["without-eos"].mid == 2
    assert export.assigned_ids["without-eos"].eosid == 0
    assert export.payload.count("*MAT_") == 2


@pytest.mark.parametrize("block_type", ["3D", "AXISYM", "PLNEPS"])
def test_parse_structured_material_group_request_accepts_supported_block_types(block_type):
    request = parse_structured_material_group_request(
        {
            "blocks": [
                {
                    "type": block_type,
                    "rows": [
                        {
                            "ammgnm": "HE1",
                            "material_id": "mat-1",
                            "pref": "1.25",
                        }
                    ],
                }
            ]
        },
        allowed_material_ids={"mat-1"},
    )

    assert isinstance(request, StructuredMaterialGroupRequest)
    assert [block.block_type for block in request.blocks] == [block_type]
    assert request.blocks[0].rows[0].material_id == "mat-1"
    assert request.blocks[0].rows[0].pref == "1.25"


def test_parse_structured_material_group_request_allows_long_material_ids():
    request = parse_structured_material_group_request(
        {
            "blocks": [
                {
                    "type": "3D",
                    "rows": [
                        {
                            "ammgnm": "AL",
                            "material_id": "al-2024(jc)",
                            "pref": "",
                        }
                    ],
                }
            ]
        },
        allowed_material_ids={"al-2024(jc)"},
    )

    assert request.blocks[0].rows[0].material_id == "al-2024(jc)"


def test_parse_structured_material_group_request_rejects_multiple_blocks():
    with pytest.raises(ValueError, match="single block"):
        parse_structured_material_group_request(
            {
                "blocks": [
                    {"type": "3D", "rows": [{"ammgnm": "A", "material_id": "mat-1"}]},
                    {"type": "AXISYM", "rows": [{"ammgnm": "B", "material_id": "mat-1"}]},
                ]
            },
            allowed_material_ids={"mat-1"},
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"blocks": [{"type": "3D", "rows": [{"ammgnm": "", "material_id": "mat-1"}]}]},
            "ammgnm",
        ),
        (
            {"blocks": [{"type": "BAD", "rows": [{"ammgnm": "HE1", "material_id": "mat-1"}]}]},
            "AXISYM",
        ),
        (
            {"blocks": [{"type": "3D", "rows": [{"ammgnm": "HE1", "material_id": ""}]}]},
            "material_id",
        ),
        (
            {"blocks": [{"type": "3D", "rows": [{"ammgnm": "HE1", "material_id": "mat-1", "pref": "12345678901"}]}]},
            "pref",
        ),
        (
            {"blocks": [{"type": "3D", "rows": [{"ammgnm": "ABCDEFGHIJK", "material_id": "mat-1"}]}]},
            "10 characters",
        ),
        (
            {"blocks": [{"type": "3D", "rows": [{"ammgnm": "HE1", "material_id": "mat-9"}]}]},
            "selected material",
        ),
    ],
)
def test_parse_structured_material_group_request_validates_input(payload, message):
    with pytest.raises(ValueError, match=message):
        parse_structured_material_group_request(payload, allowed_material_ids={"mat-1"})


def test_render_structured_material_groups_renders_3d_without_suffix_and_defaults_pref():
    request = parse_structured_material_group_request(
        {
            "blocks": [
                {
                    "type": "3D",
                    "rows": [
                        {"ammgnm": "VAC", "material_id": "mat-1", "pref": ""},
                        {"ammgnm": "HE", "material_id": "mat-2", "pref": "1.5"},
                    ],
                }
            ]
        },
        allowed_material_ids={"mat-1", "mat-2"},
    )

    rendered = render_structured_material_groups(
        request,
        {
            "mat-1": AssignedMaterialIds(mid=1, eosid=0),
            "mat-2": AssignedMaterialIds(mid=2, eosid=2),
        },
    )

    assert rendered.startswith("*ALE_STRUCTURED_MULTI-MATERIAL_GROUP\n")
    assert "*ALE_STRUCTURED_MULTI-MATERIAL_GROUP_3D" not in rendered
    assert rendered.count("$#  ammgnm") == 1
    lines = rendered.splitlines()
    assert lines[2] == join_fixed(["VAC", "1", "0", "", "", "", "", "0.0"]).rstrip()
    assert lines[3] == join_fixed(["HE", "2", "2", "", "", "", "", "1.5"]).rstrip()
