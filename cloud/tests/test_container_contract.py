from pathlib import Path
import unittest


CLOUD_DIR = Path(__file__).resolve().parents[1]


class ContainerContractTests(unittest.TestCase):
    def test_dockerfile_is_minimal_non_root_python_312_slim(self) -> None:
        dockerfile = CLOUD_DIR / "Dockerfile"
        self.assertTrue(dockerfile.is_file(), "cloud/Dockerfile must exist")
        content = dockerfile.read_text(encoding="utf-8")
        lowered = content.lower()

        self.assertIn("FROM python:3.12-slim", content)
        self.assertIn("PYTHONUNBUFFERED=1", content)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", content)
        self.assertIn("PORT=8080", content)
        self.assertIn("USER 10001:10001", content)
        self.assertIn("HEALTHCHECK", content)
        self.assertIn("/healthz", content)
        self.assertIn('["python", "-m", "alertam_cloud"]', content)
        self.assertIn("AS headless", content)
        self.assertIn("COPY --from=alertam_wheel", content)
        self.assertIn("pip install", lowered)
        self.assertIn("--no-deps", content)
        for forbidden in (
            "selenium",
            "webdriver-manager",
            "webdriver_manager",
            "pillow",
            "pyttsx3",
            "supabase",
            "device_secret",
        ):
            self.assertNotIn(forbidden, lowered)

    def test_dockerignore_excludes_local_and_sensitive_artifacts(self) -> None:
        dockerignore = CLOUD_DIR / ".dockerignore"
        self.assertTrue(dockerignore.is_file(), "cloud/.dockerignore must exist")
        ignored = {
            line.strip()
            for line in dockerignore.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        for required in {
            ".env",
            ".env.*",
            ".venv/",
            "__pycache__/",
            "*.pyc",
            ".pytest_cache/",
            "tests/",
        }:
            self.assertIn(required, ignored)


if __name__ == "__main__":
    unittest.main()
