from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
CLOUD_DIR = ROOT / "cloud"
MAKEFILE = ROOT / "Makefile"
DOCKERFILE = CLOUD_DIR / "Dockerfile"
CONTRACT_SCRIPT = CLOUD_DIR / "scripts" / "headless_contract.py"
STANDBY_SCRIPT = CLOUD_DIR / "scripts" / "standby_contract.py"


class HeadlessWheelContractTests(unittest.TestCase):
    def test_collector_modules_are_not_copied_into_cloud_package(self) -> None:
        copied_names = {
            path.name
            for path in (CLOUD_DIR / "alertam_cloud").rglob("*.py")
        }
        for forbidden in {
            "webpilot_auth.py",
            "webpilot_http.py",
            "webpilot_grid_html.py",
            "webpilot_weather.py",
            "webpilot_weather_parser.py",
            "parser.py",
        }:
            self.assertNotIn(forbidden, copied_names)

    def test_headless_contract_script_proves_canonical_import_closure(self) -> None:
        self.assertTrue(CONTRACT_SCRIPT.is_file())
        content = CONTRACT_SCRIPT.read_text(encoding="utf-8")
        for required in (
            "alertam.application.webpilot_auth",
            "alertam.infrastructure.webpilot_http",
            "alertam.infrastructure.webpilot_grid_html",
            "alertam.domain",
            "importlib.util.find_spec",
            "selenium",
            "webdriver_manager",
            "PIL",
            "pyttsx3",
            "tkinter",
            "grid_real_2026-09-21.html",
        ):
            self.assertIn(required, content)

    def test_standby_contract_executes_canonical_maneuvers_weather_with_fake_transport(self) -> None:
        self.assertTrue(STANDBY_SCRIPT.is_file())
        content = STANDBY_SCRIPT.read_text(encoding="utf-8")
        for required in (
            "build_canonical_standby",
            "BrokerSessionProvider",
            "grid_real_2026-09-21.html",
            "webpilot_weather_pecem.html",
            "AUTH_UNAVAILABLE",
            "realm_epoch",
        ):
            self.assertIn(required, content)
        for forbidden in (
            "source=cloud",
            "/snapshot",
            "failover",
            "failback",
        ):
            self.assertNotIn(forbidden, content.lower())

    def test_docker_headless_target_installs_external_wheel_no_deps(self) -> None:
        content = DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("AS headless", content)
        self.assertIn("COPY --from=alertam_wheel", content)
        self.assertRegex(
            content,
            re.compile(r"pip install[^\n]*--no-deps", re.IGNORECASE),
        )
        self.assertNotIn("COPY webpilot_", content)
        self.assertNotIn("COPY ../", content)

    def test_makefile_has_explicit_wheel_contract_build_and_smoke_targets(self) -> None:
        content = MAKEFILE.read_text(encoding="utf-8")
        for target in (
            "cloud-wheel-contract:",
            "cloud-build-wheel:",
            "cloud-smoke-wheel:",
        ):
            self.assertIn(target, content)
        self.assertIn("DESKTOP_WHEEL", content)
        self.assertIn("DESKTOP_FIXTURE", content)
        self.assertIn("--build-context alertam_wheel=", content)


if __name__ == "__main__":
    unittest.main()
