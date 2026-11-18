"""
Application Settings & Configuration Loader.
Loads configuration from environment variables via python-dotenv with dynamic reload support.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False

# Define root directory
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

# Database Settings
DB_FILE_NAME = os.getenv("DB_PATH", "career_agent.db").strip()
DB_PATH = BASE_DIR / DB_FILE_NAME

# Logging Settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "career_agent.log"


def reload_env():
    """
    Reloads .env variables with override=True so changes take effect
    immediately without restarting the Streamlit server.
    """
    global OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
    if _DOTENV_AVAILABLE and ENV_FILE.exists():
        load_dotenv(dotenv_path=ENV_FILE, override=True)
    elif _DOTENV_AVAILABLE:
        load_dotenv(override=True)

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "qwen/qwen3.8-27b").strip()
    raw_base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    OPENAI_BASE_URL = raw_base_url if raw_base_url else None


# Initial load
reload_env()


def get_openai_api_key() -> str:
    reload_env()
    return OPENAI_API_KEY


def get_openai_model() -> str:
    reload_env()
    return OPENAI_MODEL


def get_openai_base_url() -> str | None:
    reload_env()
    return OPENAI_BASE_URL


def is_openai_configured() -> bool:
    """
    Check if a non-placeholder API key is set.
    """
    key = get_openai_api_key()
    if not key:
        return False
    placeholder_keys = ["your_openai_api_key_here", "sk-...", "your_key_here", "gsk_your_api_key_here"]
    return key not in placeholder_keys and len(key) > 5
