import pytest

from kunit.api import convert_string
from kunit.core.fixed import split_fixed, join_fixed
from kunit.core.units import BASE_SYSTEMS, scale_factor


def _fields(line: str) -> list[str]:
    return [f.strip() for f in split_fixed(line)]


def test_ignition_growth_unit_scaling_from_reference_card():
    raw_cards = [
        join_fixed(["10", "5.242", "0.07678", "4.2", "1.1", "0.667", "3.4E-6", "780"]),
        join_fixed(["-0.05031", "2.22E-5", "11.3", "1.13", "0.022", "4E6", "850", "2"]),
        join_fixed(["0.667", "0.222", "1E-5", "2.49E-5", "7", "0", "0.085", "298"]),
        join_fixed(["660", "1", "0.333", "3", "0.6", "0", "", ""]),
    ]
    text = "".join(["*EOS_IGNITION_AND_GROWTH_OF_REACTION_IN_HE\n", *raw_cards])

    src = BASE_SYSTEMS["mm-mg-us"]
    dst = BASE_SYSTEMS["m-kg-s"]
    pressure_scale = scale_factor(src, dst, (1, -1, -2))
    specific_heat_scale = scale_factor(src, dst, (0, 2, -2))
    time_scale = scale_factor(src, dst, (0, 0, -1))

    converted = convert_string(
        text, src="mm-mg-us", dst="m-kg-s", models="eos-ignition-growth"
    )
    lines = converted.splitlines()

    card1 = _fields(lines[1])
    assert float(card1[1]) == pytest.approx(5.242 * pressure_scale)  # A (pressure)
    assert float(card1[2]) == pytest.approx(0.07678 * pressure_scale)  # B (pressure)
    assert float(card1[6]) == pytest.approx(3.4e-6 * specific_heat_scale)  # G (cv)
    assert float(card1[7]) == pytest.approx(780 * pressure_scale)  # R1 (pressure)

    card2 = _fields(lines[2])
    assert float(card2[0]) == pytest.approx(-0.05031 * pressure_scale)  # R2 (pressure)
    assert float(card2[1]) == pytest.approx(2.22e-5 * specific_heat_scale)  # R3 (cv)
    assert float(card2[4]) == pytest.approx(0.022 * pressure_scale)  # FMXIG (pressure)
    assert float(card2[5]) == pytest.approx(4.0e6 * time_scale)  # FREQ (1/time)

    grow1_pressure_scale = pressure_scale ** 0.222
    assert float(card2[6]) == pytest.approx(
        850 * time_scale * grow1_pressure_scale, rel=1e-5
    )

    card3 = _fields(lines[3])
    assert float(card3[2]) == pytest.approx(1e-5 * pressure_scale)  # CVP (pressure)
    assert float(card3[3]) == pytest.approx(2.49e-5 * pressure_scale)  # CVR (pressure)

    card4 = _fields(lines[4])
    grow2_pressure_scale = pressure_scale ** 0.333
    assert float(card4[0]) == pytest.approx(
        660 * time_scale * grow2_pressure_scale, rel=1e-5
    )
    assert float(card4[4]) == pytest.approx(0.6 * time_scale)  # FMXGR (1/time)
