from __future__ import annotations

import pytest

from app.core.errors import InvalidDeviceCredentialsError, InvalidViewSecretError
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret, verify_secret
from app.services.access_service import AccessService


DEVICE_ID = "pecem-01"
DEVICE_SECRET = "device-secret"
VIEW_SECRET_A = "A" * 43
VIEW_SECRET_B = "B" * 43


def _repo() -> MemoryDeviceRepository:
    repo = MemoryDeviceRepository()
    repo.create_device(
        DeviceAuthRecord(
            device_id=DEVICE_ID,
            device_secret_hash=hash_secret(DEVICE_SECRET),
        )
    )
    return repo


def test_invalid_device_credentials_are_rejected():
    service = AccessService(_repo())

    with pytest.raises(InvalidDeviceCredentialsError):
        service.rotate_view_secret(
            DEVICE_ID,
            "wrong-secret",
            VIEW_SECRET_A,
        )

@pytest.mark.parametrize(
    "view_secret",
    [
        "short",
        "A" * 42,
        ("A" * 42) + "!",
        ("A" * 42) + " ",
    ],
)
def test_view_secret_requires_base64url_shape_and_minimum_length(view_secret):
    service = AccessService(_repo())

    with pytest.raises(InvalidViewSecretError) as exc:
        service.rotate_view_secret(
            DEVICE_ID,
            DEVICE_SECRET,
            view_secret,
        )

    assert view_secret not in str(exc.value)


def test_repository_receives_only_view_secret_hash():
    repo = _repo()
    service = AccessService(repo)

    service.rotate_view_secret(
        DEVICE_ID,
        DEVICE_SECRET,
        VIEW_SECRET_A,
    )

    stored = repo.get_device_auth(DEVICE_ID)
    assert stored.view_secret_hash == hash_secret(VIEW_SECRET_A)
    assert VIEW_SECRET_A not in repr(stored)

def test_rotation_invalidates_previous_view_secret_immediately():
    repo = _repo()
    service = AccessService(repo)
    service.rotate_view_secret(
        DEVICE_ID,
        DEVICE_SECRET,
        VIEW_SECRET_A,
    )
    first_hash = repo.get_device_auth(DEVICE_ID).view_secret_hash

    service.rotate_view_secret(
        DEVICE_ID,
        DEVICE_SECRET,
        VIEW_SECRET_B,
    )

    current_hash = repo.get_device_auth(DEVICE_ID).view_secret_hash
    assert current_hash != first_hash
    assert verify_secret(VIEW_SECRET_A, current_hash) is False
    assert verify_secret(VIEW_SECRET_B, current_hash) is True
