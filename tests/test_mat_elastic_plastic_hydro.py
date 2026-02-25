import pytest

from kunit.api import convert_string, list_models
from kunit.core.fixed import join_fixed, split_fixed
from kunit.core.units import BASE_SYSTEMS, scale_factor
from kunit.models.mat_elastic_plastic_hydro import DIMS


def _fields(line: str) -> list[str]:
    return [f.strip() for f in split_fixed(line)]


def test_mat_elastic_plastic_hydro_conversion_scales_only_dimensional_fields():
    text = "".join(
        [
            "*MAT_ELASTIC_PLASTIC_HYDRO_TITLE\n",
            join_fixed(["10", "8.96", "46.0", "0.09", "0.01", "0.4", "0.25", "2.5"]),
            join_fixed(["0.0", "0.01", "0.02", "0.03", "0.04", "0.05", "0.06", "0.07"]),
            join_fixed(["0.08", "0.09", "0.10", "0.11", "0.12", "0.13", "0.14", "0.15"]),
            join_fixed(["0.09", "0.10", "0.11", "0.12", "0.13", "0.14", "0.15", "0.16"]),
            join_fixed(["0.17", "0.18", "0.19", "0.20", "0.21", "0.22", "0.23", "0.24"]),
        ]
    )

    src = BASE_SYSTEMS["mm-mg-us"]
    dst = BASE_SYSTEMS["m-kg-s"]

    density_scale = scale_factor(src, dst, DIMS["ro"])
    pressure_scale = scale_factor(src, dst, DIMS["g"])
    length_scale = scale_factor(src, dst, DIMS["charl"])

    converted = convert_string(
        text, src="mm-mg-us", dst="m-kg-s", models="mat-elastic-plastic-hydro"
    )
    lines = converted.splitlines()

    card1 = _fields(lines[1])
    assert float(card1[1]) == pytest.approx(8.96 * density_scale)
    assert float(card1[2]) == pytest.approx(46.0 * pressure_scale)
    assert float(card1[3]) == pytest.approx(0.09 * pressure_scale)
    assert float(card1[4]) == pytest.approx(0.01 * pressure_scale)
    assert float(card1[5]) == pytest.approx(0.4 * pressure_scale)
    assert float(card1[6]) == pytest.approx(0.25)
    assert float(card1[7]) == pytest.approx(2.5 * length_scale)

    card3 = _fields(lines[3])
    assert float(card3[0]) == pytest.approx(0.08)
    assert float(card3[7]) == pytest.approx(0.15)

    card5 = _fields(lines[5])
    assert float(card5[0]) == pytest.approx(0.17 * pressure_scale)
    assert float(card5[7]) == pytest.approx(0.24 * pressure_scale)


def test_mat_elastic_plastic_hydro_is_listed():
    assert "mat-elastic-plastic-hydro" in list_models()
