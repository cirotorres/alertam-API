from __future__ import annotations

from app.core.errors import (
    CloudBindingNotFoundError,
    CloudRealmUnauthorizedError,
    PersistenceUnavailableApiError,
)
from app.models.cloud_binding import (
    CloudBindingCredentialRequest,
    CloudBindingEnsureRequest,
    CloudBindingResponse,
)
from app.repositories.cloud_bindings import (
    CloudBindingRecord,
    CloudBindingsRepository,
)
from app.repositories.devices import DevicesRepository, PersistenceUnavailableError
from app.security.credentials import hash_secret


class CloudBindingService:
    def __init__(
        self,
        repository: DevicesRepository & CloudBindingsRepository,
    ) -> None:
        self._repository = repository

    def get(self, device_id: str) -> CloudBindingResponse:
        try:
            bindings = self._repository.list_cloud_bindings(device_id)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if not bindings:
            raise CloudBindingNotFoundError()
        return self._response(device_id, bindings[-1])

    def ensure(
        self,
        device_id: str,
        request: CloudBindingEnsureRequest,
    ) -> CloudBindingResponse:
        self._require_authority(device_id, request.realm_id)
        credential_hash = hash_secret(request.credential.get_secret_value())
        try:
            binding = self._repository.ensure_cloud_binding(
                device_id,
                request.realm_id,
                credential_hash,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if binding is None:
            raise CloudRealmUnauthorizedError()
        return self._response(device_id, binding)

    def rotate(
        self,
        device_id: str,
        request: CloudBindingCredentialRequest,
    ) -> CloudBindingResponse:
        binding = self._active_binding(device_id)
        self._require_authority(device_id, binding.realm_id)
        credential_hash = hash_secret(request.credential.get_secret_value())
        try:
            rotated = self._repository.rotate_cloud_binding(
                device_id,
                credential_hash,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if rotated is None:
            raise CloudRealmUnauthorizedError()
        return self._response(device_id, rotated)

    def revoke(self, device_id: str) -> CloudBindingResponse:
        binding = self._latest_binding(device_id)
        self._require_authority(device_id, binding.realm_id)
        try:
            revoked = self._repository.revoke_cloud_binding(device_id)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if revoked is None:
            raise CloudRealmUnauthorizedError()
        return self._response(device_id, revoked)

    def _active_binding(self, device_id: str) -> CloudBindingRecord:
        try:
            binding = self._repository.get_active_cloud_binding(device_id)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if binding is None:
            raise CloudBindingNotFoundError()
        return binding

    def _latest_binding(self, device_id: str) -> CloudBindingRecord:
        try:
            bindings = self._repository.list_cloud_bindings(device_id)
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if not bindings:
            raise CloudBindingNotFoundError()
        return bindings[-1]

    def _require_authority(self, device_id: str, realm_id: str) -> None:
        try:
            device = self._repository.get_device_auth(device_id)
            realm = self._repository.get_webpilot_auth_realm(realm_id)
            authorization = self._repository.get_realm_device_authorization(
                realm_id,
                device_id,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        if (
            device is None
            or not device.enabled
            or realm is None
            or not realm.active
            or authorization is None
            or not authorization.active
        ):
            raise CloudRealmUnauthorizedError()

    def _response(
        self,
        device_id: str,
        binding: CloudBindingRecord,
    ) -> CloudBindingResponse:
        try:
            device = self._repository.get_device_auth(device_id)
            realm = self._repository.get_webpilot_auth_realm(binding.realm_id)
            authorization = self._repository.get_realm_device_authorization(
                binding.realm_id,
                device_id,
            )
        except PersistenceUnavailableError as exc:
            raise PersistenceUnavailableApiError() from exc
        device_enabled = bool(device and device.enabled)
        realm_authorized = bool(
            realm
            and realm.active
            and authorization
            and authorization.active
        )
        return CloudBindingResponse(
            cloud_binding_id=binding.cloud_binding_id,
            device_id=binding.device_id,
            realm_id=binding.realm_id,
            credential_version=binding.credential_version,
            status=binding.status,
            device_enabled=device_enabled,
            realm_authorized=realm_authorized,
            usable=(
                binding.status.value == "active"
                and device_enabled
                and realm_authorized
            ),
        )
