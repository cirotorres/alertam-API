from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
SMOKE_SCRIPT = ROOT / "cloud" / "scripts" / "smoke.sh"


def _target_block(content: str, target: str) -> str:
    match = re.search(
        rf"(?m)^{re.escape(target)}:[^\n]*\n(?P<recipe>(?:\t[^\n]*\n)+)",
        content,
    )
    return match.group(0) if match else ""


class CloudMakeTargetsTests(unittest.TestCase):
    def test_cloud_targets_exist_and_are_isolated(self) -> None:
        content = MAKEFILE.read_text(encoding="utf-8")
        forbidden = ("supabase", "migrate", "vercel", "desktop", "postgres", "database")

        for target in ("cloud-test", "cloud-build", "cloud-smoke"):
            block = _target_block(content, target)
            self.assertTrue(block, f"Makefile target {target} must exist")
            lowered = block.lower()
            for token in forbidden:
                self.assertNotIn(token, lowered, f"{target} must not touch {token}")

    def test_cloud_smoke_script_checks_runtime_contract_without_operational_services(self) -> None:
        self.assertTrue(SMOKE_SCRIPT.is_file(), "cloud/scripts/smoke.sh must exist")
        content = SMOKE_SCRIPT.read_text(encoding="utf-8")
        lowered = content.lower()
        for required in ("/healthz", "/readyz", "docker stop", "docker start", "os.getuid()"):
            self.assertIn(required, content)
        self.assertGreaterEqual(
            content.count('HOST_PORT="$(docker port'),
            2,
            "smoke must refresh Docker's dynamically assigned host port after restart",
        )
        for token in ("supabase", "webpilot", "sessionlease", "cloudbinding", "device_secret"):
            self.assertNotIn(token, lowered)


if __name__ == "__main__":
    unittest.main()
