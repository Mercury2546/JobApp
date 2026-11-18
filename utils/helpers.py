"""
General helper functions for Career Agent.
"""
from datetime import datetime
from typing import Optional


def format_date(date_str: Optional[str], input_fmt: str = "%Y-%m-%d", output_fmt: str = "%b %d, %Y") -> str:
    """
    Safely format a date string into a user-friendly format.
    """
    if not date_str:
        return "N/A"
    try:
        dt = datetime.strptime(date_str, input_fmt)
        return dt.strftime(output_fmt)
    except (ValueError, TypeError):
        return date_str


def truncate_text(text: Optional[str], max_len: int = 100) -> str:
    """
    Truncate text with ellipsis if it exceeds max_len.
    """
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def get_current_date_str() -> str:
    """
    Return current date formatted as YYYY-MM-DD.
    """
    return datetime.now().strftime("%Y-%m-%d")
