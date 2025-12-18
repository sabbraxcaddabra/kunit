from __future__ import annotations

from kunit.api import convert_string, list_models
from kunit.cli import convert_cmd
from kunit.core.fixed import format_lsdyna_10, join_fixed
from kunit.core.units import BASE_SYSTEMS, scale_factor


def _sample_jwlb_card() -> str:
    lines = [
        "*EOS_JWLB\n",
        join_fixed(["4", "490.07", "56.868", "0.82426", "0.00093", "0.0", "", ""]),
        join_fixed(["40.713", "9.6754", "2.435", "0.1556", "0.0", "", "", ""]),
        join_fixed(["0.0", "11.468", "0.0", "0.0", "0.0", "", "", ""]),
        join_fixed(["1098.0", "-6.5011", "0.0", "0.0", "0.0", "", "", ""]),
        join_fixed(["15.614", "2.1593", "0.0", "0.0", "0.0", "", "", ""]),
        join_fixed(["0.071", "0.30270", "0.06656", "0.613127", "", "", "", ""]),
    ]
    return "".join(lines)


def test_eos_jwlb_pressure_scaling() -> None:
    text = _sample_jwlb_card()
    src = "cm-g-us"
    dst = "m-kg-s"

    converted = convert_string(text, src=src, dst=dst, models="eos-jwlb")

    pressure_sf = scale_factor(BASE_SYSTEMS[src], BASE_SYSTEMS[dst], (1, -1, -2))
    expected = "".join(
        [
            "*EOS_JWLB\n",
            join_fixed(
                [
                    "4",
                    format_lsdyna_10(490.07 * pressure_sf),
                    format_lsdyna_10(56.868 * pressure_sf),
                    format_lsdyna_10(0.82426 * pressure_sf),
                    format_lsdyna_10(0.00093 * pressure_sf),
                    format_lsdyna_10(0.0 * pressure_sf),
                    "",
                    "",
                ]
            ),
            join_fixed(
                [
                    format_lsdyna_10(40.713),
                    format_lsdyna_10(9.6754),
                    format_lsdyna_10(2.435),
                    format_lsdyna_10(0.1556),
                    format_lsdyna_10(0.0),
                    "",
                    "",
                    "",
                ]
            ),
            join_fixed(
                [
                    format_lsdyna_10(0.0),
                    format_lsdyna_10(11.468),
                    format_lsdyna_10(0.0),
                    format_lsdyna_10(0.0),
                    format_lsdyna_10(0.0),
                    "",
                    "",
                    "",
                ]
            ),
            join_fixed(
                [
                    format_lsdyna_10(1098.0),
                    format_lsdyna_10(-6.5011),
                    format_lsdyna_10(0.0),
                    format_lsdyna_10(0.0),
                    format_lsdyna_10(0.0),
                    "",
                    "",
                    "",
                ]
            ),
            join_fixed(
                [
                    format_lsdyna_10(15.614),
                    format_lsdyna_10(2.1593),
                    format_lsdyna_10(0.0),
                    format_lsdyna_10(0.0),
                    format_lsdyna_10(0.0),
                    "",
                    "",
                    "",
                ]
            ),
            join_fixed(
                [
                    format_lsdyna_10(0.071 * pressure_sf),
                    format_lsdyna_10(0.30270),
                    format_lsdyna_10(0.06656 * pressure_sf),
                    format_lsdyna_10(0.613127),
                    "",
                    "",
                    "",
                    "",
                ]
            ),
        ]
    )

    assert converted == expected


def test_eos_jwlb_is_listed_and_documented() -> None:
    assert "eos-jwlb" in list_models()

    model_options = [
        opt for opt in convert_cmd.params if getattr(opt, "name", None) == "models"
    ]
    assert any("eos-jwlb" in opt.help for opt in model_options)
