from __future__ import annotations

from pathlib import Path

import pytest


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSupabaseClient:
    def __init__(self, rows=None):
        self.rows = [] if rows is None else rows
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url, *, headers, params):
        self.calls.append(("GET", url, {"headers": headers, "params": params}))
        return FakeResponse(self.rows)


def test_load_prepared_identity_requires_exact_three_mobile_values(tmp_path: Path):
    from scripts.admin_device import load_prepared_identity

    complete = tmp_path / "identity.env"
    complete.write_text(
        "# Provisionamento mobile AlertaM\n"
        "ALERTAM_API_BASE_URL=https://alertam-api.vercel.app\n"
        "ALERTAM_DEVICE_ID=pecem-a1b2c3d4\n"
        "ALERTAM_DEVICE_SECRET=device-secret\n",
        encoding="utf-8",
    )

    identity = load_prepared_identity(complete)

    assert identity.api_base_url == "https://alertam-api.vercel.app"
    assert identity.device_id == "pecem-a1b2c3d4"
    assert identity.device_secret == "device-secret"

    missing = tmp_path / "partial.env"
    missing.write_text(
        "ALERTAM_API_BASE_URL=https://alertam-api.vercel.app\n"
        "ALERTAM_DEVICE_ID=pecem-a1b2c3d4\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ALERTAM_DEVICE_SECRET"):
        load_prepared_identity(missing)

    extra = tmp_path / "extra.env"
    extra.write_text(
        "ALERTAM_API_BASE_URL=https://alertam-api.vercel.app\n"
        "ALERTAM_DEVICE_ID=pecem-a1b2c3d4\n"
        "ALERTAM_DEVICE_SECRET=device-secret\n"
        "UNRELATED=value\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="somente"):
        load_prepared_identity(extra)


def test_prepared_identity_repr_never_contains_secret():
    from scripts.admin_device import PreparedDeviceIdentity

    identity = PreparedDeviceIdentity(
        api_base_url="https://alertam-api.vercel.app",
        device_id="pecem-a1b2c3d4",
        device_secret="secret-that-must-not-appear",
    )

    assert "secret-that-must-not-appear" not in repr(identity)
    assert "pecem-a1b2c3d4" in repr(identity)


def test_prepare_writes_new_identity_without_touching_other_env(tmp_path: Path):
    from scripts.admin_device import prepare_new_identity

    output = tmp_path / "attempt" / "identity.env"
    admin_env = tmp_path / ".env"
    admin_env.write_bytes(b"ADMIN_SENTINEL=unchanged\n")
    client = FakeSupabaseClient(rows=[])

    identity = prepare_new_identity(
        output,
        api_base_url="https://alertam-api.vercel.app",
        device_prefix="pecem",
        client=client,
        supabase_url="https://project.supabase.co",
        server_key="sb_secret_admin",
        secret_factory=lambda size: "device-secret" if size == 32 else "",
        token_factory=lambda size: "a1b2c3d4" if size == 4 else "",
    )

    assert identity.device_id == "pecem-a1b2c3d4"
    assert identity.device_secret == "device-secret"
    assert output.read_text(encoding="utf-8") == (
        "# Provisionamento mobile AlertaM\n"
        "ALERTAM_API_BASE_URL=https://alertam-api.vercel.app\n"
        "ALERTAM_DEVICE_ID=pecem-a1b2c3d4\n"
        "ALERTAM_DEVICE_SECRET=device-secret\n"
    )
    assert admin_env.read_bytes() == b"ADMIN_SENTINEL=unchanged\n"
    assert [call[0] for call in client.calls] == ["GET"]



class SequencedSupabaseClient:
    def __init__(self, existing_ids: set[str]):
        self.existing_ids = set(existing_ids)
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url, *, headers, params):
        self.calls.append(("GET", url, {"headers": headers, "params": params}))
        device_id = str(params["device_id"]).removeprefix("eq.")
        rows = [{"device_id": device_id}] if device_id in self.existing_ids else []
        return FakeResponse(rows)


def test_prepare_retries_colliding_device_id_and_generates_secret_only_for_free_id(
    tmp_path: Path,
):
    from scripts.admin_device import prepare_new_identity

    tokens = iter(["deadbeef", "cafebabe"])
    requested_secret_sizes: list[int] = []
    client = SequencedSupabaseClient({"pecem-deadbeef"})

    identity = prepare_new_identity(
        tmp_path / "identity.env",
        api_base_url="https://alertam-api.vercel.app",
        device_prefix="pecem",
        client=client,
        supabase_url="https://project.supabase.co",
        server_key="sb_secret_admin",
        secret_factory=lambda size: requested_secret_sizes.append(size) or "final-secret",
        token_factory=lambda size: next(tokens),
    )

    assert identity.device_id == "pecem-cafebabe"
    assert identity.device_secret == "final-secret"
    assert requested_secret_sizes == [32]
    assert [
        call[2]["params"]["device_id"] for call in client.calls
    ] == ["eq.pecem-deadbeef", "eq.pecem-cafebabe"]


