from pathlib import Path
import textwrap

from pytest import approx

from kunit.api import convert_string
from kunit.core.fixed import format_lsdyna_10, join_fixed
from kunit.materials_store import MaterialStore


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


def test_material_with_material_and_eos_sections(tmp_path: Path):
    mat_payload = """*MAT_JOHNSON_COOK
$ mid     ro        g         e         pr        dtf      vp        rateop
""" + "".join(
        [
            _fixed_line([1, 1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 0.0]),
            _fixed_line([0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            _fixed_line([0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            _fixed_line([0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        ]
    )

    eos_payload = """*EOS_JWL
$#   eosid         a         b        r1        r2      omeg        e0        vo
""" + _fixed_line([1, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])

    _write_material(
        tmp_path,
        textwrap.dedent(
            f'''
[[materials]]
id = "combo"
name = "Combo"

[materials.material]
model = "mat-jc"
units = "mm-mg-us"
payload = """{mat_payload}"""

[materials.eos]
model = "eos-jwl"
units = "mm-mg-us"
payload = """{eos_payload}"""
'''
        ),
    )

    store = MaterialStore(tmp_path)
    materials = store.list_materials()

    assert len(materials) == 1
    record = materials[0]
    assert record.model == "mat-jc"
    assert record.eos is not None
    assert record.eos.model == "eos-jwl"

    combined = record.to_k()
    assert combined.index("*MAT_JOHNSON_COOK") < combined.index("*EOS_JWL")
    assert "*EOS_JWL" in combined
    assert record.to_k() == record.to_k().rstrip("\n") + "\n"


def test_material_sections_converted_to_requested_units(tmp_path: Path):
    mat_payload = """*MAT_JOHNSON_COOK
$ mid     ro        g         e         pr        dtf      vp        rateop
""" + "".join(
        [
            _fixed_line([1, 1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 0.0]),
            _fixed_line([0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            _fixed_line([0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            _fixed_line([0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        ]
    )

    eos_payload = """*EOS_JWL
$#   eosid         a         b        r1        r2      omeg        e0        vo
""" + _fixed_line([1, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])

    _write_material(
        tmp_path,
        textwrap.dedent(
            f'''
[[materials]]
id = "combo"
name = "Combo"

[materials.material]
model = "mat-jc"
units = "mm-mg-us"
payload = """{mat_payload}"""

[materials.eos]
model = "eos-jwl"
units = "mm-mg-us"
payload = """{eos_payload}"""
'''
        ),
    )

    record = MaterialStore(tmp_path).list_materials()[0]

    converted = []
    for section in record.sections:
        converted.append(
            convert_string(
                section.payload,
                src=section.units,
                dst="m-kg-s",
                models=[section.model],
            )
        )

    mat_tokens = converted[0].splitlines()[2].split()
    assert float(mat_tokens[1]) == approx(1000)
    assert float(mat_tokens[2]) == approx(2e9)

    eos_tokens = converted[1].splitlines()[2].split()
    assert float(eos_tokens[1]) == approx(2e9)
    assert float(eos_tokens[2]) == approx(3e9)
