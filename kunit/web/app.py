from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

from flask import Flask, render_template, request, send_file

from kunit.api import convert_string, get_unit_keys, list_models


def create_app() -> Flask:
    app = Flask(__name__)

    @dataclass
    class Preview:
        changed_lines: int
        before_snippet: str
        after_snippet: str

    def build_preview(before: str, after: str, max_lines: int = 60) -> Preview:
        before_lines = before.splitlines()
        after_lines = after.splitlines()
        changed = 0
        for b, a in zip(before_lines, after_lines):
            if b != a:
                changed += 1
        # limit snippets to first max_lines lines to keep page light
        return Preview(
            changed_lines=changed,
            before_snippet="\n".join(before_lines[:max_lines]),
            after_snippet="\n".join(after_lines[:max_lines]),
        )

    @app.get("/")
    def index():
        units = get_unit_keys()
        models = list_models()
        return render_template(
            "index.html",
            units=units,
            models=models,
            default_models=models,
        )

    @app.post("/convert")
    def convert():
        units = get_unit_keys()
        models_all = list_models()

        src = request.form.get("src", type=str)
        dst = request.form.get("dst", type=str)
        out_name = (request.form.get("out_name", type=str) or "converted.k").strip()
        selected_models = request.form.getlist("models") or models_all

        # prefer pasted text over uploaded file if present
        pasted_text = request.form.get("text_input", type=str) or ""
        file_storage = request.files.get("file_input")
        text: Optional[str] = None
        if pasted_text.strip():
            text = pasted_text
        elif file_storage and file_storage.filename:
            text = file_storage.stream.read().decode("utf-8", errors="replace")

        if not text:
            # render with error message
            return render_template(
                "index.html",
                units=units,
                models=models_all,
                default_models=models_all,
                error_msg="Нужно вставить текст или выбрать файл",
            ), 400

        try:
            converted = convert_string(text, src=src, dst=dst, models=selected_models)
        except Exception as e:
            return render_template(
                "index.html",
                units=units,
                models=models_all,
                default_models=models_all,
                error_msg=f"Ошибка конвертации: {e}",
            ), 400

        prev = build_preview(text, converted)

        return render_template(
            "result.html",
            src=src,
            dst=dst,
            models=selected_models,
            out_name=out_name,
            preview=prev,
            payload=text,
        )

    @app.post("/download")
    def download():
        # Re-run conversion deterministically from posted payload; do not store files
        src = request.form.get("src", type=str)
        dst = request.form.get("dst", type=str)
        out_name = (request.form.get("out_name", type=str) or "converted.k").strip()
        models = request.form.getlist("models") or list_models()
        payload = request.form.get("payload", type=str) or ""
        try:
            converted = convert_string(payload, src=src, dst=dst, models=models)
        except Exception as e:
            # fall back to text response with error
            return f"Ошибка конвертации: {e}", 400

        buf = io.BytesIO(converted.encode("utf-8"))
        return send_file(
            buf,
            mimetype="text/plain; charset=utf-8",
            as_attachment=True,
            download_name=out_name,
        )

    return app


app = create_app()

