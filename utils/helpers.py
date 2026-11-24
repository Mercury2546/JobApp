"""
ฟังก์ชันตัวช่วยทั่วไปสำหรับ Career Agent
"""

from datetime import datetime


def format_date(
    date_str: str | None, input_fmt: str = "%Y-%m-%d", output_fmt: str = "%d/%m/%Y"
) -> str:
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


def truncate_text(text: str | None, max_len: int = 100) -> str:
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


def fetch_job_description_from_url(url: str, max_chars: int = 5000) -> dict:
    """
    ดึงเนื้อหาคำอธิบายตำแหน่งงาน (JD) จากลิงก์เว็บที่ระบุ
    พร้อมตัดแท็ก HTML และส่วนที่ไม่เกี่ยวข้องออกให้อัตโนมัติ
    """
    url_str = (url or "").strip()
    if not url_str:
        return {"success": False, "error": "ไม่ได้ระบุ URL ลิงก์", "text": "", "title": ""}

    if not url_str.startswith(("http://", "https://")):
        url_str = "https://" + url_str

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "th,en-US;q=0.9,en;q=0.8",
    }

    try:
        import requests
        from bs4 import BeautifulSoup

        response = requests.get(url_str, headers=headers, timeout=12)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # ดึงชื่อหน้าเว็บ
        page_title = (
            soup.title.string.strip() if soup.title and soup.title.string else ""
        )

        # ลบองค์ประกอบที่ไม่เกี่ยวข้องออก
        for tag in soup(
            [
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "noscript",
                "svg",
                "form",
                "iframe",
            ]
        ):
            tag.decompose()

        # ค้นหาส่วนเนื้อหาหลักก่อน (ถ้ามี)
        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find(
                class_=lambda c: (
                    c
                    and any(
                        k in str(c).lower()
                        for k in [
                            "job-desc",
                            "job_desc",
                            "description",
                            "details",
                            "posting",
                        ]
                    )
                )
            )
            or soup.body
        )

        target_element = main_content if main_content else soup
        raw_text = target_element.get_text(separator="\n")

        # ทำความสะอาดช่องว่างและบรรทัดว่าง
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        # ควบคุมความยาว
        if len(clean_text) > max_chars:
            clean_text = (
                clean_text[:max_chars]
                + "\n\n...[เนื้อหาถูกตัดให้กระชับเพื่อความเหมาะสมในการประมวลผล]..."
            )

        if not clean_text or len(clean_text) < 50:
            return {
                "success": False,
                "error": "ไม่พบเนื้อหาข้อความในหน้านี้ (อาจต้องเข้าสู่ระบบหรือเว็บไซต์ป้องกันการเข้าถึง)",
                "text": "",
                "title": page_title,
            }

        return {
            "success": True,
            "error": None,
            "text": clean_text,
            "title": page_title,
            "url": url_str,
        }

    except Exception as e:  # noqa: BLE001 — return user-friendly fetch error
        err_msg = str(e)
        if "timeout" in err_msg.lower():
            friendly_err = "การเชื่อมต่อหมดเวลา (Timeout) เว็บไซต์ตอบสนองช้าเกินไป"
        elif "403" in err_msg:
            friendly_err = (
                "เว็บไซต์ปฏิเสธการเข้าถึง (403 Forbidden - เว็บไซต์ป้องกัน Bot หรือต้องล็อกอิน)"
            )
        elif "404" in err_msg:
            friendly_err = "ไม่พบหน้านี้ (404 Not Found) ลิงก์อาจหมดอายุหรือไม่ถูกต้อง"
        else:
            friendly_err = f"เกิดข้อผิดพลาดในการดึงข้อมูล: {err_msg}"

        return {
            "success": False,
            "error": friendly_err,
            "text": "",
            "title": "",
            "url": url_str,
        }


