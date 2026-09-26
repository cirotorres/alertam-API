from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app as application_app
from main import app as vercel_app


ROOT = Path(__file__).parents[3]
VERCEL_CONFIG = ROOT / "vercel.json"


def _vercel_config() -> dict:
    return json.loads(VERCEL_CONFIG.read_text(encoding="utf-8"))


def test_vercel_entrypoint_exports_same_fastapi_app():
    assert isinstance(vercel_app, FastAPI)
    assert vercel_app is application_app

    response = TestClient(vercel_app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_vercel_services_config_points_to_same_fastapi_entrypoint():
    config = _vercel_config()

    assert config["$schema"] == "https://openapi.vercel.sh/vercel.json"
    assert config["services"]["api"] == {
        "root": "api/",
        "entrypoint": "main:app",
    }
    assert config["services"]["frontend"] == {
        "root": "frontend/",
    }
    assert config["rewrites"] == [
        {
            "source": "/api/v1/:path*",
            "destination": {"service": "api"},
        },
        {
            "source": "/:path*",
            "destination": {"service": "frontend"},
        },
    ]


def test_vercel_config_never_contains_server_credentials():
    raw = VERCEL_CONFIG.read_text(encoding="utf-8")

    assert "SUPABASE_SECRET_KEY" not in raw
    assert "SUPABASE_SERVICE_ROLE_KEY" not in raw
    assert "sb_secret_" not in raw
