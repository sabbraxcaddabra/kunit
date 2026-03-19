from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
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


def _require_lang_map(
    raw: object, *, field: str, material_id: str, source_path: Path
) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(
            f"Field '{field}' for material '{material_id}' in {source_path} must be a TOML inline table like "
            f"{{ru=..., en=...}}"
        )
    if "ru" not in raw or "en" not in raw:
        raise ValueError(
            f"Field '{field}' for material '{material_id}' in {source_path} must include both 'ru' and 'en'"
        )
    return raw


def _parse_i18n_string(
    raw: object, *, field: str, material_id: str, source_path: Path
) -> Mapping[str, str]:
    data = _require_lang_map(raw, field=field, material_id=material_id, source_path=source_path)
    out: dict[str, str] = {}
    for lang in ("ru", "en"):
        val = data.get(lang)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(
                f"Field '{field}.{lang}' for material '{material_id}' in {source_path} must be a non-empty string"
            )
        out[lang] = val.strip()
    return out


def _parse_i18n_tags(
    raw: object, *, field: str, material_id: str, source_path: Path
) -> Mapping[str, List[str]]:
    data = _require_lang_map(raw, field=field, material_id=material_id, source_path=source_path)
    out: dict[str, List[str]] = {}
    for lang in ("ru", "en"):
        val = data.get(lang)
        tags: List[str]
        if isinstance(val, str):
            tags = [t.strip() for t in val.split(",") if t.strip()]
        elif isinstance(val, Sequence) and not isinstance(val, (str, bytes)):
            if any(not isinstance(tag, str) for tag in val):
                raise ValueError(
                    f"Each tag for field '{field}.{lang}' of material '{material_id}' in {source_path} must be a string"
                )
            tags = [str(tag).strip() for tag in val if str(tag).strip()]
        else:
            raise ValueError(
                f"Field '{field}.{lang}' for material '{material_id}' in {source_path} must be a list of strings "
                f"or a comma-separated string"
            )
        if not tags:
            raise ValueError(
                f"Field '{field}.{lang}' for material '{material_id}' in {source_path} must be non-empty"
            )
        out[lang] = tags
    return out


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Expected string value")
    text = value.strip()
    return text or None


def _parse_references(
    raw_references: object,
    *,
    legacy_reference: object,
    material_id: str,
    source_path: Path,
) -> List[Mapping[str, Any]]:
    references: List[Mapping[str, Any]] = []

    if raw_references is not None:
        if not isinstance(raw_references, list):
            raise ValueError(
                f"Field 'references' for material '{material_id}' in {source_path} must be an array of objects"
            )
        references.extend(
            _parse_reference_item(item, material_id=material_id, source_path=source_path)
            for item in raw_references
        )

    if legacy_reference is not None:
        legacy_url = _optional_text(legacy_reference)
        if legacy_url is not None:
            references.append(
                {
                    "title": {"ru": legacy_url, "en": legacy_url},
                    "url": legacy_url,
                    "kind": None,
                    "publisher": None,
                    "authors": [],
                    "year": None,
                    "doi": None,
                    "accessed": None,
                    "note": None,
                }
            )

    return references


