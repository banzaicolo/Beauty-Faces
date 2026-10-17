"""Runtime configuration and active scenario profile."""

import os
from pathlib import Path

from .profile import load_profile

BASE_DIR = Path(__file__).parent
PROFILES_DIR = BASE_DIR / "profiles"
PROFILE_ID = os.environ.get("APP_PROFILE", "skin_care")
PROFILE = load_profile(PROFILES_DIR / PROFILE_ID)
PUBLIC_PROFILE = PROFILE.public_meta()

DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR.parent / "data")))
DB_PATH = DATA_DIR / f"{PROFILE_ID}.db"
CHECKPOINT_DB_PATH = DATA_DIR / f"{PROFILE_ID}-checkpoints.db"

SEED_DEMO = os.environ.get("SEED_DEMO", "0") == "1"

# Providers. DeepSeek is optional; Ollama is the default local provider.
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3.5:4b")
VLM_MODEL = os.environ.get("VLM_MODEL", "qwen3-vl:8b")

PORT = int(os.environ.get("PORT", "8000"))

# Authentication is fail-closed: a weak or missing secret prevents startup.
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "28800"))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

# Request limits and simple in-process rate limits for this single-node demo.
MAX_REQUEST_BYTES = int(os.environ.get("MAX_REQUEST_BYTES", str(16 * 1024 * 1024)))
MAX_CHAT_CHARS = int(os.environ.get("MAX_CHAT_CHARS", "4000"))
MAX_IMAGE_B64_CHARS = int(os.environ.get("MAX_IMAGE_B64_CHARS", str(12 * 1024 * 1024)))
RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "12"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))


def load_json(name: str):
    return PROFILE.read_json(name)


def load_text(name: str) -> str:
    return PROFILE.read_text(name)


def validate_runtime_config() -> None:
    """Reject insecure defaults instead of silently exposing customer data."""
    errors = []
    if len(ADMIN_TOKEN) < 16:
        errors.append("ADMIN_TOKEN must contain at least 16 characters")
    if len(SESSION_SECRET) < 32:
        errors.append("SESSION_SECRET must contain at least 32 characters")
    if MAX_REQUEST_BYTES < 1024:
        errors.append("MAX_REQUEST_BYTES must be at least 1024")
    if errors:
        raise RuntimeError("Unsafe runtime configuration: " + "; ".join(errors))
