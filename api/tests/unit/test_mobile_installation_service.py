import re
from uuid import UUID

from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.services.mobile_installation_service import (
    MobileInstallationService,
    generate_display_code,
    normalize_mobile_platform,
)


INSTALLATION_ID = UUID("10000000-0000-4000-8000-000000000001")


def test_normalize_mobile_platform_accepts_known_values_and_falls_back():
    assert normalize_mobile_platform("ios") == "ios"
    assert normalize_mobile_platform("ANDROID") == "android"
    assert normalize_mobile_platform("desktop") == "other"
    assert normalize_mobile_platform(None) == "other"


def test_generate_display_code_uses_six_unambiguous_characters():
    code = generate_display_code()

    assert re.fullmatch(r"[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}", code)


def test_service_ensure_normalizes_platform_and_assigns_display_code():
    repository = MemoryDeviceRepository()
    repository.create_device(DeviceAuthRecord("pecem-01", "hash", "view"))
    service = MobileInstallationService(
        repository,
        code_factory=lambda: "K7M4Q2",
    )

    installation = service.ensure("pecem-01", INSTALLATION_ID, platform="IOS")

    assert installation is not None
    assert installation.platform == "ios"
    assert installation.display_code == "K7M4Q2"


def test_service_retries_display_code_collision_without_partial_installation():
    repository = MemoryDeviceRepository()
    repository.create_device(DeviceAuthRecord("pecem-01", "hash", "view"))
    first = UUID("10000000-0000-4000-8000-000000000010")
    second = UUID("10000000-0000-4000-8000-000000000011")
    repository.ensure_mobile_installation(
        "pecem-01",
        first,
        platform="ios",
        display_code="AAAAAA",
    )
    codes = iter(("AAAAAA", "BBBBBB"))
    service = MobileInstallationService(
        repository,
        code_factory=lambda: next(codes),
    )

    installation = service.ensure("pecem-01", second, platform="android")

    assert installation is not None
    assert installation.display_code == "BBBBBB"
    assert repository.get_mobile_installation("pecem-01", second) == installation