def test_prepare_fails_after_five_collisions_without_writing_secret_file(
    tmp_path: Path,
):
    from scripts.admin_device import prepare_new_identity

    tokens = iter(["00000001", "00000002", "00000003", "00000004", "00000005"])
    existing = {f"pecem-{token}" for token in (
        "00000001", "00000002", "00000003", "00000004", "00000005"
    )}
    client = SequencedSupabaseClient(existing)
    output = tmp_path / "identity.env"

    with pytest.raises(ValueError, match="5") as exc_info:
        prepare_new_identity(
            output,
            api_base_url="https://alertam-api.vercel.app",
            device_prefix="pecem",
            client=client,
            supabase_url="https://project.supabase.co",
            server_key="sb_secret_admin",
            secret_factory=lambda _: pytest.fail("secret não deve ser gerado"),
            token_factory=lambda size: next(tokens),
        )

    assert not output.exists()
    assert len(client.calls) == 5
    assert "secret" not in str(exc_info.value).lower()



class RegisterSupabaseClient:
    def __init__(self, *, existing_row=None, get_status=200):
        self.existing_row = existing_row
        self.get_status = get_status
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url, *, headers, params):
        self.calls.append(("GET", url, {"headers": headers, "params": params}))
        payload = [] if self.existing_row is None else [self.existing_row]
        return FakeResponse(payload, status_code=self.get_status)

    def post(self, url, *, headers, json):
        self.calls.append(("POST", url, {"headers": headers, "json": json}))
        return FakeResponse(None, status_code=201)

    def patch(self, url, *, headers, params, json):
        self.calls.append(
            ("PATCH", url, {"headers": headers, "params": params, "json": json})
        )
        return FakeResponse(None, status_code=204)


def test_register_prepared_identity_creates_only_hash_for_missing_device():
    from app.security.credentials import hash_secret
    from scripts.admin_device import PreparedDeviceIdentity, register_prepared_identity

    identity = PreparedDeviceIdentity(
        api_base_url="https://alertam-api.vercel.app",
        device_id="pecem-a1b2c3d4",
        device_secret="plain-secret",
    )
    client = RegisterSupabaseClient()

    register_prepared_identity(
        identity,
        description="Notebook do pai",
        client=client,
        supabase_url="https://project.supabase.co",
        server_key="sb_secret_admin",
    )

    assert [call[0] for call in client.calls] == ["GET", "POST"]
    payload = client.calls[1][2]["json"]
    assert payload == {
        "device_id": "pecem-a1b2c3d4",
        "device_secret_hash": hash_secret("plain-secret"),
        "description": "Notebook do pai",
        "enabled": True,
    }
    assert "plain-secret" not in repr(payload)


def test_register_prepared_identity_is_create_only_even_when_hash_matches():
    from app.repositories.devices import DeviceAlreadyExistsError
    from app.security.credentials import hash_secret
    from scripts.admin_device import PreparedDeviceIdentity, register_prepared_identity

    identity = PreparedDeviceIdentity(
        api_base_url="https://alertam-api.vercel.app",
        device_id="pecem-existing",
        device_secret="same-secret",
    )
    client = RegisterSupabaseClient(
        existing_row={
            "device_id": "pecem-existing",
            "device_secret_hash": hash_secret("same-secret"),
        }
    )

    with pytest.raises(DeviceAlreadyExistsError):
        register_prepared_identity(
            identity,
            description="Notebook existente",
            client=client,
            supabase_url="https://project.supabase.co",
            server_key="sb_secret_admin",
        )

    assert [call[0] for call in client.calls] == ["GET"]


def test_register_rejects_malformed_identity_file_before_network(tmp_path: Path):
    from scripts.admin_device import load_prepared_identity

    malformed = tmp_path / "identity.env"
    malformed.write_text(
        "ALERTAM_DEVICE_ID=pecem-a1b2c3d4\n"
        "ALERTAM_DEVICE_SECRET=plain-secret\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ALERTAM_API_BASE_URL"):
        load_prepared_identity(malformed)


