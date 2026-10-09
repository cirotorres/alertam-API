from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SANDBOX = ROOT / "cloud" / "sandbox"
COMPOSE = SANDBOX / "c2c-compose.yml"
BOOTSTRAP = SANDBOX / "bootstrap.py"
PUBLISHER = SANDBOX / "publisher.py"
FAKE_WEBPILOT = SANDBOX / "fake_webpilot.py"
SCENARIO = SANDBOX / "cloud_scenario.py"
RESTART = SANDBOX / "restart_persistence.py"


class C2CSandboxContractTests(unittest.TestCase):
    def test_sandbox_files_exist(self) -> None:
        for path in (
            COMPOSE,
            BOOTSTRAP,
            PUBLISHER,
            FAKE_WEBPILOT,
            SCENARIO,
            RESTART,
        ):
            self.assertTrue(path.is_file(), path)

    def test_compose_is_fully_synthetic_and_ephemeral(self) -> None:
        content = COMPOSE.read_text(encoding="utf-8")
        for service in (
            "db:",
            "migrate:",
            "api:",
            "fake-webpilot:",
            "bootstrap:",
            "publisher-a:",
            "publisher-b:",
            "cloud-runner:",
            "restart-outage:",
            "restart-probe:",
            "expiry-probe:",
        ):
            self.assertIn(service, content)

        self.assertIn("tmpfs:", content)
        self.assertIn("ALERTAM_WHEEL_NAME", content)
        self.assertIn("additional_contexts", content)
        self.assertNotIn("northflank", content.lower())
        self.assertNotIn("webpilot.cearapilots.com.br", content.lower())
        self.assertNotIn("source=cloud", content.lower())
        self.assertNotIn("failover", content.lower())
        self.assertNotIn("failback", content.lower())

    def test_scenario_has_no_snapshot_or_source_writes(self) -> None:
        content = SCENARIO.read_text(encoding="utf-8").lower()
        for forbidden in (
            "/snapshot",
            "source=cloud",
            "failover",
            "failback",
            "event/push",
        ):
            self.assertNotIn(forbidden, content)

        for required in (
            "brokersessionprovider",
            "sessionbrokerclient",
            "build_canonical_standby",
            "auth_unavailable",
            "realm_epoch",
        ):
            self.assertIn(required, content)

    def test_restart_probe_persists_only_sanitized_identity_metadata(self) -> None:
        content = RESTART.read_text(encoding="utf-8").lower()
        for required in (
            "filerejectedidentitystore",
            "auth_unavailable",
            "restart-rejections.json",
            "realm_epoch",
        ):
            self.assertIn(required, content)
        for forbidden in (
            "/snapshot",
            "source=cloud",
            "failover",
            "failback",
            "ciphertext",
            "authorization",
        ):
            self.assertNotIn(forbidden, content)

    def test_fake_webpilot_serves_only_synthetic_fixture_routes(self) -> None:
        content = FAKE_WEBPILOT.read_text(encoding="utf-8").lower()
        for required in ("/maneuvers", "/weather", "/login"):
            self.assertIn(required, content)
        self.assertNotIn("cearapilots", content)


if __name__ == "__main__":
    unittest.main()
