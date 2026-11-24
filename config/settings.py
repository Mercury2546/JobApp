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
    global \
        OPENAI_API_KEY, \
        OPENAI_MODEL, \
        OPENAI_BASE_URL, \
        NOTION_API_KEY, \
        NOTION_DATABASE_ID
    if _DOTENV_AVAILABLE and ENV_FILE.exists():
        load_dotenv(dotenv_path=ENV_FILE, override=True)
    elif _DOTENV_AVAILABLE:
        load_dotenv(override=True)

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "qwen/qwen3.8-27b").strip()
    raw_base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    OPENAI_BASE_URL = raw_base_url if raw_base_url else None

    NOTION_API_KEY = (
        os.getenv("NOTION_API_KEY", "").strip() or os.getenv("NOTION_TOKEN", "").strip()
    )
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "").strip()

    # รองรับ Streamlit Cloud Secrets หรือ Session State เมื่อ Deploy ขึ้น Cloud หรือกรอกผ่านเว็บ
    try:
        import streamlit as st

        # อ่านจาก session_state ก่อน (หากผู้ใช้กรอกผ่านหน้า UI)
        if hasattr(st, "session_state"):
            if st.session_state.get("custom_notion_key"):
                NOTION_API_KEY = st.session_state["custom_notion_key"].strip()
            if st.session_state.get("custom_notion_db_id"):
                NOTION_DATABASE_ID = st.session_state["custom_notion_db_id"].strip()

        # อ่านจาก st.secrets
        if hasattr(st, "secrets"):
            if not OPENAI_API_KEY and "OPENAI_API_KEY" in st.secrets:
                OPENAI_API_KEY = str(st.secrets["OPENAI_API_KEY"]).strip()
            if "OPENAI_MODEL" in st.secrets:
                OPENAI_MODEL = str(st.secrets["OPENAI_MODEL"]).strip()
            if "OPENAI_BASE_URL" in st.secrets and not OPENAI_BASE_URL:
                OPENAI_BASE_URL = str(st.secrets["OPENAI_BASE_URL"]).strip()
            if not NOTION_API_KEY and "NOTION_API_KEY" in st.secrets:
                NOTION_API_KEY = str(st.secrets["NOTION_API_KEY"]).strip()
            if not NOTION_DATABASE_ID and "NOTION_DATABASE_ID" in st.secrets:
                NOTION_DATABASE_ID = str(st.secrets["NOTION_DATABASE_ID"]).strip()
    except Exception:  # noqa: BLE001, S110 — optional Streamlit context when imported from CLI
        pass


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
    placeholder_keys = [
        "your_openai_api_key_here",
        "sk-...",
        "your_key_here",
        "gsk_your_api_key_here",
    ]
    return key not in placeholder_keys and len(key) > 5


def get_notion_api_key() -> str:
    reload_env()
    return NOTION_API_KEY


def get_notion_database_id() -> str:
    reload_env()
    return NOTION_DATABASE_ID


def is_notion_configured() -> bool:
    """
    ตรวจสอบว่ามีการระบุ Notion API Token และ Database ID แล้วหรือไม่
    """
    key = get_notion_api_key()
    db_id = get_notion_database_id()
    return bool(key and db_id and len(key) > 10 and len(db_id) > 10)