def test_register_admin_401_does_not_leak_device_or_admin_secret():
    from scripts.admin_device import PreparedDeviceIdentity, register_prepared_identity

    identity = PreparedDeviceIdentity(
        api_base_url="https://alertam-api.vercel.app",
        device_id="pecem-a1b2c3d4",
        device_secret="device-secret-never-log",
    )
    admin_key = "admin-key-never-log"
    client = RegisterSupabaseClient(get_status=401)

    with pytest.raises(ValueError, match="401") as exc_info:
        register_prepared_identity(
            identity,
            description="Notebook teste",
            client=client,
            supabase_url="https://project.supabase.co",
            server_key=admin_key,
        )

    message = str(exc_info.value)
    assert identity.device_secret not in message
    assert admin_key not in message



class ContextRegisterClient(RegisterSupabaseClient):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_cli_prepare_prints_device_id_but_never_secret(tmp_path: Path, capsys):
    from scripts.admin_device import main

    admin_env = tmp_path / ".env.prod"
    admin_env.write_text(
        "SUPABASE_URL=https://project.supabase.co\n"
        "SUPABASE_SECRET_KEY=sb_secret_admin\n",
        encoding="utf-8",
    )
    identity_env = tmp_path / "identity.env"
    client = ContextRegisterClient()

    exit_code = main(
        [
            "prepare",
            "--output-env",
            str(identity_env),
            "--admin-env",
            str(admin_env),
            "--api-base-url",
            "https://alertam-api.vercel.app",
            "--device-prefix",
            "pecem",
        ],
        secret_factory=lambda size: "cli-device-secret" if size == 32 else "",
        token_factory=lambda size: "a1b2c3d4" if size == 4 else "",
        client_factory=lambda **_: client,
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "DEVICE_ID=pecem-a1b2c3d4" in output
    assert "cli-device-secret" not in output
    assert identity_env.exists()


def test_cli_register_prints_device_id_but_never_secret(tmp_path: Path, capsys):
    from scripts.admin_device import main

    admin_env = tmp_path / ".env.prod"
    admin_env.write_text(
        "SUPABASE_URL=https://project.supabase.co\n"
        "SUPABASE_SECRET_KEY=sb_secret_admin\n",
        encoding="utf-8",
    )
    identity_env = tmp_path / "identity.env"
    identity_env.write_text(
        "# Provisionamento mobile AlertaM\n"
        "ALERTAM_API_BASE_URL=https://alertam-api.vercel.app\n"
        "ALERTAM_DEVICE_ID=pecem-a1b2c3d4\n"
        "ALERTAM_DEVICE_SECRET=cli-device-secret\n",
        encoding="utf-8",
    )
    client = ContextRegisterClient()

    exit_code = main(
        [
            "register",
            "--identity-env",
            str(identity_env),
            "--admin-env",
            str(admin_env),
            "--description",
            "Notebook do pai",
        ],
        client_factory=lambda **_: client,
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "DEVICE_ID=pecem-a1b2c3d4" in output
    assert "cli-device-secret" not in output
    assert [call[0] for call in client.calls] == ["GET", "POST"]



class FakeDbResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class FakeDbConnection:
    def __init__(
        self,
        *,
        device_row,
        dependency: tuple[str, str] | None = None,
        delete_row=("pecem-attempt01",),
        dependency_error: Exception | None = None,
    ):
        self.device_row = device_row
        self.dependency = dependency
        self.delete_row = delete_row
        self.dependency_error = dependency_error
        self.calls: list[tuple[str, tuple]] = []
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited = True
        return False

    def execute(self, sql, params=()):
        normalized = " ".join(str(sql).split()).lower()
        params = tuple(params)
        self.calls.append((normalized, params))
        if "from public.devices" in normalized and "for update" in normalized:
            if self.device_row is None:
                return FakeDbResult(None)
            row = self.device_row
            return FakeDbResult(
                (
                    row["device_id"],
                    row["device_secret_hash"],
                    row["view_secret_hash"],
                    row["snapshot"],
                    row["boot_id"],
                    row["sequence"],
                    row["generated_at"],
                    row["received_at"],
                )
            )
        if normalized.startswith("select 1 from public."):
            if self.dependency_error is not None:
                raise self.dependency_error
            if self.dependency is not None:
                table, column = self.dependency
                if (
                    f"from public.{table}" in normalized
                    and f"where {column} = %s" in normalized
                ):
                    return FakeDbResult((1,))
            return FakeDbResult(None)
        if normalized.startswith("delete from public.devices"):
            return FakeDbResult(self.delete_row)
        raise AssertionError(f"SQL inesperado: {normalized}")


def pristine_device_row(secret: str = "attempt-secret"):
    from app.security.credentials import hash_secret

    return {
        "device_id": "pecem-attempt01",
        "device_secret_hash": hash_secret(secret),
        "view_secret_hash": None,
        "snapshot": None,
        "boot_id": None,
        "sequence": None,
        "generated_at": None,
        "received_at": None,
    }


def prepared_attempt_identity(secret: str = "attempt-secret"):
    from scripts.admin_device import PreparedDeviceIdentity

    return PreparedDeviceIdentity(
        api_base_url="https://alertam-api.vercel.app",
        device_id="pecem-attempt01",
        device_secret=secret,
    )


def connect_to(fake_connection: FakeDbConnection):
    calls: list[str] = []

    def factory(database_url: str):
        calls.append(database_url)
        return fake_connection

    factory.calls = calls
    return factory


def test_compensate_locks_pristine_attempt_owned_device_and_deletes_in_same_transaction():
    from scripts.admin_device import compensate_prepared_identity

    identity = prepared_attempt_identity()
    connection = FakeDbConnection(device_row=pristine_device_row())
    factory = connect_to(connection)

    removed = compensate_prepared_identity(
        identity,
        database_url="postgresql://admin-db",
        connect_factory=factory,
    )

    assert removed is True
    assert connection.entered and connection.exited
    assert factory.calls == ["postgresql://admin-db"]
    assert "for update" in connection.calls[0][0]
    assert connection.calls[-1][0].startswith("delete from public.devices")
    assert "attempt-secret" not in repr(connection.calls)


def test_compensate_refuses_when_stored_hash_does_not_match_attempt():
    from scripts.admin_device import compensate_prepared_identity

    connection = FakeDbConnection(
        device_row=pristine_device_row("another-secret")
    )

    removed = compensate_prepared_identity(
        prepared_attempt_identity(),
        database_url="postgresql://admin-db",
        connect_factory=connect_to(connection),
    )

    assert removed is False
    assert all(not sql.startswith("delete ") for sql, _ in connection.calls)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("view_secret_hash", "view-hash"),
        ("snapshot", {"meta": {}}),
        ("boot_id", "11111111-1111-1111-1111-111111111111"),
        ("sequence", 1),
        ("generated_at", "2026-10-02T12:00:00+00:00"),
        ("received_at", "2026-10-02T12:00:00+00:00"),
    ],
)
def test_compensate_refuses_any_activation_signal(field, value):
    from scripts.admin_device import compensate_prepared_identity

    row = pristine_device_row()
    row[field] = value
    connection = FakeDbConnection(device_row=row)

    removed = compensate_prepared_identity(
        prepared_attempt_identity(),
        database_url="postgresql://admin-db",
        connect_factory=connect_to(connection),
    )

    assert removed is False
    assert all(not sql.startswith("delete ") for sql, _ in connection.calls)


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("maneuver_events", "device_id"),
        ("push_installations", "device_id"),
        ("vessel_tracking_events", "device_id"),
        ("mobile_installations", "device_id"),
        ("tracked_vessels", "device_id"),
        ("mobile_session_switches", "from_device_id"),
        ("mobile_session_switches", "to_device_id"),
    ],
)
def test_compensate_refuses_when_any_dependent_row_exists(table, column):
    from scripts.admin_device import compensate_prepared_identity

    connection = FakeDbConnection(
        device_row=pristine_device_row(),
        dependency=(table, column),
    )

    removed = compensate_prepared_identity(
        prepared_attempt_identity(),
        database_url="postgresql://admin-db",
        connect_factory=connect_to(connection),
    )

    assert removed is False
    assert all(not sql.startswith("delete ") for sql, _ in connection.calls)


