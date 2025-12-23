from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Sequence

import tomllib

from kunit.api import convert_string
from kunit.core import engine
from kunit.core.engine import KeywordSpec
from kunit.core.fixed import format_lsdyna_10, join_fixed, split_fixed
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
class MaterialSection:
    kind: str
    model: str
    units: str
    payload: str

    def to_k(self) -> str:
        """Return payload text with trailing newline for concatenation."""

        return self.payload if self.payload.endswith("\n") else f"{self.payload}\n"


@dataclass(frozen=True)
class MaterialRecord:
    material_id: str
    name: str
    model: str
    units: str
    payload: str
    models: Sequence[str]
    reference: str | None = None
    comment: str | None = None
    tags: Sequence[str] = field(default_factory=list)
    meta: Mapping[str, Any] = field(default_factory=dict)
    source: str | None = None
    sections: Sequence[MaterialSection] = field(default_factory=list)

    @property
    def material(self) -> MaterialSection:
        for section in self.sections:
            if section.kind == "material":
                return section
        return self.sections[0]

    @property
    def eos(self) -> MaterialSection | None:
        for section in self.sections:
            if section.kind == "eos":
                return section
        return None

    def to_k(self) -> str:
        """Return .k text for all sections with trailing newline for concatenation."""

        return "".join(section.to_k() for section in self.sections)


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

    def _normalize_section(
        self, raw: Mapping[str, Any], kind: str, source_path: Path
    ) -> MaterialSection:
        if not isinstance(raw, Mapping):
            raise ValueError(f"Section '{kind}' in {source_path} must be an object")

        model = str(raw.get("model", "")).strip()
        if model not in SPECS_BY_NAME:
            known = ", ".join(sorted(SPECS_BY_NAME))
            raise ValueError(f"Unknown model '{model}' in {source_path}; known: {known}")

        units = str(raw.get("units", "")).strip()
        if units not in BASE_SYSTEMS:
            raise ValueError(
                f"Unknown units '{units}' for section '{kind}' in {source_path}; known: {list(BASE_SYSTEMS)}"
            )

        payload = raw.get("payload") or raw.get("text") or ""
        if not isinstance(payload, str) or not payload.strip():
            raise ValueError(
                f"Section '{kind}' in {source_path} must include payload text"
            )

        return MaterialSection(kind=kind, model=model, units=units, payload=payload)

    def _normalize_record(self, raw: Mapping[str, Any], source_path: Path) -> MaterialRecord:
        if not isinstance(raw, Mapping):
            raise ValueError(f"Material entry in {source_path} must be an object")

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

        sections: List[MaterialSection] = []
        for section_name in ("material", "eos"):
            section_data = raw.get(section_name)
            if section_data is not None:
                sections.append(
                    self._normalize_section(section_data, section_name, source_path)
                )

        if not sections:
            section = self._normalize_section(
                raw,
                kind="material",
                source_path=source_path,
            )
            sections.append(section)

        material_section = sections[0]
        model = material_section.model
        units = material_section.units
        payload = material_section.payload

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

        combined_payload = "\n".join(section.payload for section in sections)

        detected = _extract_models_from_payload(combined_payload)
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
            sections=sections,
        )


def export_materials(materials: Sequence[MaterialRecord]) -> str:
    """Concatenate materials into a single .k document."""

    out: List[str] = []

    for idx, material in enumerate(materials, start=1):
        text = material.to_k()
        for spec in _identifier_specs(material):
            id_fields = _identifier_fields(spec)
            if id_fields:
                text = _rewrite_identifier(text, spec, id_fields, idx)
        out.append(text)

    return "".join(out)


def convert_materials(materials: Sequence[MaterialRecord], dst_units: str) -> str:
    """Convert materials to dst_units and rewrite identifiers to incremental ids."""

    out: List[str] = []

    for idx, material in enumerate(materials, start=1):
        models = list(material.models) if material.models else [material.model]
        converted = convert_string(
            material.to_k(),
            src=material.units,
            dst=dst_units,
            models=models,
        )
        converted = converted if converted.endswith("\n") else f"{converted}\n"

        for spec in _identifier_specs(material):
            id_fields = _identifier_fields(spec)
            if id_fields:
                converted = _rewrite_identifier(converted, spec, id_fields, idx)

        out.append(converted)

    return "".join(out)


def _identifier_specs(material: MaterialRecord) -> List[KeywordSpec]:
    specs: List[KeywordSpec] = []
    seen: set[str] = set()
    candidate_names = [section.model for section in material.sections]
    candidate_names.extend(material.models)

    for name in candidate_names:
        if name in seen:
            continue
        spec = SPECS_BY_NAME.get(name)
        if spec:
            specs.append(spec)
            seen.add(name)
    return specs


def _identifier_fields(spec: KeywordSpec) -> set[str]:
    id_fields: set[str] = set()
    for card in spec.cards:
        for field in card:
            if field in {"mid", "eosid"}:
                id_fields.add(field)
    return id_fields


def _rewrite_identifier(payload: str, spec: KeywordSpec, field_names: set[str], new_id: int) -> str:
    lines = payload.splitlines(keepends=True)
    out: List[str] = []

    i = 0
    prefix = spec.keyword_prefix.upper()
    while i < len(lines):
        line = lines[i]
        if line.lstrip().upper().startswith(prefix):
            block = [line]
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith("*"):
                block.append(lines[i])
                i += 1
            out.extend(_rewrite_block_identifier(block, spec, field_names, new_id))
            continue

        out.append(line)
        i += 1

    rewritten = "".join(out)
    return rewritten if rewritten.endswith("\n") else f"{rewritten}\n"


def _rewrite_block_identifier(
    block: List[str], spec: KeywordSpec, field_names: set[str], new_id: int
) -> List[str]:
    data_idxs = engine._extract_data_lines(block, n=len(spec.cards))  # type: ignore[attr-defined]
    if not data_idxs:
        return block

    out = block[:]

    for line_i, card_fields in zip(data_idxs, spec.cards):
        if not field_names.intersection(card_fields):
            continue
        fields = split_fixed(block[line_i])
        new_fields: List[str] = []
        for name, raw in zip(card_fields, fields):
            if name in field_names:
                new_fields.append(format_lsdyna_10(new_id))
            else:
                new_fields.append(raw.strip())
        out[line_i] = join_fixed(new_fields)

    return out
