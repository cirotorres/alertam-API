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


class OutOfOrderSnapshotError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="out_of_order_snapshot",
            message="Snapshot fora de ordem.",
        )


class SequenceReuseMismatchError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="sequence_reuse_mismatch",
            message="Sequência reutilizada com conteúdo diferente.",
        )


class PersistenceUnavailableApiError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            code="persistence_unavailable",
            message="Persistência temporariamente indisponível.",
        )


class InvalidViewSecretError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            code="invalid_view_secret",
            message="Segredo de leitura inválido.",
        )


class SnapshotNotAvailableError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            code="snapshot_not_available",
            message="Ainda não há snapshot disponível.",
        )


class VesselNotInSnapshotError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            code="vessel_not_in_snapshot",
            message="Navio não está disponível no snapshot atual.",
        )


class VesselPhotoUnavailableError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            code="vessel_photo_unavailable",
            message="Foto do navio temporariamente indisponível.",
        )