def extract_job_details_from_image(
    image_bytes: bytes, mime_type: str = "image/jpeg"
) -> dict:
    """
    ใช้ AI Vision สแกนรูปภาพประกาศงาน (เช่น โปสเตอร์รับสมัครงาน, แคปหน้าจอจาก Facebook / LINE)
    พร้อมสกัดข้อมูล: บริษัท, ตำแหน่ง, เงินเดือน, อีเมลติดต่อ HR, สถานที่, และคุณสมบัติ/เนื้อหา JD
    """
    from services.ai_service import ai_service

    system_prompt = (
        "You are an expert OCR and Job Posting Information Extraction Specialist. "
        "Your task is to analyze images of job advertisements, hiring posters, Facebook screenshots, or infographics (in Thai or English) "
        "and extract all structured job details accurately."
    )

    user_prompt = """
กรุณาวิเคราะห์รูปภาพประกาศรับสมัครงานนี้ และสกัดข้อมูลสำคัญทั้งหมดอย่างละเอียด โดยตอบกลับในรูปแบบแท็กตามโครงสร้างนี้อย่างเคร่งครัด:

---
COMPANY: <ชื่อบริษัท หรือองค์กร หากไม่ระบุให้ใส่ ไม่ระบุ>
ROLE: <ชื่อตำแหน่งงานที่รับสมัคร>
SALARY: <ฐานเงินเดือน หรือผลตอบแทน เช่น 25,000 - 35,000 บาท หากไม่ระบุให้ใส่ ไม่ระบุ>
EMAIL_CONTACT: <อีเมลสำหรับส่งใบสมัคร หรือช่องทางติดต่อ HR เช่น hr@company.com หากไม่มีให้ใส่ ไม่ระบุ>
LOCATION: <สถานที่ทำงาน เช่น กรุงเทพฯ, BTS อโศก, WFH หากไม่ระบุให้ใส่ ไม่ระบุ>
JOB_DESCRIPTION:
<รายละเอียดหน้าที่ความรับผิดชอบ คุณสมบัติผู้สมัคร ทักษะที่ต้องการ และข้อกำหนดทั้งหมดที่ปรากฏในรูปภาพ เรียบเรียงเป็นภาษาไทยให้ครบถ้วนและอ่านง่าย>
---
"""

    try:
        raw_output = ai_service.generate_vision_response(
            image_bytes=image_bytes,
            mime_type=mime_type,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )

        company = ""
        role = ""
        salary = ""
        email_contact = ""
        location = ""
        jd_lines = []
        is_jd = False

        for line in raw_output.splitlines():
            line_str = line.strip()
            if line_str.startswith("---"):
                continue
            if line_str.upper().startswith("COMPANY:"):
                company = line_str.split(":", 1)[1].strip()
                if "ไม่ระบุ" in company:
                    company = ""
            elif line_str.upper().startswith("ROLE:"):
                role = line_str.split(":", 1)[1].strip()
                if "ไม่ระบุ" in role:
                    role = ""
            elif line_str.upper().startswith("SALARY:"):
                salary = line_str.split(":", 1)[1].strip()
                if "ไม่ระบุ" in salary:
                    salary = ""
            elif line_str.upper().startswith("EMAIL_CONTACT:"):
                email_contact = line_str.split(":", 1)[1].strip()
                if "ไม่ระบุ" in email_contact:
                    email_contact = ""
            elif line_str.upper().startswith("LOCATION:"):
                location = line_str.split(":", 1)[1].strip()
                if "ไม่ระบุ" in location:
                    location = ""
            elif line_str.upper().startswith("JOB_DESCRIPTION:"):
                is_jd = True
            elif is_jd:
                jd_lines.append(line)

        jd_text = "\n".join(jd_lines).strip()
        if not jd_text:
            jd_text = raw_output.strip()

        return {
            "success": True,
            "company": company,
            "role": role,
            "salary": salary,
            "email_contact": email_contact,
            "location": location,
            "job_description": jd_text,
            "raw_output": raw_output,
            "error": None,
        }

    except Exception as e:  # noqa: BLE001 — return user-friendly vision error
        return {
            "success": False,
            "company": "",
            "role": "",
            "salary": "",
            "email_contact": "",
            "location": "",
            "job_description": "",
            "raw_output": "",
            "error": str(e),
        }
