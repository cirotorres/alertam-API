from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    return FastAPI(
        title="AlertaM Mobile API",
        version="0.1.0",
    )


app = create_app()