def test_compensate_dependency_query_error_fails_closed_without_delete():
    from scripts.admin_device import compensate_prepared_identity

    connection = FakeDbConnection(
        device_row=pristine_device_row(),
        dependency_error=RuntimeError("dependency query failed"),
    )

    with pytest.raises(RuntimeError, match="dependency query failed"):
        compensate_prepared_identity(
            prepared_attempt_identity(),
            database_url="postgresql://admin-db",
            connect_factory=connect_to(connection),
        )

    assert all(not sql.startswith("delete ") for sql, _ in connection.calls)


def test_compensate_returns_false_when_filtered_delete_removes_zero_rows():
    from scripts.admin_device import compensate_prepared_identity

    connection = FakeDbConnection(
        device_row=pristine_device_row(),
        delete_row=None,
    )

    removed = compensate_prepared_identity(
        prepared_attempt_identity(),
        database_url="postgresql://admin-db",
        connect_factory=connect_to(connection),
    )

    assert removed is False


def write_prepared_identity_file(path: Path, secret: str = "attempt-secret"):
    path.write_text(
        "# Provisionamento mobile AlertaM\n"
        "ALERTAM_API_BASE_URL=https://alertam-api.vercel.app\n"
        "ALERTAM_DEVICE_ID=pecem-attempt01\n"
        f"ALERTAM_DEVICE_SECRET={secret}\n",
        encoding="utf-8",
    )