def _parse_reference_item(
    raw: object,
    *,
    material_id: str,
    source_path: Path,
) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(
            f"Each item in 'references' for material '{material_id}' in {source_path} must be an object"
        )

    title_raw = raw.get("title")
    title: Mapping[str, str] | None = None
    if title_raw is not None:
        title = _parse_i18n_string(
            title_raw,
            field="references.title",
            material_id=material_id,
            source_path=source_path,
        )

    url = _optional_text(raw.get("url"))
    if url is not None:
        scheme = urlparse(url).scheme.lower()
        if scheme not in {"http", "https"}:
            raise ValueError(
                f"Field 'references.url' for material '{material_id}' in {source_path} must use http/https"
            )

    doi = _optional_text(raw.get("doi"))

    if title is None and url is None and doi is None:
        raise ValueError(
            f"Reference item for material '{material_id}' in {source_path} must include at least one of title/url/doi"
        )

    kind = _optional_text(raw.get("kind"))
    valid_kinds = {"paper", "standard", "datasheet", "manual", "report", "vendor", "internal"}
    if kind is not None and kind not in valid_kinds:
        raise ValueError(
            f"Field 'references.kind' for material '{material_id}' in {source_path} must be one of {sorted(valid_kinds)}"
        )

    publisher = _optional_text(raw.get("publisher"))

    authors_raw = raw.get("authors")
    authors: List[str] = []
    if authors_raw is not None:
        if not isinstance(authors_raw, Sequence) or isinstance(authors_raw, (str, bytes)):
            raise ValueError(
                f"Field 'references.authors' for material '{material_id}' in {source_path} must be a list of strings"
            )
        authors = []
        for author in authors_raw:
            clean = _optional_text(author)
            if clean is not None:
                authors.append(clean)

    year_raw = raw.get("year")
    year: int | None = None
    if year_raw is not None:
        if not isinstance(year_raw, int):
            raise ValueError(
                f"Field 'references.year' for material '{material_id}' in {source_path} must be an integer"
            )
        current_year = date.today().year + 1
        if year_raw < 1800 or year_raw > current_year:
            raise ValueError(
                f"Field 'references.year' for material '{material_id}' in {source_path} must be between 1800 and {current_year}"
            )
        year = year_raw

    accessed_raw = _optional_text(raw.get("accessed"))
    accessed: str | None = None
    if accessed_raw is not None:
        try:
            date.fromisoformat(accessed_raw)
        except ValueError as exc:
            raise ValueError(
                f"Field 'references.accessed' for material '{material_id}' in {source_path} must be ISO date YYYY-MM-DD"
            ) from exc
        accessed = accessed_raw

    note_raw = raw.get("note")
    note: Mapping[str, str] | None = None
    if note_raw is not None:
        note = _parse_i18n_string(
            note_raw,
            field="references.note",
            material_id=material_id,
            source_path=source_path,
        )

    return {
        "title": title,
        "url": url,
        "kind": kind,
        "publisher": publisher,
        "authors": authors,
        "year": year,
        "doi": doi,
        "accessed": accessed,
        "note": note,
    }


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
    references: Sequence[Mapping[str, Any]] = field(default_factory=list)
    comment: str | None = None
    tags: Sequence[str] = field(default_factory=list)
    name_i18n: Mapping[str, str] = field(default_factory=dict)
    comment_i18n: Mapping[str, str] = field(default_factory=dict)
    tags_i18n: Mapping[str, Sequence[str]] = field(default_factory=dict)
    meta: Mapping[str, Any] = field(default_factory=dict)
    source: str | None = None
    sections: Sequence[MaterialSection] = field(default_factory=list)

    def display_name(self, lang: str) -> str:
        return str(self.name_i18n.get(lang) or self.name)

    def display_comment(self, lang: str) -> str | None:
        return self.comment_i18n.get(lang) or self.comment

    def display_tags(self, lang: str) -> Sequence[str]:
        tags = self.tags_i18n.get(lang)
        return list(tags) if tags is not None else list(self.tags)

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


@dataclass(frozen=True)
class AssignedMaterialIds:
    mid: int
    eosid: int


@dataclass(frozen=True)
class MaterialExportResult:
    payload: str
    assigned_ids: Mapping[str, AssignedMaterialIds]


@dataclass(frozen=True)
class StructuredMaterialGroupRow:
    ammgnm: str
    material_id: str
    pref: str = ""


@dataclass(frozen=True)
class StructuredMaterialGroupBlock:
    block_type: str
    rows: Sequence[StructuredMaterialGroupRow]


@dataclass(frozen=True)
class StructuredMaterialGroupRequest:
    blocks: Sequence[StructuredMaterialGroupBlock]


_STRUCTURED_GROUP_BLOCK_TYPES = {"AXISYM", "PLNEPS", "3D"}
_STRUCTURED_GROUP_MAX_FIELD_LENGTH = 10
_STRUCTURED_GROUP_COMMENT = (
    "$#  ammgnm       mid     eosid         -         -         -         -      pref\n"
)


def _normalize_group_text_field(
    raw: object, *, field_name: str, allow_empty: bool = False
) -> str:
    if raw is None:
        if allow_empty:
            return ""
        raise ValueError(f"Field '{field_name}' is required")
    if not isinstance(raw, str):
        raise ValueError(f"Field '{field_name}' must be a string")

    value = raw.strip()
    if not value and not allow_empty:
        raise ValueError(f"Field '{field_name}' is required")
    if len(value) > _STRUCTURED_GROUP_MAX_FIELD_LENGTH:
        raise ValueError(
            f"Field '{field_name}' must fit into 10 characters"
        )
    return value


def _normalize_group_material_id(raw: object) -> str:
    if raw is None:
        raise ValueError("Field 'material_id' is required")
    if not isinstance(raw, str):
        raise ValueError("Field 'material_id' must be a string")

    value = raw.strip()
    if not value:
        raise ValueError("Field 'material_id' is required")
    return value


