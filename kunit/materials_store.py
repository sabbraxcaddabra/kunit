from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Sequence

import tomllib

from kunit.core.units import BASE_SYSTEMS
from kunit.models import SPECS_BY_NAME


@dataclass(frozen=True)
class MaterialRecord:
    material_id: str
    name: str
    model: str
    units: str
    payload: str
    tags: Sequence[str] = field(default_factory=list)
    meta: Mapping[str, Any] = field(default_factory=dict)
    source: str | None = None

    def to_k(self) -> str:
        """Return .k text with a trailing newline for safe concatenation."""
        return self.payload if self.payload.endswith("\n") else f"{self.payload}\n"


class MaterialStore:
    """Lightweight file-based store for materials.

    Files are authored by developers/administrators locally in JSON or TOML, e.g.:
    {
      "materials": [
        {"id": "steel-1", "name": "Steel #1", "model": "mat-jc", "units": "mm-mg-us", "payload": "*MAT..."}
      ]
    }
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
        return sorted(
            [
                *self.root.glob("*.json"),
                *self.root.glob("*.toml"),
            ]
        )

    def _load_file(self, path: Path) -> List[MaterialRecord]:
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix.lower() == ".toml":
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        else:
            return []

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
        tags = raw.get("tags") or []
        if not isinstance(tags, Sequence) or isinstance(tags, (str, bytes)):
            raise ValueError(f"Tags for material '{material_id}' must be a list of strings")
        if any(not isinstance(tag, str) for tag in tags):
            raise ValueError(f"Each tag for material '{material_id}' must be a string")

        meta = raw.get("meta") if isinstance(raw.get("meta"), Mapping) else {}

        return MaterialRecord(
            material_id=material_id,
            name=name,
            model=model,
            units=units,
            payload=payload,
            tags=list(tags),
            meta=meta,
            source=str(source_path),
        )


def export_materials(materials: Sequence[MaterialRecord]) -> str:
    """Concatenate materials into a single .k document."""

    return "".join(m.to_k() for m in materials)
