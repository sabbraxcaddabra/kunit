from __future__ import annotations

from typing import List

FIELD_WIDTH = 10
N_FIELDS = 8


def split_fixed(line: str) -> List[str]:
    """Split LS-DYNA fixed-width line into 8 fields of 10 chars (pads if shorter)."""
    core = line[:-1] if line.endswith("\n") else line
    core = core.ljust(FIELD_WIDTH * N_FIELDS)
    return [core[i * FIELD_WIDTH : (i + 1) * FIELD_WIDTH] for i in range(N_FIELDS)]


def join_fixed(fields: List[str]) -> str:
    """
    Join 8 fields into LS-DYNA fixed-width line (8×10) + '\\n'.
    If a field is longer than 10 chars it is truncated (preserve format).
    """
    out: List[str] = []
    for f in fields:
        s = (f or "").strip()
        if len(s) > FIELD_WIDTH:
            s = s[:FIELD_WIDTH]
        out.append(s.rjust(FIELD_WIDTH))
    return "".join(out) + "\n"


def is_number(s: str) -> bool:
    try:
        float(s.strip())
        return True
    except ValueError:
        return False


def format_lsdyna_10(v: float) -> str:
    """
    Format numeric value to fit into 10 characters.
    Prefers compact 'g', then 'E'. Last resort: truncate.
    """
    if v == 0.0:
        return "0.0"

    for prec in (9, 8, 7, 6, 5, 4):
        s = f"{v:.{prec}g}"
        if len(s) <= 10:
            return s

    for prec in (4, 3, 2, 1, 0):
        s = f"{v:.{prec}E}"
        if len(s) <= 10:
            return s

    return f"{v:.3E}"[:10]
