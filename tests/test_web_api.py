from __future__ import annotations

import html
import json
import re
from pathlib import Path

from werkzeug.datastructures import MultiDict

from kunit.core.fixed import format_lsdyna_10, join_fixed
from kunit.materials_store import MaterialRecord, MaterialSection
from kunit.web.app import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _fixed_line(values):
    return join_fixed([format_lsdyna_10(v) for v in values])


def test_tailwind_pipeline_has_npm_build_script():
    package_json = PROJECT_ROOT / "package.json"

    data = json.loads(package_json.read_text(encoding="utf-8"))

    assert data["scripts"]["build:css"] == (
        "tailwindcss -i ./kunit/web/assets/css/tailwind.css "
        "-o ./kunit/web/static/css/app.css --minify"
    )
    assert data["scripts"]["watch:css"] == (
        "tailwindcss -i ./kunit/web/assets/css/tailwind.css "
        "-o ./kunit/web/static/css/app.css --watch"
    )
    assert "@tailwindcss/cli" in data["devDependencies"]
    assert "tailwindcss" in data["devDependencies"]


def test_tailwind_source_scans_jinja_templates():
    source = (PROJECT_ROOT / "kunit/web/assets/css/tailwind.css").read_text(
        encoding="utf-8"
    )

    assert '@import "tailwindcss";' in source
    assert '@source "../../templates";' in source


def test_web_pages_use_local_stylesheet_instead_of_tailwind_cdn():
    client = _client()
    text = (
        "*MAT_JOHNSON_COOK\n"
        "$#     mid        ro         e        pr\n"
        "        1       7.8   210000.0      0.29\n"
    )

    responses = [
        client.get("/"),
        client.get("/materials"),
        client.post(
            "/convert",
            data={
                "text_input": text,
                "src": "mm-mg-us",
                "dst": "m-kg-s",
                "models": ["mat-jc"],
                "out_name": "converted.k",
            },
        ),
    ]

    for resp in responses:
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "cdn.tailwindcss.com" not in body
        assert 'href="/static/css/app.css"' in body


def test_local_stylesheet_is_served():
    client = _client()

    resp = client.get("/static/css/app.css")

    assert resp.status_code == 200
    assert "text/css" in resp.content_type
    css = resp.get_data(as_text=True)
    assert "tailwindcss v" in css
    assert ".bg-slate-50" in css


def test_api_list_materials_returns_records():
    client = _client()

    resp = client.get("/api/v1/materials")

    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    assert isinstance(data.get("materials"), list)
    assert data["materials"]
    first = data["materials"][0]
    assert "id" in first
    assert "models" in first


