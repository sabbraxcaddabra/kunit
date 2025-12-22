from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class BaseUnits:
    length_si: float  # meters per 1 length unit
    mass_si: float  # kg per 1 mass unit
    time_si: float  # s per 1 time unit


BASE_SYSTEMS: Dict[str, BaseUnits] = {
    "mm-mg-us": BaseUnits(1e-3, 1e-6, 1e-6),
    "cm-g-us": BaseUnits(1e-2, 1e-3, 1e-6),
    "m-kg-s": BaseUnits(1.0, 1.0, 1.0),
    "mm-mg-ms": BaseUnits(1e-3, 1e-6, 1e-3),
}

DIM = Tuple[int, int, int]  # (a,b,c) for M^a L^b T^c


def scale_factor(src: BaseUnits, dst: BaseUnits, dim: DIM) -> float:
    a, b, c = dim
    return (
        (src.mass_si / dst.mass_si) ** a
        * (src.length_si / dst.length_si) ** b
        * (src.time_si / dst.time_si) ** c
    )


@dataclass(frozen=True)
class UnitDescriptor:
    key: str
    label: str
    pressure_unit: str


_LABEL_PARTS = {
    "mm": "мм",
    "cm": "см",
    "m": "м",
    "mg": "мг",
    "g": "г",
    "kg": "кг",
    "us": "мкс",
    "ms": "мс",
    "s": "с",
}


def _pressure_label(src: BaseUnits) -> str:
    """Return a human-friendly pressure unit for the given base system."""

    pa_factor = scale_factor(src, BASE_SYSTEMS["m-kg-s"], (1, -1, -2))
    if pa_factor >= 5e10:
        return "Мбар"
    if pa_factor >= 1e9:
        return "ГПа"
    if pa_factor >= 1e6:
        return "МПа"
    if pa_factor >= 1e3:
        return "кПа"
    return "Па"


def describe_unit_systems() -> List[UnitDescriptor]:
    """Return unit systems with localized labels and pressure dimension."""

    systems: List[UnitDescriptor] = []
    for key, base in BASE_SYSTEMS.items():
        parts = [
            _LABEL_PARTS.get(part, part) for part in key.replace("-", " ").split()
        ]
        pressure = _pressure_label(base)
        label = f"{'-'.join(parts)} — {pressure}"
        systems.append(UnitDescriptor(key=key, label=label, pressure_unit=pressure))

    return sorted(systems, key=lambda u: u.key)
