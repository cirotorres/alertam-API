from __future__ import annotations


class ApiError(Exception):
    status_code: int
    code: str
    message: str

    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)

    @property
    def detail(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
        }


class InvalidDeviceCredentialsError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            code="invalid_device_credentials",
            message="Credenciais do dispositivo inválidas.",
        )


class InvalidViewCredentialsError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            code="invalid_view_credentials",
            message="Credenciais de leitura inválidas.",
        )
