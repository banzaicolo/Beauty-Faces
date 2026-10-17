"""Runtime configuration and active scenario profile."""

import json
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

SUPPORTED_PROVIDERS = {"ollama", "openai_compatible", "custom", "disabled"}
PRIVACY_MODES = {"local", "external", "unknown"}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float | None = None) -> float | None:
    raw = os.environ.get(name, "").strip()
    return float(raw) if raw else default


def _env_int(name: str, default: int | None = None) -> int | None:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def _env_json_object(name: str) -> dict:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return value


# Text model. Providers are selected entirely by deployment configuration.
TEXT_PROVIDER = os.environ.get("TEXT_PROVIDER", "").strip().lower()
TEXT_MODEL = os.environ.get("TEXT_MODEL", "").strip()
TEXT_BASE_URL = os.environ.get("TEXT_BASE_URL", "").strip()
TEXT_API_KEY = os.environ.get("TEXT_API_KEY", "").strip()
TEXT_PROVIDER_FACTORY = os.environ.get("TEXT_PROVIDER_FACTORY", "").strip()
TEXT_TEMPERATURE = _env_float("TEXT_TEMPERATURE", 0.6)
TEXT_MAX_TOKENS = _env_int("TEXT_MAX_TOKENS")
TEXT_TIMEOUT_SECONDS = _env_int("TEXT_TIMEOUT_SECONDS", 180)
TEXT_HEADERS = _env_json_object("TEXT_HEADERS_JSON")
TEXT_EXTRA_BODY = _env_json_object("TEXT_EXTRA_BODY_JSON")
TEXT_TOOL_CALLING = _env_bool("TEXT_TOOL_CALLING", True)
TEXT_PRIVACY_MODE = os.environ.get("TEXT_PRIVACY_MODE", "unknown").strip().lower()

# Vision model. The same protocols and custom factory escape hatch are available.
VISION_PROVIDER = os.environ.get("VISION_PROVIDER", "").strip().lower()
VISION_MODEL = os.environ.get("VISION_MODEL", "").strip()
VISION_BASE_URL = os.environ.get("VISION_BASE_URL", "").strip()
VISION_API_KEY = os.environ.get("VISION_API_KEY", "").strip()
VISION_ENDPOINT = os.environ.get("VISION_ENDPOINT", "").strip()
VISION_PROVIDER_FACTORY = os.environ.get("VISION_PROVIDER_FACTORY", "").strip()
VISION_TEMPERATURE = _env_float("VISION_TEMPERATURE", 0.3)
VISION_MAX_TOKENS = _env_int("VISION_MAX_TOKENS")
VISION_STREAM = _env_bool("VISION_STREAM", True)
VISION_TIMEOUT_SECONDS = _env_int("VISION_TIMEOUT_SECONDS", 300)
VISION_HEADERS = _env_json_object("VISION_HEADERS_JSON")
VISION_EXTRA_BODY = _env_json_object("VISION_EXTRA_BODY_JSON")
VISION_PRIVACY_MODE = os.environ.get("VISION_PRIVACY_MODE", "unknown").strip().lower()

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
    _validate_model_settings("TEXT", TEXT_PROVIDER, TEXT_MODEL, errors)
    _validate_model_settings("VISION", VISION_PROVIDER, VISION_MODEL, errors)
    if TEXT_PRIVACY_MODE not in PRIVACY_MODES:
        errors.append("TEXT_PRIVACY_MODE must be local, external, or unknown")
    if VISION_PRIVACY_MODE not in PRIVACY_MODES:
        errors.append("VISION_PRIVACY_MODE must be local, external, or unknown")
    if TEXT_TIMEOUT_SECONDS is None or TEXT_TIMEOUT_SECONDS < 1:
        errors.append("TEXT_TIMEOUT_SECONDS must be positive")
    if VISION_TIMEOUT_SECONDS is None or VISION_TIMEOUT_SECONDS < 1:
        errors.append("VISION_TIMEOUT_SECONDS must be positive")
    if errors:
        raise RuntimeError("Unsafe runtime configuration: " + "; ".join(errors))


def _validate_model_settings(prefix: str, provider: str, model: str, errors: list) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        errors.append(
            f"{prefix}_PROVIDER must be one of: ollama, openai_compatible, custom, disabled"
        )
        return
    if provider == "disabled":
        return
    if provider == "custom":
        factory = os.environ.get(f"{prefix}_PROVIDER_FACTORY", "").strip()
        if ":" not in factory:
            errors.append(f"{prefix}_PROVIDER_FACTORY must use module.path:function syntax")
        return
    if not model:
        errors.append(f"{prefix}_MODEL is required for provider {provider}")
    base_url = os.environ.get(f"{prefix}_BASE_URL", "").strip()
    endpoint = os.environ.get("VISION_ENDPOINT", "").strip() if prefix == "VISION" else ""
    if provider in {"ollama", "openai_compatible"} and not base_url and not endpoint:
        errors.append(f"{prefix}_BASE_URL is required for provider {provider}")
