from __future__ import annotations

import click
from pathlib import Path
from typing import List, Optional

from kunit.api import convert_string, get_unit_keys, list_models


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """LS-DYNA unit converter (fixed-width aware)."""
    pass


@cli.command("convert")
@click.argument("input", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--src", required=True, type=click.Choice(get_unit_keys()))
@click.option("--dst", required=True, type=click.Choice(get_unit_keys()))
@click.option(
    "--models",
    default="all",
    help=(
        "Comma-separated list: mat-jc,eos-gruneisen,eos-ignition-growth,"
        "eos-jwl,mat-he-burn or 'all'."
    ),
)
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path))
def convert_cmd(
    input: Path, src: str, dst: str, models: str, output: Optional[Path]
) -> None:
    # Validate/parse models for consistent UX and messages
    if models.strip().lower() == "all":
        model_arg: str | list[str] = "all"
        model_names: list[str] = list_models()
    else:
        names = [m.strip() for m in models.split(",") if m.strip()]
        known = set(list_models())
        unknown = [n for n in names if n not in known]
        if unknown:
            raise click.UsageError(
                f"Unknown models: {unknown}. Known: {sorted(known)}"
            )
        model_arg = names
        model_names = names

    text = input.read_text(encoding="utf-8", errors="replace")
    converted = convert_string(text, src=src, dst=dst, models=model_arg)

    out_path = output or input.with_suffix(input.suffix + f".{dst}.k")
    out_path.write_text(converted, encoding="utf-8")

    click.echo(f"✔ Converted: {input} → {out_path}")
    click.echo(f"  Units: {src} → {dst}")
    click.echo(f"  Models: {', '.join(model_names)}")


@cli.command("list-models")
def list_models_cmd() -> None:
    for name in list_models():
        click.echo(name)


if __name__ == "__main__":
    cli()
