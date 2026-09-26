from __future__ import annotations

from fastapi import FastAPI

from app.main import create_app


def test_create_app_builds_fastapi_without_external_connections():
    application = create_app()

    assert isinstance(application, FastAPI)
    assert application.title == "AlertaM Mobile API"
