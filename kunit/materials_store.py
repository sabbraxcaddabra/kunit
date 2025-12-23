from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Sequence

import tomllib

from kunit.core.units import BASE_SYSTEMS
from kunit.models import ALL_SPECS, SPECS_BY_NAME


def _extract_models_from_payload(payload: str) -> List[str]:
    """Return ordered unique models detected by keyword prefixes in payload."""

    models: List[str] = []
    seen = set()
    spec_prefixes = [(spec.keyword_prefix.upper(), spec.name) for spec in ALL_SPECS]

    for line in payload.splitlines():
        s = line.lstrip()
        if not s.startswith("*"):
            continue
        upper = s.upper()
        for prefix, name in spec_prefixes:
            if upper.startswith(prefix) and name not in seen:
                models.append(name)
                seen.add(name)
                break

    return models


@dataclass(frozen=True)
class MaterialRecord:
    material_id: str
    name: str
    model: str
    units: str
    payload: str
    models: Sequence[str] = field(default_factory=list)
    reference: str | None = None
    comment: str | None = None
    tags: Sequence[str] = field(default_factory=list)
    meta: Mapping[str, Any] = field(default_factory=dict)
    source: str | None = None

    def to_k(self) -> str:
        """Return .k text with a trailing newline for safe concatenation."""
        return self.payload if self.payload.endswith("\n") else f"{self.payload}\n"


class MaterialStore:
    """Lightweight file-based store for materials.

    Files are authored by developers/administrators locally as TOML collections, e.g.:

    [[materials]]
    id = "steel-1"
    name = "Steel #1"
    model = "mat-jc"
    units = "mm-mg-us"
    text = "*MAT..."
    reference = "https://example.com/ref"
    comment = "Short note about provenance"
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def list_materials(self) -> List[MaterialRecord]:
        records: List[MaterialRecord] = []
        for path in self._iter_material_files():
            records.extend(self._load_file(path))
        return records

    def export_all(self) -> str:
        return "".join(m.to_k() for m in self.list_materials())

    def _iter_material_files(self) -> Iterable[Path]:
        if not self.root.exists():
            return []
        return sorted(self.root.glob("*.toml"))

    def _load_file(self, path: Path) -> List[MaterialRecord]:
        if path.suffix.lower() != ".toml":
            return []

        data = tomllib.loads(path.read_text(encoding="utf-8"))

        materials = data.get("materials") if isinstance(data, Mapping) else None
        if not isinstance(materials, list):
            return []

        return [self._normalize_record(item, path) for item in materials]

    def _normalize_record(self, raw: Mapping[str, Any], source_path: Path) -> MaterialRecord:
        if not isinstance(raw, Mapping):
            raise ValueError(f"Material entry in {source_path} must be an object")

        model = str(raw.get("model", "")).strip()
        if model not in SPECS_BY_NAME:
            known = ", ".join(sorted(SPECS_BY_NAME))
            raise ValueError(f"Unknown model '{model}' in {source_path}; known: {known}")

        units = str(raw.get("units", "")).strip()
        if units not in BASE_SYSTEMS:
            raise ValueError(
                f"Unknown units '{units}' for material '{model}' in {source_path}; known: {list(BASE_SYSTEMS)}"
            )

        payload = raw.get("payload") or raw.get("text") or ""
        if not isinstance(payload, str) or not payload.strip():
            raise ValueError(f"Material '{model}' in {source_path} must include payload text")

        material_id = str(raw.get("id") or raw.get("name") or source_path.stem)

        name = str(raw.get("name") or material_id).strip()
        reference = raw.get("reference")
        if reference is not None and not isinstance(reference, str):
            raise ValueError(f"Reference for material '{material_id}' must be a string if provided")

        comment = raw.get("comment")
        if comment is not None and not isinstance(comment, str):
            raise ValueError(f"Comment for material '{material_id}' must be a string if provided")

        raw_tags = raw.get("tags") or []
        tags: List[str]
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, Sequence) and not isinstance(raw_tags, (str, bytes)):
            if any(not isinstance(tag, str) for tag in raw_tags):
                raise ValueError(f"Each tag for material '{material_id}' must be a string")
            tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
        else:
            raise ValueError(f"Tags for material '{material_id}' must be a list of strings or a comma-separated string")

        meta = raw.get("meta") if isinstance(raw.get("meta"), Mapping) else {}

        raw_models = raw.get("models")
        models: List[str] = []
        if raw_models is None:
            models = [model]
        elif isinstance(raw_models, str):
            models = [m for m in (s.strip() for s in raw_models.split(",")) if m]
        elif isinstance(raw_models, Sequence) and not isinstance(raw_models, (str, bytes)):
            if any(not isinstance(m, str) for m in raw_models):
                raise ValueError(f"Each model for material '{material_id}' must be a string")
            models = [str(m).strip() for m in raw_models if str(m).strip()]
        else:
            raise ValueError(f"Models for material '{material_id}' must be a list or comma-separated string when provided")

        detected = _extract_models_from_payload(payload)
        for m in detected:
            if m not in models:
                models.append(m)
        if model not in models:
            models.insert(0, model)

        unknown_models = [m for m in models if m not in SPECS_BY_NAME]
        if unknown_models:
            known = ", ".join(sorted(SPECS_BY_NAME))
            raise ValueError(
                f"Unknown models {unknown_models} for material '{material_id}' in {source_path}; known: {known}"
            )

        return MaterialRecord(
            material_id=material_id,
            name=name,
            model=model,
            units=units,
            payload=payload,
            models=models,
            reference=reference,
            comment=comment,
            tags=list(tags),
            meta=meta,
            source=str(source_path),
        )


def export_materials(materials: Sequence[MaterialRecord]) -> str:
    """Concatenate materials into a single .k document."""

    return "".join(m.to_k() for m in materials)
