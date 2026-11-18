"""
ฟังก์ชันตัวช่วยทั่วไปสำหรับ Career Agent
"""
from datetime import datetime
from typing import Optional


def format_date(date_str: Optional[str], input_fmt: str = "%Y-%m-%d", output_fmt: str = "%d/%m/%Y") -> str:
    """
    จัดรูปแบบวันที่ให้แสดงผลอย่างสวยงามและเข้าใจง่าย (วัน/เดือน/ปี)
    """
    if not date_str:
        return "ไม่ระบุ"
    try:
        dt = datetime.strptime(str(date_str)[:10], input_fmt)
        return dt.strftime(output_fmt)
    except (ValueError, TypeError):
        return str(date_str)


def truncate_text(text: Optional[str], max_len: int = 100) -> str:
    """
    ตัดข้อความให้สั้นลงพร้อมใส่จุดไข่ปลา (...) หากยาวเกินกำหนด
    """
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def get_current_date_str() -> str:
    """
    คืนค่าสตริงวันที่ปัจจุบันในรูปแบบ YYYY-MM-DD
    """
    return datetime.now().strftime("%Y-%m-%d")