def parse_structured_material_group_request(
    raw: object, *, allowed_material_ids: set[str] | None = None
) -> StructuredMaterialGroupRequest:
    if raw is None:
        return StructuredMaterialGroupRequest(blocks=[])
    if isinstance(raw, str):
        if not raw.strip():
            return StructuredMaterialGroupRequest(blocks=[])
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Structured material groups payload must be valid JSON") from exc

    if not isinstance(raw, Mapping):
        raise ValueError("Structured material groups payload must be an object")

    raw_blocks = raw.get("blocks", [])
    if raw_blocks is None:
        raw_blocks = []
    if not isinstance(raw_blocks, list):
        raise ValueError("Structured material groups 'blocks' must be a list")
    if len(raw_blocks) > 1:
        raise ValueError("Structured material groups support a single block per export")

    blocks: list[StructuredMaterialGroupBlock] = []
    for block_index, raw_block in enumerate(raw_blocks, start=1):
        if not isinstance(raw_block, Mapping):
            raise ValueError(f"Structured material group block #{block_index} must be an object")

        block_type = _normalize_group_text_field(raw_block.get("type"), field_name="type")
        if block_type not in _STRUCTURED_GROUP_BLOCK_TYPES:
            supported = ", ".join(sorted(_STRUCTURED_GROUP_BLOCK_TYPES))
            raise ValueError(f"Unsupported structured material group type '{block_type}'; expected one of {supported}")

        raw_rows = raw_block.get("rows", [])
        if not isinstance(raw_rows, list) or not raw_rows:
            raise ValueError(f"Structured material group block '{block_type}' must include at least one row")

        rows: list[StructuredMaterialGroupRow] = []
        for row_index, raw_row in enumerate(raw_rows, start=1):
            if not isinstance(raw_row, Mapping):
                raise ValueError(
                    f"Structured material group row #{row_index} in block '{block_type}' must be an object"
                )

            ammgnm = _normalize_group_text_field(raw_row.get("ammgnm"), field_name="ammgnm")
            material_id = _normalize_group_material_id(raw_row.get("material_id"))
            if allowed_material_ids is not None and material_id not in allowed_material_ids:
                raise ValueError(
                    f"Structured material group row #{row_index} references a selected material outside the export set"
                )

            pref = _normalize_group_text_field(
                raw_row.get("pref", ""),
                field_name="pref",
                allow_empty=True,
            )
            rows.append(
                StructuredMaterialGroupRow(
                    ammgnm=ammgnm,
                    material_id=material_id,
                    pref=pref,
                )
            )

        blocks.append(StructuredMaterialGroupBlock(block_type=block_type, rows=rows))

    return StructuredMaterialGroupRequest(blocks=blocks)


def render_structured_material_groups(
    request: StructuredMaterialGroupRequest,
    assigned_ids: Mapping[str, AssignedMaterialIds],
) -> str:
    blocks: list[str] = []

    for block in request.blocks:
        suffix = "" if block.block_type == "3D" else f"_{block.block_type}"
        blocks.append(f"*ALE_STRUCTURED_MULTI-MATERIAL_GROUP{suffix}\n")
        blocks.append(_STRUCTURED_GROUP_COMMENT)

        for row in block.rows:
            material_ids = assigned_ids.get(row.material_id)
            if material_ids is None:
                raise ValueError(
                    f"Structured material group row references unknown material '{row.material_id}'"
                )

            pref = row.pref or "0.0"
            blocks.append(
                join_fixed(
                    [
                        row.ammgnm,
                        str(material_ids.mid),
                        str(material_ids.eosid),
                        "",
                        "",
                        "",
                        "",
                        pref,
                    ]
                )
            )

    return "".join(blocks)


class MaterialStore:
    """Lightweight file-based store for materials.

    Files are authored by developers/administrators locally as TOML collections, e.g.:

    [[materials]]
    id = "steel-1"
    name = { ru = "Сталь #1", en = "Steel #1" }
    model = "mat-jc"
    units = "mm-mg-us"
    text = "*MAT..."
    reference = "https://example.com/ref"
    comment = { ru = "Описание на русском", en = "English description" }
    tags = { ru = ["тег1", "тег2"], en = ["tag1", "tag2"] }
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

        name_i18n = _parse_i18n_string(
            raw.get("name"),
            field="name",
            material_id=material_id,
            source_path=source_path,
        )
        name = name_i18n["ru"]

        legacy_reference = raw.get("reference")
        references = _parse_references(
            raw.get("references"),
            legacy_reference=legacy_reference,
            material_id=material_id,
            source_path=source_path,
        )
        reference = next((str(item["url"]) for item in references if item.get("url")), None)

        comment_i18n = _parse_i18n_string(
            raw.get("comment"),
            field="comment",
            material_id=material_id,
            source_path=source_path,
        )
        comment = comment_i18n["ru"]

        tags_i18n = _parse_i18n_tags(
            raw.get("tags"),
            field="tags",
            material_id=material_id,
            source_path=source_path,
        )
        tags = tags_i18n["ru"]

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
            references=references,
            comment=comment,
            tags=list(tags),
            name_i18n=name_i18n,
            comment_i18n=comment_i18n,
            tags_i18n=tags_i18n,
            meta=meta,
            source=str(source_path),
            sections=sections,
        )


def build_materials_export(
    materials: Sequence[MaterialRecord], dst_units: str | None = None
) -> MaterialExportResult:
    """Build exported material text and assigned identifier map."""

    out: List[str] = []
    assigned_ids: dict[str, AssignedMaterialIds] = {}

    for idx, material in enumerate(materials, start=1):
        if dst_units is None:
            converted = material.to_k()
        else:
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
        assigned_ids[material.material_id] = AssignedMaterialIds(
            mid=idx,
            eosid=idx if material.eos is not None else 0,
        )

    return MaterialExportResult(payload="".join(out), assigned_ids=assigned_ids)


def export_materials(materials: Sequence[MaterialRecord]) -> str:
    """Concatenate materials into a single .k document."""

    return build_materials_export(materials).payload


def convert_materials(materials: Sequence[MaterialRecord], dst_units: str) -> str:
    """Convert materials to dst_units and rewrite identifiers to incremental ids."""

    return build_materials_export(materials, dst_units).payload


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
