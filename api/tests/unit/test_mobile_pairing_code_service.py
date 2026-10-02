from datetime import datetime, timedelta, timezone
import re

import pytest

from app.core.errors import (
    InvalidMobilePairingCodeError,
    MobilePairingCodeRateLimitedError,
)
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret
from app.services.device_auth import AuthenticatedDevice
from app.services.mobile_pairing_code_service import MobilePairingCodeService


NOW = datetime(2026, 10, 2, 17, 0, tzinfo=timezone.utc)


def repo() -> MemoryDeviceRepository:
    item = MemoryDeviceRepository(clock=lambda: NOW)
    item.create_device(
        DeviceAuthRecord(
            "pecem-01",
            hash_secret("device-secret"),
            hash_secret("V" * 43),
        )
    )
    return item


def test_issue_uses_six_digits_and_expires_in_five_minutes():
    service = MobilePairingCodeService(
        repo(),
        clock=lambda: NOW,
        code_factory=lambda: "483721",
    )

    issued = service.issue_for_device(
        AuthenticatedDevice("pecem-01")
    )

    assert issued.code == "483721"
    assert re.fullmatch(r"\d{6}", issued.code)
    assert issued.expires_at == NOW + timedelta(minutes=5)


def test_redeem_accepts_display_spacing_and_returns_short_lived_ticket():
    repository = repo()
    service = MobilePairingCodeService(
        repository,
        clock=lambda: NOW,
        code_factory=lambda: "483721",
        ticket_factory=lambda: "ticket-secret",
    )
    service.issue_for_device(AuthenticatedDevice("pecem-01"))

    redeemed = service.redeem("483 721")

    assert redeemed.device_id == "pecem-01"
    assert redeemed.ticket == "ticket-secret"
    assert redeemed.expires_at == NOW + timedelta(minutes=5)


def test_code_is_single_redeem_and_new_issue_invalidates_previous():
    repository = repo()
    codes = iter(("111111", "222222"))
    service = MobilePairingCodeService(
        repository,
        clock=lambda: NOW,
        code_factory=lambda: next(codes),
        ticket_factory=lambda: "ticket-a",
    )
    service.issue_for_device(AuthenticatedDevice("pecem-01"))
    service.issue_for_device(AuthenticatedDevice("pecem-01"))

    with pytest.raises(InvalidMobilePairingCodeError):
        service.redeem("111111")

    service.redeem("222222")
    with pytest.raises(InvalidMobilePairingCodeError):
        service.redeem("222222")


def test_invalid_attempts_are_rate_limited():
    repository = repo()
    service = MobilePairingCodeService(repository, clock=lambda: NOW)

    for _ in range(30):
        with pytest.raises(InvalidMobilePairingCodeError):
            service.redeem("999999")

    with pytest.raises(MobilePairingCodeRateLimitedError):
        service.redeem("999999")
