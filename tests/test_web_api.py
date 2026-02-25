from __future__ import annotations

from kunit.web.app import create_app


def _client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


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
