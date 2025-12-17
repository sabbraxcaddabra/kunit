from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class BaseUnits:
    length_si: float  # meters per 1 length unit
    mass_si: float  # kg per 1 mass unit
    time_si: float  # s per 1 time unit


BASE_SYSTEMS: Dict[str, BaseUnits] = {
    "mm-mg-us": BaseUnits(1e-3, 1e-6, 1e-6),
    "cm-g-us": BaseUnits(1e-2, 1e-3, 1e-6),
    "m-kg-s": BaseUnits(1.0, 1.0, 1.0),
}

DIM = Tuple[int, int, int]  # (a,b,c) for M^a L^b T^c


def scale_factor(src: BaseUnits, dst: BaseUnits, dim: DIM) -> float:
    a, b, c = dim
    return (
        (src.mass_si / dst.mass_si) ** a
        * (src.length_si / dst.length_si) ** b
        * (src.time_si / dst.time_si) ** c
    )
