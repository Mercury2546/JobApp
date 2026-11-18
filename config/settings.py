"""
Application Settings & Configuration Loader.
Loads configuration from environment variables via python-dotenv.
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

# Load .env file from base directory if dotenv is installed
ENV_FILE = BASE_DIR / ".env"
if _DOTENV_AVAILABLE:
    if ENV_FILE.exists():
        load_dotenv(dotenv_path=ENV_FILE)
    else:
        load_dotenv()


# OpenAI & Compatible AI Provider Settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip() or None

# Database Settings
DB_FILE_NAME = os.getenv("DB_PATH", "career_agent.db").strip()
DB_PATH = BASE_DIR / DB_FILE_NAME

# Logging Settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "career_agent.log"


def is_openai_configured() -> bool:
    """
    Check if a non-placeholder OpenAI API key is set.
    """
    if not OPENAI_API_KEY:
        return False
    placeholder_keys = ["your_openai_api_key_here", "sk-...", "your_key_here"]
    return OPENAI_API_KEY not in placeholder_keys and len(OPENAI_API_KEY) > 10
