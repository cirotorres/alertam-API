from __future__ import annotations

from app.core.errors import (
    InvalidDeviceCredentialsError,
    InvalidViewCredentialsError,
)


def test_device_credentials_error_has_stable_public_detail():
    error = InvalidDeviceCredentialsError()

    assert error.status_code == 401
    assert error.detail == {
        "code": "invalid_device_credentials",
        "message": "Credenciais do dispositivo inválidas.",
    }


def test_view_credentials_error_has_stable_public_detail():
    error = InvalidViewCredentialsError()

    assert error.status_code == 401
    assert error.detail == {
        "code": "invalid_view_credentials",
        "message": "Credenciais de leitura inválidas.",
    }
