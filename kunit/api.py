from __future__ import annotations

from typing import Iterable, List, Sequence

from .core.units import BASE_SYSTEMS, BaseUnits
from .core.engine import convert_text, KeywordSpec
from .models import ALL_SPECS, SPECS_BY_NAME


def get_unit_keys() -> List[str]:
    """Return available base unit system keys (e.g., 'mm-mg-us')."""
    return sorted(BASE_SYSTEMS.keys())


def list_models() -> List[str]:
    """Return internal model names in a stable order."""
    return [s.name for s in ALL_SPECS]


def _resolve_specs(models: Sequence[str] | str) -> Sequence[KeywordSpec]:
    if isinstance(models, str):
        if models.strip().lower() == "all":
            return ALL_SPECS
        # comma-separated convenience
        models = [m.strip() for m in models.split(",") if m.strip()]

    unknown = [m for m in models if m not in SPECS_BY_NAME]
    if unknown:
        known = ", ".join(sorted(SPECS_BY_NAME.keys()))
        raise ValueError(f"Unknown models: {unknown}. Known: {known}")
    return [SPECS_BY_NAME[m] for m in models]


def convert_string(
    text: str,
    *,
    src: str,
    dst: str,
    models: Sequence[str] | str = "all",
) -> str:
    """
    Convert LS-DYNA keyword text between unit systems preserving fixed-width.

    - text: raw .k file contents
    - src/dst: unit system keys from get_unit_keys()
    - models: 'all', comma-separated string, or a list of names from list_models()
    """
    try:
        src_u: BaseUnits = BASE_SYSTEMS[src]
        dst_u: BaseUnits = BASE_SYSTEMS[dst]
    except KeyError as e:
        raise ValueError(
            f"Unknown unit key '{e.args[0]}'. Known: {get_unit_keys()}"
        ) from None

    specs = _resolve_specs(models)
    return convert_text(text, specs=specs, src=src_u, dst=dst_u)


class KunitConverter:
    """
    Reusable converter bound to (src, dst, models).
    Keeps API purely in-memory (no file I/O).
    """

    def __init__(self, src: str, dst: str, models: Sequence[str] | str = "all"):
        try:
            self._src_u: BaseUnits = BASE_SYSTEMS[src]
            self._dst_u: BaseUnits = BASE_SYSTEMS[dst]
        except KeyError as e:
            raise ValueError(
                f"Unknown unit key '{e.args[0]}'. Known: {get_unit_keys()}"
            ) from None
        self._specs: Sequence[KeywordSpec] = _resolve_specs(models)

    def convert_text(self, text: str) -> str:
        return convert_text(text, specs=self._specs, src=self._src_u, dst=self._dst_u)

