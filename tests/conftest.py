import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TEST_DATA_DIR = tempfile.mkdtemp(prefix="beauty-faces-tests-")
os.environ["DATA_DIR"] = TEST_DATA_DIR
os.environ["ADMIN_TOKEN"] = "test-admin-token-not-for-release"
os.environ["SESSION_SECRET"] = "test-session-secret-with-more-than-32-characters"
os.environ["SEED_DEMO"] = "1"
os.environ["COOKIE_SECURE"] = "false"
os.environ.setdefault("APP_PROFILE", "skin_care")
os.environ["TEXT_PROVIDER"] = "ollama"
os.environ["TEXT_MODEL"] = "test-text-model"
os.environ["TEXT_BASE_URL"] = "http://localhost:11434"
os.environ["TEXT_PRIVACY_MODE"] = "local"
os.environ["VISION_PROVIDER"] = "ollama"
os.environ["VISION_MODEL"] = "test-vision-model"
os.environ["VISION_BASE_URL"] = "http://localhost:11434"
os.environ["VISION_PRIVACY_MODE"] = "local"

from app.seed import seed  # noqa: E402

seed()
