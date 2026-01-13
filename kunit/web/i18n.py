from __future__ import annotations

from pathlib import Path
from typing import Iterable

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po


def compile_translations(
    *,
    src_root: Path,
    dst_root: Path,
    locales: Iterable[str],
    domain: str = "messages",
) -> None:
    """Compile .po files from src_root into .mo files under dst_root.

    This keeps the repository text-only (we commit .po), while the app runs off compiled .mo files.
    """

    for locale in locales:
        po_path = src_root / locale / "LC_MESSAGES" / f"{domain}.po"
        if not po_path.exists():
            continue

        mo_dir = dst_root / locale / "LC_MESSAGES"
        mo_dir.mkdir(parents=True, exist_ok=True)
        mo_path = mo_dir / f"{domain}.mo"

        if mo_path.exists() and mo_path.stat().st_mtime >= po_path.stat().st_mtime:
            continue

        with po_path.open("r", encoding="utf-8") as f:
            catalog = read_po(f, locale=locale, domain=domain)
        with mo_path.open("wb") as f:
            write_mo(f, catalog)
