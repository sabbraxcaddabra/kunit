from __future__ import annotations

import json
from typing import Any, Iterable, List, Mapping, MutableMapping, Sequence

from .core.units import BASE_SYSTEMS, BaseUnits, DIM, describe_unit_systems
from .core.engine import CustomTransformMap, FieldTransform, convert_text, KeywordSpec
from .models import ALL_SPECS, SPECS_BY_NAME


def get_unit_keys() -> List[str]:
    """Return available base unit system keys (e.g., 'mm-mg-us')."""
    return sorted(BASE_SYSTEMS.keys())


def get_unit_descriptors():
    """Return available base unit systems with presentation labels."""

    return describe_unit_systems()


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


def _parse_dim(value: Any) -> DIM:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("dim must be a 3-item list or tuple of integers")
    try:
        return tuple(int(v) for v in value)  # type: ignore[return-value]
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("dim must contain integers") from exc


def parse_custom_transforms(raw: Mapping[str, Any]) -> CustomTransformMap:
    """
    Validate and normalize user-provided custom transforms.

    Expected format (JSON/TOML/etc.):
    {
      "mat-jc": {
        "pr": {"power": 1.2, "multiplier": 1.0, "offset": 0.0, "dim": [1,-1,-2]},
        "ro": {"multiplier": 0.5},
        "g": {
          "scale_dim_field": "p",    # reuse the dimension of field p
          "scale_power_field": "z"   # raise scale factor to the value of field z
        }
      }
    }
    """

    spec_map: MutableMapping[str, MutableMapping[str, FieldTransform]] = {}
    for spec_name, fields in raw.items():
        if not isinstance(fields, Mapping):
            raise ValueError(f"Custom transforms for '{spec_name}' must be a mapping of fields")
        field_map: MutableMapping[str, FieldTransform] = {}
        for field_name, cfg in fields.items():
            if not isinstance(cfg, Mapping):
                raise ValueError(f"Transform for field '{field_name}' must be an object")
            power = float(cfg.get("power", 1.0))
            multiplier = float(cfg.get("multiplier", 1.0))
            offset = float(cfg.get("offset", 0.0))
            dim_value = cfg.get("dim")
            dim = _parse_dim(dim_value) if dim_value is not None else None
            scale_dim_value = cfg.get("scale_dim")
            scale_dim = _parse_dim(scale_dim_value) if scale_dim_value is not None else None
            scale_dim_field = cfg.get("scale_dim_field")
            if scale_dim_field is not None and not isinstance(scale_dim_field, str):
                raise ValueError("scale_dim_field must be a string when provided")
            scale_power_field = cfg.get("scale_power_field")
            if scale_power_field is not None and not isinstance(scale_power_field, str):
                raise ValueError("scale_power_field must be a string when provided")
            scale_power_value = cfg.get("scale_power")
            scale_power = float(scale_power_value) if scale_power_value is not None else None
            field_map[field_name] = FieldTransform(
                power=power,
                multiplier=multiplier,
                offset=offset,
                dim=dim,
                scale_dim=scale_dim,
                scale_dim_field=scale_dim_field,
                scale_power_field=scale_power_field,
                scale_power=scale_power,
            )
        spec_map[spec_name] = field_map
    return spec_map


def _normalize_custom_transforms(
    custom_transforms: Mapping[str, Any] | str | None,
) -> CustomTransformMap | None:
    if custom_transforms is None:
        return None
    if isinstance(custom_transforms, str):
        custom_transforms = json.loads(custom_transforms)
    if not isinstance(custom_transforms, Mapping):
        raise ValueError("custom_transforms must be a mapping or JSON string")
    return parse_custom_transforms(custom_transforms)


def convert_string(
    text: str,
    *,
    src: str,
    dst: str,
    models: Sequence[str] | str = "all",
    custom_transforms: Mapping[str, Any] | str | None = None,
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
    transforms = _normalize_custom_transforms(custom_transforms)
    return convert_text(
        text, specs=specs, src=src_u, dst=dst_u, custom_transforms=transforms
    )


class KunitConverter:
    """
    Reusable converter bound to (src, dst, models).
    Keeps API purely in-memory (no file I/O).
    """

    def __init__(
        self,
        src: str,
        dst: str,
        models: Sequence[str] | str = "all",
        custom_transforms: Mapping[str, Any] | str | None = None,
    ):
        try:
            self._src_u: BaseUnits = BASE_SYSTEMS[src]
            self._dst_u: BaseUnits = BASE_SYSTEMS[dst]
        except KeyError as e:
            raise ValueError(
                f"Unknown unit key '{e.args[0]}'. Known: {get_unit_keys()}"
            ) from None
        self._specs: Sequence[KeywordSpec] = _resolve_specs(models)
        self._transforms = _normalize_custom_transforms(custom_transforms)

    def convert_text(self, text: str) -> str:
        return convert_text(
            text,
            specs=self._specs,
            src=self._src_u,
            dst=self._dst_u,
            custom_transforms=self._transforms,
        )

