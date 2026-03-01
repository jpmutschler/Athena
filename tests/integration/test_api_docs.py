"""Integration tests for API documentation and OpenAPI schema."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("SWITCHTEC_API_KEY", "test-key")


@pytest.fixture
def app():
    from serialcables_switchtec.api.app import create_app

    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app, headers={"X-API-Key": "test-key"})


class TestOpenApiSchema:
    """OpenAPI schema validation tests."""

    def test_openapi_json_returns_200(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_openapi_json_is_valid(self, client):
        response = client.get("/openapi.json")
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

    def test_openapi_has_title(self, client):
        schema = client.get("/openapi.json").json()
        assert schema["info"]["title"] == "Athena API"

    def test_openapi_has_version(self, client):
        schema = client.get("/openapi.json").json()
        assert schema["info"]["version"] == "0.1.0"

    def test_all_tags_have_metadata(self, client):
        schema = client.get("/openapi.json").json()
        tags = schema.get("tags", [])
        tag_names = {t["name"] for t in tags}
        expected_tags = {
            "devices", "ports", "diagnostics", "firmware",
            "evcntr", "events", "fabric", "mrpc", "osa",
            "performance", "monitor",
        }
        assert expected_tags.issubset(tag_names), (
            f"Missing tags: {expected_tags - tag_names}"
        )

    def test_tags_have_descriptions(self, client):
        schema = client.get("/openapi.json").json()
        tags = schema.get("tags", [])
        for tag in tags:
            assert "description" in tag and tag["description"], (
                f"Tag '{tag['name']}' missing description"
            )


class TestDocsEndpoints:
    """Swagger UI and ReDoc endpoint tests."""

    def test_swagger_ui_returns_200(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_returns_200(self, client):
        response = client.get("/redoc")
        assert response.status_code == 200