def test_api_export_materials_returns_payload():
    client = _client()

    materials = client.get("/api/v1/materials").get_json()["materials"]
    selected_id = materials[0]["id"]

    resp = client.post(
        "/api/v1/materials/export",
        json={"material_ids": [selected_id], "dst": "m-kg-s"},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 1
    assert data["material_ids"] == [selected_id]
    assert isinstance(data["payload"], str)
    assert data["payload"].strip()


def test_api_export_materials_supports_get_query_params():
    client = _client()

    materials = client.get("/api/v1/materials").get_json()["materials"]
    selected_id = materials[0]["id"]

    resp = client.get(
        "/api/v1/materials/export",
        query_string={"material_id": [selected_id], "dst": "m-kg-s"},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 1
    assert data["material_ids"] == [selected_id]
    assert isinstance(data["payload"], str)
    assert data["payload"].strip()


def test_api_convert_returns_converted_text():
    client = _client()

    text = (
        "*MAT_JOHNSON_COOK\n"
        "$#     mid        ro         e        pr\n"
        "        1       7.8   210000.0      0.29\n"
    )

    resp = client.post(
        "/api/v1/convert",
        json={
            "text": text,
            "src": "mm-mg-us",
            "dst": "m-kg-s",
            "models": ["mat-jc"],
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["src"] == "mm-mg-us"
    assert data["dst"] == "m-kg-s"
    assert isinstance(data["converted"], str)
    assert data["converted"].strip()


def test_api_convert_validates_payload():
    client = _client()

    resp = client.post(
        "/api/v1/convert",
        json={"text": "", "src": "mm-mg-us", "dst": "m-kg-s"},
    )

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "text must be a non-empty string"


def test_materials_export_preserves_posted_selection_order(monkeypatch):
    class FakeStore:
        def __init__(self, root):
            self.root = root

        def list_materials(self):
            return [
                MaterialRecord(
                    material_id="alpha",
                    name="Alpha",
                    model="mat-jc",
                    units="mm-mg-us",
                    payload="*MAT_JOHNSON_COOK\n",
                    models=["mat-jc"],
                    comment="Description",
                    tags=["alpha"],
                    name_i18n={"ru": "Alpha", "en": "Alpha"},
                    comment_i18n={"ru": "Description", "en": "Description"},
                    tags_i18n={"ru": ["alpha"], "en": ["alpha"]},
                    sections=[
                        MaterialSection(
                            kind="material",
                            model="mat-jc",
                            units="mm-mg-us",
                            payload=(
                                "*MAT_JOHNSON_COOK\n"
                                "$#     mid        ro         a         b         n         c         m    tmelt\n"
                                f"{_fixed_line([91, 7.1, 500.0, 10.0, 0.2, 0.01, 1.0, 800.0])}\n"
                            ),
                        )
                    ],
                ),
                MaterialRecord(
                    material_id="beta",
                    name="Beta",
                    model="mat-jc",
                    units="mm-mg-us",
                    payload="*MAT_JOHNSON_COOK\n",
                    models=["mat-jc"],
                    comment="Description",
                    tags=["beta"],
                    name_i18n={"ru": "Beta", "en": "Beta"},
                    comment_i18n={"ru": "Description", "en": "Description"},
                    tags_i18n={"ru": ["beta"], "en": ["beta"]},
                    sections=[
                        MaterialSection(
                            kind="material",
                            model="mat-jc",
                            units="mm-mg-us",
                            payload=(
                                "*MAT_JOHNSON_COOK\n"
                                "$#     mid        ro         a         b         n         c         m    tmelt\n"
                                f"{_fixed_line([92, 8.2, 600.0, 20.0, 0.3, 0.02, 1.1, 900.0])}\n"
                            ),
                        )
                    ],
                ),
            ]

    monkeypatch.setattr("kunit.web.app.MaterialStore", FakeStore)
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    resp = client.post(
        "/materials/export",
        data=MultiDict([
            ("materials", "beta"),
            ("materials", "alpha"),
            ("materials_dst", "mm-mg-us"),
        ]),
    )

    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    match = re.search(r'<textarea id="materials-output"[^>]*>(.*?)</textarea>', body, re.S)
    assert match is not None
    payload = html.unescape(match.group(1))
    lines = payload.splitlines()

    first_keyword = lines.index("*MAT_JOHNSON_COOK")
    second_keyword = lines.index("*MAT_JOHNSON_COOK", first_keyword + 1)

    assert lines[first_keyword + 2][:10].strip() == "1"
    assert lines[first_keyword + 2][10:20].strip() == format_lsdyna_10(8.2).strip()
    assert lines[second_keyword + 2][:10].strip() == "2"
    assert lines[second_keyword + 2][10:20].strip() == format_lsdyna_10(7.1).strip()


def test_materials_export_appends_structured_multi_material_groups(monkeypatch):
    class FakeStore:
        def __init__(self, root):
            self.root = root

        def list_materials(self):
            return [
                MaterialRecord(
                    material_id="he",
                    name="HE",
                    model="mat-he-burn",
                    units="mm-mg-us",
                    payload="*MAT_HIGH_EXPLOSIVE_BURN\n",
                    models=["mat-he-burn", "eos-jwl"],
                    comment="Description",
                    tags=["he"],
                    name_i18n={"ru": "HE", "en": "HE"},
                    comment_i18n={"ru": "Description", "en": "Description"},
                    tags_i18n={"ru": ["he"], "en": ["he"]},
                    sections=[
                        MaterialSection(
                            kind="material",
                            model="mat-he-burn",
                            units="mm-mg-us",
                            payload=(
                                "*MAT_HIGH_EXPLOSIVE_BURN\n"
                                "$#     mid        ro         d       pcj      beta         k         g      sigy\n"
                                f"{_fixed_line([90, 1.8, 2.0, 3.0, 0.0, 0.0, 0.0, 4.0])}\n"
                            ),
                        ),
                        MaterialSection(
                            kind="eos",
                            model="eos-jwl",
                            units="mm-mg-us",
                            payload=(
                                "*EOS_JWL\n"
                                "$#   eosid         a         b        r1        r2      omeg        e0        vo\n"
                                f"{_fixed_line([190, 10.0, 20.0, 1.0, 2.0, 3.0, 60.0, 0.5])}\n"
                            ),
                        ),
                    ],
                )
            ]

    monkeypatch.setattr("kunit.web.app.MaterialStore", FakeStore)
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    resp = client.post(
        "/materials/export",
        data=MultiDict([
            ("materials", "he"),
            ("materials_dst", "mm-mg-us"),
            (
                "structured_material_groups",
                json.dumps(
                    {
                        "blocks": [
                            {
                                "type": "3D",
                                "rows": [
                                    {"ammgnm": "HE", "material_id": "he", "pref": ""},
                                ],
                            }
                        ]
                    }
                ),
            ),
        ]),
    )

    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    match = re.search(r'<textarea id="materials-output"[^>]*>(.*?)</textarea>', body, re.S)
    assert match is not None
    payload = html.unescape(match.group(1))

    assert payload.index("*MAT_HIGH_EXPLOSIVE_BURN") < payload.index("*ALE_STRUCTURED_MULTI-MATERIAL_GROUP")
    assert "*ALE_STRUCTURED_MULTI-MATERIAL_GROUP\n" in payload
    assert "        HE         1         1" in payload
    assert 'id="materials-output-preview"' not in body


def test_materials_page_renders_structured_multi_material_group_controls():
    client = _client()

    resp = client.get("/materials")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'name="structured_material_groups"' in body
    assert "Добавить карты `*STRUCTURED_MULTI-MATERIAL_GROUP`" in body
    assert 'id="structured-groups-modal"' in body
    assert "Добавить блок" not in body


def test_materials_page_uses_roomier_export_sidebar_layout():
    client = _client()

    resp = client.get("/materials")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'lg:grid-cols-[minmax(0,1.55fr)_minmax(26rem,28rem)]' in body


def test_materials_page_stacks_export_sidebar_actions():
    client = _client()

    resp = client.get("/materials")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'class="flex flex-col gap-3"' in body
    assert 'class="flex flex-col items-start gap-2"' in body


def test_materials_export_uses_same_light_textarea_style_as_converter():
    client = _client()

    materials = client.get("/api/v1/materials").get_json()["materials"]
    selected_id = materials[0]["id"]

    resp = client.post(
        "/materials/export",
        data=MultiDict([
            ("materials", selected_id),
            ("materials_dst", "m-kg-s"),
        ]),
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    match = re.search(r'<textarea id="materials-output"[^>]*class="([^"]*)"', body)
    assert match is not None
    classes = match.group(1)
    assert "bg-white" in classes


def test_materials_export_preserves_structured_group_state_on_error(monkeypatch):
    class FakeStore:
        def __init__(self, root):
            self.root = root

        def list_materials(self):
            return [
                MaterialRecord(
                    material_id="alpha",
                    name="Alpha",
                    model="mat-jc",
                    units="mm-mg-us",
                    payload="*MAT_JOHNSON_COOK\n",
                    models=["mat-jc"],
                    comment="Description",
                    tags=["alpha"],
                    name_i18n={"ru": "Alpha", "en": "Alpha"},
                    comment_i18n={"ru": "Description", "en": "Description"},
                    tags_i18n={"ru": ["alpha"], "en": ["alpha"]},
                    sections=[
                        MaterialSection(
                            kind="material",
                            model="mat-jc",
                            units="mm-mg-us",
                            payload=(
                                "*MAT_JOHNSON_COOK\n"
                                "$#     mid        ro         a         b         n         c         m    tmelt\n"
                                f"{_fixed_line([91, 7.1, 500.0, 10.0, 0.2, 0.01, 1.0, 800.0])}\n"
                            ),
                        )
                    ],
                )
            ]

    state = json.dumps(
        {
            "blocks": [
                {
                    "type": "3D",
                    "rows": [
                        {"ammgnm": "BETA", "material_id": "beta", "pref": ""},
                    ],
                }
            ]
        }
    )

    monkeypatch.setattr("kunit.web.app.MaterialStore", FakeStore)
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    resp = client.post(
        "/materials/export",
        data=MultiDict([
            ("materials", "alpha"),
            ("materials_dst", "mm-mg-us"),
            ("structured_material_groups", state),
        ]),
    )

    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "selected material outside the export set" in body
    match = re.search(r'name="structured_material_groups"[^>]*value="([^"]*)"', body, re.S)
    assert match is not None
    assert html.unescape(match.group(1)) == state
