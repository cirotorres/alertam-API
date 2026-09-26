from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.snapshots import create_snapshot_router
from app.core.errors import ApiError
from app.repositories.devices import DevicesRepository
from app.repositories.memory import MemoryDeviceRepository


def create_app(
    repository: DevicesRepository | None = None,
) -> FastAPI:
    application = FastAPI(
        title="AlertaM Mobile API",
        version="0.1.0",
    )
    devices_repository = repository or MemoryDeviceRepository()
    application.include_router(
        create_snapshot_router(devices_repository)
    )

    @application.exception_handler(ApiError)
    async def handle_api_error(
        request: Request,
        exc: ApiError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ):
        for error in exc.errors():
            if (
                error.get("loc") == ("body", "schema_version")
                and error.get("type") == "literal_error"
            ):
                return JSONResponse(
                    status_code=422,
                    content={
                        "detail": {
                            "code": "unsupported_snapshot_schema",
                            "message": "Versão de snapshot não suportada.",
                        }
                    },
                )
        return await request_validation_exception_handler(request, exc)

    return application


app = create_app()
