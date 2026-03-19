from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from flask import Flask, jsonify, redirect, render_template, request, send_file
from flask_babel import Babel, get_locale, gettext as _

from kunit.api import convert_string, get_unit_descriptors, get_unit_keys, list_models
from kunit.core.units import UnitDescriptor
from kunit.materials_store import (
    MaterialRecord,
    MaterialStore,
    build_materials_export,
    convert_materials,
    parse_structured_material_group_request,
    render_structured_material_groups,
)
from kunit.web.i18n import compile_translations


def _convert_material_records(records: Sequence[MaterialRecord], dst_units: str) -> str:
    return convert_materials(records, dst_units)


def _ordered_unique(values: Sequence[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _select_materials_in_order(
    materials: Sequence[MaterialRecord], requested_ids: Sequence[str]
) -> list[MaterialRecord]:
    by_id = {material.material_id: material for material in materials}
    return [by_id[material_id] for material_id in _ordered_unique(requested_ids) if material_id in by_id]

_PRESSURE_UNIT_EN = {
    "Па": "Pa",
    "кПа": "kPa",
    "МПа": "MPa",
    "ГПа": "GPa",
    "Мбар": "Mbar",
}


def _localize_unit_descriptors(
    units: Sequence[UnitDescriptor], lang: str
) -> List[UnitDescriptor]:
    if lang != "en":
        return list(units)

    localized: List[UnitDescriptor] = []
    for unit in units:
        pressure_unit = _PRESSURE_UNIT_EN.get(unit.pressure_unit, unit.pressure_unit)
        localized.append(
            UnitDescriptor(
                key=unit.key,
                label=f"{unit.key} — {pressure_unit}",
                pressure_unit=pressure_unit,
            )
        )
    return localized


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.setdefault("BABEL_DEFAULT_LOCALE", "ru")

    supported_languages = ("ru", "en")

    package_root = Path(__file__).resolve().parent
    compiled_translations_root = Path(app.instance_path) / "translations"
    compile_translations(
        src_root=package_root / "translations",
        dst_root=compiled_translations_root,
        locales=("en",),
    )
    app.config.setdefault("BABEL_TRANSLATION_DIRECTORIES", str(compiled_translations_root))

    def select_locale() -> str:
        lang = request.cookies.get("lang")
        if lang in supported_languages:
            return lang
        best = request.accept_languages.best_match(list(supported_languages))
        return best or "ru"

    Babel(app, locale_selector=select_locale)

    materials_root = Path(__file__).resolve().parent / "materials"
    materials_store = MaterialStore(materials_root)

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

    def _material_to_api_payload(material: MaterialRecord, lang: str) -> dict[str, object]:
        return {
            "id": material.material_id,
            "name": material.display_name(lang),
            "comment": material.display_comment(lang),
            "tags": list(material.display_tags(lang)),
            "reference": material.reference,
            "models": list(material.models),
            "units": material.units,
            "source": material.source,
        }

    @app.context_processor
    def _inject_i18n():
        lang = str(get_locale())
        return dict(
            lang=lang,
            languages=[
                ("ru", "RU"),
                ("en", "EN"),
            ],
        )

    def _index_context(**kwargs):
        lang = str(get_locale())
        unit_options = _localize_unit_descriptors(get_unit_descriptors(), lang)
        models = list_models()
        unit_labels = {u.key: u.label for u in unit_options}
        base_ctx = dict(
            units=unit_options,
            models=models,
            default_models=models,
            unit_labels=unit_labels,
            custom_transforms="",
        )
        base_ctx.update(kwargs)
        return base_ctx

    def _materials_context(**kwargs):
        lang = str(get_locale())
        unit_options = _localize_unit_descriptors(get_unit_descriptors(), lang)
        unit_labels = {u.key: u.label for u in unit_options}
        materials = materials_store.list_materials()
        material_models = sorted(
            {section.model for m in materials for section in m.sections if section.kind == "material"}
        )
        eos_models = sorted(
            {section.model for m in materials for section in m.sections if section.kind == "eos"}
        )
        base_ctx = dict(
            units=unit_options,
            unit_labels=unit_labels,
            materials=materials,
            material_models=material_models,
            eos_models=eos_models,
        )
        base_ctx.update(kwargs)
        return base_ctx

    @app.post("/lang")
    def set_language():
        lang = request.form.get("lang", type=str) or "ru"
        if lang not in supported_languages:
            lang = "ru"

        next_url = request.form.get("next", type=str) or "/"
        if not next_url.startswith("/"):
            next_url = "/"

        resp = redirect(next_url)
        resp.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
        return resp

    @app.get("/api/v1/materials")
    def api_list_materials():
        lang = str(get_locale())
        materials = [_material_to_api_payload(item, lang) for item in materials_store.list_materials()]
        return jsonify({"materials": materials})

    def _parse_export_request() -> tuple[object, str]:
        if request.method == "GET":
            material_ids = request.args.getlist("material_id")
            dst_units = request.args.get("dst", get_unit_keys()[0])
            return material_ids, str(dst_units)

        data = request.get_json(silent=True) or {}
        return data.get("material_ids"), str(data.get("dst", get_unit_keys()[0]))

    @app.route("/api/v1/materials/export", methods=["GET", "POST"])
    def api_export_materials():
        material_ids, dst_units = _parse_export_request()

        if not isinstance(material_ids, list) or any(not isinstance(m, str) for m in material_ids):
            return jsonify({"error": "material_ids must be a list of strings"}), 400

        selected = _select_materials_in_order(materials_store.list_materials(), material_ids)
        if not selected:
            return jsonify({"error": "No materials matched the provided material_ids"}), 400

        try:
            payload = _convert_material_records(selected, dst_units)
        except Exception as exc:
            return jsonify({"error": f"Material export failed: {exc}"}), 400

        return jsonify(
            {
                "dst": dst_units,
                "count": len(selected),
                "material_ids": [m.material_id for m in selected],
                "payload": payload,
            }
        )

    @app.post("/api/v1/convert")
    def api_convert():
        data = request.get_json(silent=True) or {}
        text = data.get("text")
        src = data.get("src")
        dst = data.get("dst")
        models = data.get("models", "all")
        custom_transforms = data.get("custom_transforms")

        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "text must be a non-empty string"}), 400
        if not isinstance(src, str) or not src:
            return jsonify({"error": "src must be provided"}), 400
        if not isinstance(dst, str) or not dst:
            return jsonify({"error": "dst must be provided"}), 400
        if not (
            models == "all"
            or isinstance(models, str)
            or (isinstance(models, list) and all(isinstance(item, str) for item in models))
        ):
            return jsonify({"error": "models must be 'all', a string, or a list of strings"}), 400

        try:
            converted = convert_string(
                text,
                src=src,
                dst=dst,
                models=models,
                custom_transforms=custom_transforms,
            )
        except Exception as exc:
            return jsonify({"error": f"Conversion failed: {exc}"}), 400

        return jsonify(
            {
                "src": src,
                "dst": dst,
                "models": models,
                "converted": converted,
            }
        )

    @app.get("/")
    def index():
        return render_template("index.html", **_index_context(custom_transforms=""))

    @app.get("/materials")
    def materials_page():
        return render_template(
            "materials.html",
            **_materials_context(materials_out_name="materials.k"),
        )

    @app.post("/convert")
    def convert():
        units = get_unit_descriptors()
        models_all = list_models()
        unit_labels = {u.key: u.label for u in units}

        src = request.form.get("src", type=str)
        dst = request.form.get("dst", type=str)
        out_name = (request.form.get("out_name", type=str) or "converted.k").strip()
        selected_models = request.form.getlist("models") or models_all
        custom_transforms = request.form.get("custom_transforms", type=str) or ""

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
            return (
                render_template(
                    "index.html",
                    **_index_context(
                        error_msg=_("Нужно вставить текст или выбрать файл"),
                        selected_src=src,
                        selected_dst=dst,
                        custom_transforms=custom_transforms,
                    ),
                ),
                400,
            )

        try:
            converted = convert_string(
                text,
                src=src,
                dst=dst,
                models=selected_models,
                custom_transforms=custom_transforms or None,
            )
        except Exception as e:
            return (
                render_template(
                    "index.html",
                    **_index_context(
                        error_msg=_("Ошибка конвертации: %(error)s", error=str(e)),
                        selected_src=src,
                        selected_dst=dst,
                        custom_transforms=custom_transforms,
                    ),
                ),
                400,
            )

        prev = build_preview(text, converted)

        return render_template(
            "result.html",
            src=src,
            dst=dst,
            models=selected_models,
            out_name=out_name,
            preview=prev,
            payload=text,
            converted_text=converted,
            unit_labels=unit_labels,
            custom_transforms=custom_transforms,
        )

    @app.post("/materials/export")
    def export_materials():
        selected_ids = _ordered_unique(request.form.getlist("materials"))
        dst_units = request.form.get("materials_dst", type=str)
        out_name = (request.form.get("materials_out_name", type=str) or "materials.k").strip()
        structured_groups_state = request.form.get("structured_material_groups", type=str) or ""
        selected = _select_materials_in_order(materials_store.list_materials(), selected_ids)

        if not selected:
            return (
                render_template(
                    "materials.html",
                    **_materials_context(
                        materials_error=_("Нужно выбрать хотя бы один материал"),
                        selected_materials=selected_ids,
                        materials_dst=dst_units,
                        materials_out_name=out_name,
                        structured_material_groups=structured_groups_state,
                    ),
                ),
                400,
            )

        try:
            export_result = build_materials_export(selected, dst_units or get_unit_keys()[0])
            try:
                groups_request = parse_structured_material_group_request(
                    structured_groups_state,
                    allowed_material_ids=set(selected_ids),
                )
                maps_payload = render_structured_material_groups(
                    groups_request,
                    export_result.assigned_ids,
                )
            except Exception as e:
                return (
                    render_template(
                        "materials.html",
                        **_materials_context(
                            selected_materials=selected_ids,
                            materials_dst=dst_units,
                            materials_out_name=out_name,
                            structured_material_groups=structured_groups_state,
                            structured_material_groups_error=_(
                                "Ошибка карт multimaterial: %(error)s",
                                error=str(e),
                            ),
                        ),
                    ),
                    400,
                )
            payload = export_result.payload
            if maps_payload:
                payload = f"{payload.rstrip()}\n{maps_payload}"
        except Exception as e:
            return (
                render_template(
                    "materials.html",
                    **_materials_context(
                        materials_error=_("Ошибка экспорта материалов: %(error)s", error=str(e)),
                        selected_materials=selected_ids,
                        materials_dst=dst_units,
                        materials_out_name=out_name,
                        structured_material_groups=structured_groups_state,
                    ),
                ),
                400,
            )

        return render_template(
            "materials.html",
            **_materials_context(
                selected_materials=selected_ids,
                materials_dst=dst_units,
                materials_out_name=out_name,
                structured_material_groups=structured_groups_state,
                materials_export=payload,
            ),
        )

    @app.post("/materials/download")
    def download_materials():
        payload = request.form.get("payload", type=str) or ""
        out_name = (request.form.get("materials_out_name", type=str) or "materials.k").strip()
        buf = io.BytesIO(payload.encode("utf-8"))
        return send_file(
            buf,
            mimetype="text/plain; charset=utf-8",
            as_attachment=True,
            download_name=out_name,
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
            return _("Ошибка конвертации: %(error)s", error=str(e)), 400

        buf = io.BytesIO(converted.encode("utf-8"))
        return send_file(
            buf,
            mimetype="text/plain; charset=utf-8",
            as_attachment=True,
            download_name=out_name,
        )

    return app


app = create_app()