def write_admin_db_env(path: Path):
    path.write_text(
        "SUPABASE_DB_URL=postgresql://admin-db\n",
        encoding="utf-8",
    )


def test_cli_compensate_uses_database_url_and_never_prints_secret(tmp_path: Path, capsys):
    from scripts.admin_device import main

    identity_env = tmp_path / "identity.env"
    admin_env = tmp_path / ".env.prod"
    write_prepared_identity_file(identity_env)
    write_admin_db_env(admin_env)
    connection = FakeDbConnection(device_row=pristine_device_row())

    exit_code = main(
        [
            "compensate",
            "--identity-env",
            str(identity_env),
            "--admin-env",
            str(admin_env),
        ],
        connect_factory=connect_to(connection),
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "DEVICE_ID=pecem-attempt01" in output
    assert "attempt-secret" not in output
    assert "postgresql://admin-db" not in output


def test_cli_compensate_refusal_is_nonzero_and_never_prints_secret(
    tmp_path: Path, capsys
):
    from scripts.admin_device import main

    identity_env = tmp_path / "identity.env"
    admin_env = tmp_path / ".env.prod"
    write_prepared_identity_file(identity_env)
    write_admin_db_env(admin_env)
    connection = FakeDbConnection(
        device_row=pristine_device_row("different-secret")
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "compensate",
                "--identity-env",
                str(identity_env),
                "--admin-env",
                str(admin_env),
            ],
            connect_factory=connect_to(connection),
        )

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "pecem-attempt01" in combined
    assert "attempt-secret" not in combined
    assert "postgresql://admin-db" not in combined



def test_cli_compensate_database_error_never_prints_database_url_or_password(
    tmp_path: Path, capsys
):
    import psycopg
    from scripts.admin_device import main

    identity_env = tmp_path / "identity.env"
    admin_env = tmp_path / ".env.prod"
    write_prepared_identity_file(identity_env)
    admin_env.write_text(
        "SUPABASE_DB_URL=postgresql://admin:db-password-never-log@db.example/postgres\n",
        encoding="utf-8",
    )

    def failing_connect(_database_url: str):
        raise psycopg.OperationalError(
            "connection failed for postgresql://admin:db-password-never-log@db.example/postgres"
        )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "compensate",
                "--identity-env",
                str(identity_env),
                "--admin-env",
                str(admin_env),
            ],
            connect_factory=failing_connect,
        )

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "db-password-never-log" not in combined
    assert "postgresql://" not in combined
    assert "compensação" in combined.lower()


def test_register_new_device_persists_trimmed_description_and_enabled_true():
    from app.security.credentials import hash_secret
    from scripts.admin_device import PreparedDeviceIdentity, register_prepared_identity

    identity = PreparedDeviceIdentity(
        api_base_url="https://alertam-api.vercel.app",
        device_id="pecem-meta1234",
        device_secret="plain-secret",
    )
    client = RegisterSupabaseClient()

    register_prepared_identity(
        identity,
        description="  Notebook do pai  ",
        client=client,
        supabase_url="https://project.supabase.co",
        server_key="sb_secret_admin",
    )

    assert [call[0] for call in client.calls] == ["GET", "POST"]
    assert client.calls[1][2]["json"] == {
        "device_id": "pecem-meta1234",
        "device_secret_hash": hash_secret("plain-secret"),
        "description": "Notebook do pai",
        "enabled": True,
    }


@pytest.mark.parametrize("value", ["", "   ", "x" * 201])
def test_register_new_device_rejects_invalid_description_before_network(value):
    from scripts.admin_device import PreparedDeviceIdentity, register_prepared_identity

    client = RegisterSupabaseClient()
    identity = PreparedDeviceIdentity(
        api_base_url="https://alertam-api.vercel.app",
        device_id="pecem-meta1234",
        device_secret="plain-secret",
    )

    with pytest.raises(ValueError, match="description"):
        register_prepared_identity(
            identity,
            description=value,
            client=client,
            supabase_url="https://project.supabase.co",
            server_key="sb_secret_admin",
        )

    assert client.calls == []
