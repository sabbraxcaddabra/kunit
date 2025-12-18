from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .fixed import split_fixed, join_fixed, is_number, format_lsdyna_10
from .units import BaseUnits, DIM, scale_factor


@dataclass(frozen=True)
class KeywordSpec:
    """
    Specification of a keyword block with fixed-width numeric cards.
    """

    name: str  # internal name, e.g. "mat-jc"
    keyword_prefix: str  # match by startswith (upper), e.g. "*MAT_JOHNSON_COOK"
    cards: Sequence[Sequence[str]]  # list of 8-field card layouts
    dims: Dict[str, Optional[DIM]]  # dimensions for fields; None => do not convert


@dataclass(frozen=True)
class FieldTransform:
    """User-provided transformation applied after unit scaling."""

    power: float = 1.0
    multiplier: float = 1.0
    offset: float = 0.0
    dim: Optional[DIM] = None  # override spec dim if provided
    scale_dim: Optional[DIM] = None  # scale factor raised to custom power
    scale_dim_field: Optional[str] = None  # reuse dimension of another field
    scale_power_field: Optional[str] = None  # read exponent from another field
    scale_power: Optional[float] = None  # fixed exponent for scaling

    def scale_exponent(self, context: Mapping[str, float]) -> float:
        if self.scale_power_field and self.scale_power_field in context:
            return float(context[self.scale_power_field])
        if self.scale_power is not None:
            return float(self.scale_power)
        return 1.0

    def has_custom_scaling(self) -> bool:
        return (
            self.scale_dim is not None
            or self.scale_dim_field is not None
            or self.scale_power_field is not None
            or self.scale_power is not None
        )

    def apply(self, value: float) -> float:
        return (value**self.power) * self.multiplier + self.offset


def _is_data_line(line: str) -> bool:
    """
    Data line criterion: not comment/keyword, and first fixed field is numeric.
    This excludes TITLE lines and most text lines.
    """
    s = line.lstrip()
    if not s or s.startswith(("*", "$")):
        return False
    f0 = split_fixed(line)[0].strip()
    return is_number(f0)


def _extract_data_lines(block: List[str], n: int) -> List[int]:
    idxs: List[int] = []
    for i, line in enumerate(block):
        if _is_data_line(line):
            idxs.append(i)
            if len(idxs) == n:
                break
    return idxs


def _convert_field(
    field_name: str,
    raw_field: str,
    src: BaseUnits,
    dst: BaseUnits,
    dims: Dict[str, Optional[DIM]],
    transform: Optional[FieldTransform] = None,
    context: Mapping[str, float] | None = None,
) -> str:
    s = raw_field.strip()
    if not s or not is_number(s):
        return s

    dim = transform.dim if transform and transform.dim is not None else dims.get(field_name, None)
    value = float(s)
    ctx = context or {}
    if transform and transform.has_custom_scaling():
        scale_dim = None
        if transform.scale_dim is not None:
            scale_dim = transform.scale_dim
        elif transform.scale_dim_field is not None:
            if transform.scale_dim_field not in dims:
                raise ValueError(
                    f"Unknown scale_dim_field '{transform.scale_dim_field}' for '{field_name}'"
                )
            scale_dim = dims[transform.scale_dim_field]
        elif dim is not None:
            scale_dim = dim
        if scale_dim is not None:
            value *= scale_factor(src, dst, scale_dim) ** transform.scale_exponent(ctx)
    elif dim is not None:
        value *= scale_factor(src, dst, dim)
    if transform:
        value = transform.apply(value)
    return format_lsdyna_10(value)


CustomTransformMap = Mapping[str, Mapping[str, FieldTransform]]


def convert_block(
    block: List[str],
    spec: KeywordSpec,
    src: BaseUnits,
    dst: BaseUnits,
    custom_transforms: Optional[CustomTransformMap] = None,
) -> List[str]:
    out = block[:]
    data_idxs = _extract_data_lines(block, n=len(spec.cards))
    if len(data_idxs) < len(spec.cards):
        return out  # unexpected structure => leave block unchanged

    spec_transforms: Mapping[str, FieldTransform] = (
        custom_transforms.get(spec.name, {}) if custom_transforms else {}
    )

    context: Dict[str, float] = {}
    for line_i, card_fields in zip(data_idxs, spec.cards):
        fields = split_fixed(block[line_i])
        for name, raw in zip(card_fields, fields):
            if name in ("mid", "eosid", "_"):
                continue
            raw_val = raw.strip()
            if is_number(raw_val):
                context[name] = float(raw_val)

    for line_i, card_fields in zip(data_idxs, spec.cards):
        fields = split_fixed(block[line_i])
        new_fields: List[str] = []
        for name, raw in zip(card_fields, fields):
            if name in ("mid", "eosid", "_"):
                new_fields.append(raw.strip())  # IDs/empty
            else:
                transform = spec_transforms.get(name)
                new_fields.append(
                    _convert_field(name, raw, src, dst, spec.dims, transform, context)
                )
        out[line_i] = join_fixed(new_fields)

    return out


def convert_text(
    text: str,
    specs: Sequence[KeywordSpec],
    src: BaseUnits,
    dst: BaseUnits,
    *,
    custom_transforms: Optional[CustomTransformMap] = None,
) -> str:
    lines = text.splitlines(keepends=True)
    out: List[str] = []

    # precompute (upper_prefix -> spec)
    spec_map: List[Tuple[str, KeywordSpec]] = [
        (s.keyword_prefix.upper(), s) for s in specs
    ]

    i = 0
    while i < len(lines):
        line = lines[i]
        u = line.lstrip().upper()

        matched: Optional[KeywordSpec] = None
        for prefix, spec in spec_map:
            if u.startswith(prefix):
                matched = spec
                break

        if matched is None:
            out.append(line)
            i += 1
            continue

        # collect block until next keyword or EOF
        block = [line]
        i += 1
        while i < len(lines) and not lines[i].lstrip().startswith("*"):
            block.append(lines[i])
            i += 1

        out.extend(convert_block(block, matched, src, dst, custom_transforms))

    return "".join(out)
