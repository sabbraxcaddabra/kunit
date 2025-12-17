from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

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
) -> str:
    s = raw_field.strip()
    if not s or not is_number(s):
        return s

    dim = dims.get(field_name, None)
    if dim is None:
        return s

    k = scale_factor(src, dst, dim)
    return format_lsdyna_10(float(s) * k)


def convert_block(
    block: List[str], spec: KeywordSpec, src: BaseUnits, dst: BaseUnits
) -> List[str]:
    out = block[:]
    data_idxs = _extract_data_lines(block, n=len(spec.cards))
    if len(data_idxs) < len(spec.cards):
        return out  # unexpected structure => leave block unchanged

    for line_i, card_fields in zip(data_idxs, spec.cards):
        fields = split_fixed(block[line_i])
        new_fields: List[str] = []
        for name, raw in zip(card_fields, fields):
            if name in ("mid", "eosid", "_"):
                new_fields.append(raw.strip())  # IDs/empty
            else:
                new_fields.append(_convert_field(name, raw, src, dst, spec.dims))
        out[line_i] = join_fixed(new_fields)

    return out


def convert_text(
    text: str,
    specs: Sequence[KeywordSpec],
    src: BaseUnits,
    dst: BaseUnits,
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

        out.extend(convert_block(block, matched, src, dst))

    return "".join(out)
