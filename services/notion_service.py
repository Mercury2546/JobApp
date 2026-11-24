"""
Notion Integration Service.
Manages direct communication with Notion Official REST API.
Enables 1-click sync of job applications and email cover letters into Notion Databases.
"""

import re
from typing import Any

import requests

from config.settings import (
    get_notion_api_key,
    get_notion_database_id,
    is_notion_configured,
)
from utils.logger import setup_logger

logger = setup_logger("notion_service")

NOTION_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"


def clean_notion_database_id(raw_id: str) -> str:
    """
    สกัดและแปลง Database ID จาก URL หรือรหัส Hex 32 ตัวอักษรให้เป็นรูปแบบที่ Notion API รองรับ
    เช่น จาก https://www.notion.so/myorg/1234567890abcdef1234567890abcdef?v=...
    จะสกัดได้ 12345678-90ab-cdef-1234-567890abcdef
    """
    if not raw_id:
        return ""

    raw_str = raw_id.strip()

    # กรณีเป็น URL หรือข้อความยาว ให้ค้นหารหัส Hex 32 ตัวอักษร
    match_hex = re.search(r"([0-9a-fA-F]{32})", raw_str)
    if match_hex:
        raw_hex = match_hex.group(1).lower()
        return f"{raw_hex[:8]}-{raw_hex[8:12]}-{raw_hex[12:16]}-{raw_hex[16:20]}-{raw_hex[20:]}"

    # กรณีมีขีดคั่น UUID อยู่แล้ว
    match_uuid = re.search(
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        raw_str,
    )
    if match_uuid:
        return match_uuid.group(1).lower()

    return raw_str


def get_notion_headers(api_key: str | None = None) -> dict[str, str]:
    """สร้าง Headers มาตรฐานสำหรับการเรียก Notion API"""
    key = (api_key or get_notion_api_key()).strip()
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def test_notion_connection(
    api_key: str | None = None, database_id: str | None = None
) -> dict[str, Any]:
    """
    ทดสอบการเชื่อมต่อไปยัง Notion Database
    ตรวจสอบว่า Token ถูกต้อง และได้กด Connect เข้าถึง Database นั้นแล้วหรือยัง
    """
    key = (api_key or get_notion_api_key()).strip()
    db_id = clean_notion_database_id(database_id or get_notion_database_id())

    if not key or not db_id:
        return {
            "success": False,
            "message": "ยังไม่ได้ระบุ Notion Token หรือ Database ID",
            "db_title": "",
        }

    url = f"{NOTION_API_BASE}/databases/{db_id}"
    try:
        response = requests.get(url, headers=get_notion_headers(key), timeout=10)
        if response.status_code == 200:
            data = response.json()
            title_objs = data.get("title", [])
            db_title = (
                "".join([t.get("plain_text", "") for t in title_objs])
                or "Untitled Database"
            )
            logger.info(f"เชื่อมต่อกับ Notion Database สำเร็จ: {db_title}")
            return {
                "success": True,
                "message": f"เชื่อมต่อสำเร็จกับ Notion Database: '{db_title}'",
                "db_title": db_title,
                "properties": data.get("properties", {}),
            }
        elif response.status_code == 401:
            return {
                "success": False,
                "message": "Notion Token ไม่ถูกต้อง หรือไม่มีสิทธิ์เข้าถึง (401 Unauthorized)",
                "db_title": "",
            }
        elif response.status_code == 404:
            # ตรวจสอบว่ามี Database ใดบ้างที่ Integration นี้มีสิทธิ์เข้าถึง (Auto-discovery)
            accessible_dbs = []
            try:
                search_res = requests.post(
                    f"{NOTION_API_BASE}/search",
                    headers=get_notion_headers(key),
                    json={"filter": {"value": "database", "property": "object"}},
                    timeout=8,
                )
                if search_res.status_code == 200:
                    for item in search_res.json().get("results", []):
                        t_objs = item.get("title", [])
                        t_str = (
                            "".join([t.get("plain_text", "") for t in t_objs])
                            or "Untitled Database"
                        )
                        accessible_dbs.append(
                            {
                                "id": item.get("id"),
                                "title": t_str,
                                "url": item.get("url")
                                or f"https://notion.so/{item.get('id', '').replace('-', '')}",
                            }
                        )
            except (requests.RequestException, ValueError) as e_search:
                logger.warning(
                    f"Error while searching accessible databases: {e_search}"
                )

            if accessible_dbs:
                suggest_msg = "\n\n💡 **ระบบตรวจพบตารางที่คุณ Connect ไว้แล้ว ดังนี้:**\n"
                for sdb in accessible_dbs:
                    suggest_msg += f"• **{sdb['title']}** — ID: `{sdb['id']}` ([เปิดดูใน Notion]({sdb['url']}))\n"
                return {
                    "success": False,
                    "message": f"ไม่พบ Database ตาม ID ที่ระบุ (404 Not Found){suggest_msg}",
                    "db_title": "",
                    "found_databases": accessible_dbs,
                }

            return {
                "success": False,
                "message": (
                    "ไม่พบ Database นี้ใน Notion (404 Not Found) "
                    "โปรดตรวจสอบ Database ID และอย่าลืมกดจุด 3 จุด '...' ที่มุมขวาบนของตารางใน Notion -> "
                    "เลือก 'Connect to' -> แล้วเลือกชื่อ Integration ของคุณเพื่ออนุญาตให้เข้าถึงก่อนครับ"
                ),
                "db_title": "",
            }
        else:
            err_data = response.json() if response.text else {}
            return {
                "success": False,
                "message": f"Notion API Error ({response.status_code}): {err_data.get('message', response.text)}",
                "db_title": "",
            }
    except (requests.RequestException, ValueError) as e:
        logger.error(f"เกิดข้อผิดพลาดในการทดสอบเชื่อมต่อ Notion: {e}")
        return {
            "success": False,
            "message": f"เกิดข้อผิดพลาดในการเชื่อมต่อ Notion: {e}",
            "db_title": "",
        }


def chunk_text_to_blocks(text: str) -> list[dict[str, Any]]:
    """
    แปลงข้อความยาว (เช่น เนื้อหาอีเมล) ให้เป็นรายการ Paragraph Blocks ของ Notion
    โดยจำกัดไม่ให้เกิน 2,000 ตัวอักษรต่อ Block ตามข้อกำหนดของ Notion API
    """
    if not text:
        return []

    blocks = []
    paragraphs = text.split("\n\n")

    for p in paragraphs:
        p_clean = p.strip()
        if not p_clean:
            continue

        # หากย่อหน้ายาวเกิน 1,900 ตัวอักษร ให้ตัดย่อย
        while p_clean:
            chunk = p_clean[:1900]
            p_clean = p_clean[1900:]

            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": chunk},
                            }
                        ]
                    },
                }
            )

    return blocks


def upload_image_to_public_host(
    image_bytes: bytes,
    file_name: str = "job_poster.png",
    mime_type: str = "image/png",
) -> str | None:
    """
    อัปโหลดรูปภาพ (เช่น ภาพโปสเตอร์หรือ Screenshot ประกาศงาน) ขึ้นบริการโฮสต์รูปภาพสาธารณะที่รองรับ Direct Link
    เพื่อให้สามารถแนบเข้าไปใน Notion Page (Property Files, Cover และ Image Block) ได้อย่างสมบูรณ์
    รองรับ Catbox.moe เป็นหลัก และมี Tmpfiles.org เป็นตัวสำรอง
    """
    if not image_bytes:
        return None

    clean_name = file_name or "job_poster.png"
    if not any(
        clean_name.lower().endswith(ext)
        for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]
    ):
        clean_name += ".png"

    # 1. Catbox.moe (ถาวร, เร็ว, รองรับ Notion API ได้ 100%)
    try:
        files = {"fileToUpload": (clean_name, image_bytes, mime_type)}
        data = {"reqtype": "fileupload"}
        resp = requests.post(
            "https://catbox.moe/user/api.php", data=data, files=files, timeout=15
        )
        if resp.status_code == 200 and resp.text.strip().startswith("http"):
            url = resp.text.strip()
            logger.info(f"อัปโหลดภาพโปสเตอร์ขึ้น Catbox สำเร็จ: {url}")
            return url
    except (requests.RequestException, ValueError) as e_catbox:
        logger.warning(f"Catbox upload failed: {e_catbox}, trying backup provider...")

    # 2. Tmpfiles.org (ตัวสำรอง)
    try:
        files = {"file": (clean_name, image_bytes, mime_type)}
        resp = requests.post(
            "https://tmpfiles.org/api/v1/upload", files=files, timeout=15
        )
        if resp.status_code == 200:
            res_json = resp.json()
            raw_url = res_json.get("data", {}).get("url", "")
            if raw_url:
                direct_url = raw_url.replace(
                    "https://tmpfiles.org/", "https://tmpfiles.org/dl/"
                )
                logger.info(f"อัปโหลดภาพโปสเตอร์ขึ้น Tmpfiles สำเร็จ: {direct_url}")
                return direct_url
    except (requests.RequestException, ValueError) as e_tmp:
        logger.warning(f"Tmpfiles upload failed: {e_tmp}")

    return None


def ensure_database_schema(
    api_key: str | None = None,
    database_id: str | None = None,
    existing_props: dict[str, Any] | None = None,
    current_title: str = "",
) -> dict[str, Any]:
    """
    ตรวจสอบและเพิ่มคอลัมน์มาตรฐานของตารางติดตามงาน (Company, Role, Status, Dates, Salary, Location, URL)
    ลงใน Notion Database อัตโนมัติผ่าน Notion API PATCH endpoint
    """
    key = (api_key or get_notion_api_key()).strip()
    db_id = clean_notion_database_id(database_id or get_notion_database_id())

    if not key or not db_id:
        return existing_props or {}

    props = existing_props or {}
    if not props:
        test_res = test_notion_connection(key, db_id)
        if test_res.get("success"):
            props = test_res.get("properties", {})
            current_title = current_title or test_res.get("db_title", "")

    existing_names_lower = {k.lower().strip(): k for k in props}
    props_to_add: dict[str, Any] = {}

    # 1. Company
    if not any(k in existing_names_lower for k in ["company", "บริษัท", "org"]):
        props_to_add["Company"] = {"rich_text": {}}

    # 2. Role
    if not any(k in existing_names_lower for k in ["role", "position", "ตำแหน่ง"]):
        props_to_add["Role"] = {"rich_text": {}}

    # 3. Status (Select with standard recruitment pipeline colors)
    if not any(k in existing_names_lower for k in ["status", "สถานะ", "stage"]):
        props_to_add["Status"] = {
            "select": {
                "options": [
                    {"name": "Wishlist", "color": "blue"},
                    {"name": "Applied", "color": "purple"},
                    {"name": "Interviewing", "color": "yellow"},
                    {"name": "Offered", "color": "green"},
                    {"name": "Rejected", "color": "red"},
                ]
            }
        }

    # 4. Applied Date
    if not any(
        k in existing_names_lower
        for k in ["applied date", "applied_date", "วันที่สมัคร", "applied"]
    ):
        props_to_add["Applied Date"] = {"date": {}}

    # 5. Follow-up Date
    if not any(
        k in existing_names_lower
        for k in ["follow-up date", "follow_up_date", "follow up", "วันที่ติดตาม"]
    ):
        props_to_add["Follow-up Date"] = {"date": {}}

    # 6. Location
    if not any(k in existing_names_lower for k in ["location", "สถานที่", "สถานที่ทำงาน"]):
        props_to_add["Location"] = {"rich_text": {}}

    # 7. Salary
    if not any(k in existing_names_lower for k in ["salary", "เงินเดือน", "ค่าตอบแทน"]):
        props_to_add["Salary"] = {"rich_text": {}}

    # 8. Job URL
    if not any(
        k in existing_names_lower for k in ["job url", "job_url", "url", "link", "ลิงก์"]
    ):
        props_to_add["Job URL"] = {"url": {}}

    # 9. Poster / Image (Files & Media)
    if not any(
        k in existing_names_lower
        for k in ["poster", "image", "รูปภาพ", "โปสเตอร์", "ภาพ", "ไฟล์"]
    ):
        props_to_add["Poster / Image"] = {"files": {}}

    if props_to_add:
        try:
            patch_url = f"{NOTION_API_BASE}/databases/{db_id}"
            patch_payload: dict[str, Any] = {"properties": props_to_add}

            # หากตารางยังเป็น Untitled หรือ New database ให้ตั้งชื่อให้เหมาะสม
            clean_title = current_title.strip().lower()
            if not clean_title or clean_title in [
                "untitled",
                "untitled database",
                "new database",
            ]:
                patch_payload["title"] = [
                    {"type": "text", "text": {"content": "💼 Job Application Tracker"}}
                ]

            resp = requests.patch(
                patch_url,
                headers=get_notion_headers(key),
                json=patch_payload,
                timeout=12,
            )
            if resp.status_code == 200:
                updated_data = resp.json()
                logger.info(
                    f"เพิ่มคอลัมน์มาตรฐานใน Notion Database สำเร็จ: {list(props_to_add.keys())}"
                )
                return updated_data.get("properties", props)
            else:
                logger.warning(
                    f"Failed to auto-update database columns ({resp.status_code}): {resp.text}"
                )
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"Error updating database schema: {e}")

    return props


def create_notion_job_page(
    company: str,
    role: str,
    status: str = "Applied",
    applied_date: str = "",
    follow_up_date: str = "",
    location: str = "",
    salary: str = "",
    job_url: str = "",
    email_subject: str = "",
    email_content: str = "",
    notes: str = "",
    image_url: str | None = None,
    image_bytes: bytes | None = None,
    image_name: str = "job_poster.png",
    image_mime: str = "image/png",
    api_key: str | None = None,
    database_id: str | None = None,
) -> dict[str, Any]:
    """
    สร้าง Page (แถวใหม่) ลงใน Notion Database โดยตรง
    รองรับการจับคู่คอลัมน์อัตโนมัติ, อัปโหลดภาพโปสเตอร์/Screenshot และนำเนื้อหาอีเมลไปบันทึกไว้ในหน้าด้านในของการ์ด
    """
    key = (api_key or get_notion_api_key()).strip()
    db_id = clean_notion_database_id(database_id or get_notion_database_id())

    if not key or not db_id:
        return {
            "success": False,
            "message": "ยังไม่ได้ระบุ Notion Token หรือ Database ID",
            "url": "",
        }

    # 1. ตรวจสอบ Schema ของ Database เพื่อจับคู่คอลัมน์ได้อย่างยืดหยุ่น
    test_res = test_notion_connection(key, db_id)
    if not test_res["success"]:
        return {
            "success": False,
            "message": test_res["message"],
            "url": "",
        }

    existing_props = test_res.get("properties", {})
    db_title = test_res.get("db_title", "")

    # ตรวจสอบและสร้างคอลัมน์มาตรฐานอัตโนมัติหากตารางยังขาดคอลัมน์ใดไป
    existing_props = ensure_database_schema(
        key, db_id, existing_props, current_title=db_title
    )

    # ค้นหาชื่อของคอลัมน์ที่เป็น Title (ชื่อเรื่องหลัก)
    title_prop_name = "Name"
    for prop_name, prop_data in existing_props.items():
        if prop_data.get("type") == "title":
            title_prop_name = prop_name
            break

    # สร้าง Properties ตามโครงสร้างตารางของผู้ใช้
    page_properties: dict[str, Any] = {
        title_prop_name: {
            "title": [{"text": {"content": f"{role.strip()} @ {company.strip()}"}}]
        }
    }

    # อัปโหลดภาพหากส่งมาเป็น binary bytes (เช่น จาก Facebook Poster / Screenshot)
    final_image_url = (image_url or "").strip()
    if not final_image_url and image_bytes:
        final_image_url = (
            upload_image_to_public_host(
                image_bytes=image_bytes,
                file_name=image_name,
                mime_type=image_mime,
            )
            or ""
        )

    # จับคู่คอลัมน์อื่นๆ หากมีอยู่ใน Database
    for prop_name, prop_data in existing_props.items():
        prop_lower = prop_name.lower()
        prop_type = prop_data.get("type")

        # Company
        if (
            any(k in prop_lower for k in ["company", "บริษัท", "org"])
            and prop_type == "rich_text"
        ):
            page_properties[prop_name] = {
                "rich_text": [{"text": {"content": company.strip()}}]
            }
        elif (
            any(k in prop_lower for k in ["company", "บริษัท", "org"])
            and prop_type == "select"
        ):
            page_properties[prop_name] = {"select": {"name": company.strip()[:100]}}

        # Role / Position
        elif (
            any(k in prop_lower for k in ["role", "position", "ตำแหน่ง", "job"])
            and prop_type == "rich_text"
            and prop_name != title_prop_name
        ):
            page_properties[prop_name] = {
                "rich_text": [{"text": {"content": role.strip()}}]
            }

        # Status
        elif any(
            k in prop_lower for k in ["status", "สถานะ", "stage"]
        ) and prop_type in ["select", "status"]:
            status_tag = status.strip() or "Applied"
            if prop_type == "select":
                page_properties[prop_name] = {"select": {"name": status_tag}}
            else:
                page_properties[prop_name] = {"status": {"name": status_tag}}

        # Applied Date
        elif (
            any(k in prop_lower for k in ["applied", "สมัคร", "application date"])
            and prop_type == "date"
            and applied_date
        ):
            page_properties[prop_name] = {"date": {"start": applied_date[:10]}}

        # Follow-up Date
        elif (
            any(k in prop_lower for k in ["follow", "ติดตาม"])
            and prop_type == "date"
            and follow_up_date
        ):
            page_properties[prop_name] = {"date": {"start": follow_up_date[:10]}}

        # Location
        elif (
            any(k in prop_lower for k in ["location", "สถานที่"])
            and prop_type == "rich_text"
            and location
        ):
            page_properties[prop_name] = {
                "rich_text": [{"text": {"content": location.strip()}}]
            }

        # Salary
        elif (
            any(k in prop_lower for k in ["salary", "เงินเดือน"])
            and prop_type == "rich_text"
            and salary
        ):
            page_properties[prop_name] = {
                "rich_text": [{"text": {"content": salary.strip()}}]
            }

        # Job URL
        elif (
            any(k in prop_lower for k in ["url", "link", "ลิงก์"])
            and prop_type == "url"
            and job_url
        ):
            clean_url = (
                job_url.strip()
                if job_url.strip().startswith(("http://", "https://"))
                else f"https://{job_url.strip()}"
            )
            page_properties[prop_name] = {"url": clean_url}

        # Poster / Image (Files & media)
        elif (
            any(
                k in prop_lower
                for k in ["poster", "image", "รูปภาพ", "โปสเตอร์", "ภาพ", "ไฟล์"]
            )
            and prop_type == "files"
            and final_image_url
        ):
            page_properties[prop_name] = {
                "files": [
                    {
                        "name": image_name or "job_poster.png",
                        "type": "external",
                        "external": {"url": final_image_url},
                    }
                ]
            }

    # 2. สร้าง Child Blocks (เนื้อหาด้านในของการ์ด Notion)
    child_blocks: list[dict[str, Any]] = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "💼"},
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"ข้อมูลตำแหน่งงาน: {role.strip()} ที่ {company.strip()}\n"
                            f"สถานะ: {status} • วันที่สมัคร: {applied_date or 'ไม่ระบุ'}\n"
                            f"สถานที่: {location or 'ไม่ระบุ'} • เงินเดือน: {salary or 'ไม่ระบุ'}"
                        },
                    }
                ],
            },
        }
    ]

    # ใส่ภาพโปสเตอร์ด้านในของการ์ด Notion (ถ้ามี)
    if final_image_url:
        child_blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "🖼️ ภาพประกาศงาน / โปสเตอร์รับสมัคร (Job Poster)"
                            },
                        }
                    ],
                },
            }
        )
        child_blocks.append(
            {
                "object": "block",
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {"url": final_image_url},
                },
            }
        )

    # บันทึกเนื้อหาอีเมลและ Cover Letter ที่ส่งไป
    if email_content:
        child_blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "✉️ อีเมลและจดหมายแนะนำตัว (Application Email)"
                            },
                        }
                    ],
                },
            }
        )
        if email_subject:
            child_blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": f"หัวข้ออีเมล: {email_subject.strip()}"
                                },
                            }
                        ],
                    },
                }
            )

        # แตกเนื้อหาอีเมลเป็น Blocks
        email_blocks = chunk_text_to_blocks(email_content)
        child_blocks.extend(email_blocks)

    if notes:
        child_blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "📝 บันทึกเพิ่มเติม"}}
                    ],
                },
            }
        )
        notes_blocks = chunk_text_to_blocks(notes)
        child_blocks.extend(notes_blocks)

    # 3. ส่งคำขอสร้าง Page ไปยัง Notion API
    payload: dict[str, Any] = {
        "parent": {"database_id": db_id},
        "icon": {"type": "emoji", "emoji": "📨"},
        "properties": page_properties,
        "children": child_blocks[:100],  # Notion อนุญาตสูงสุด 100 blocks ต่อ 1 คำขอ
    }

    # ตั้ง Cover ของหน้าการ์ดด้วยรูปภาพ (เพื่อให้ปรากฏรูปหน้าปกบน Gallery View)
    if final_image_url:
        payload["cover"] = {
            "type": "external",
            "external": {"url": final_image_url},
        }

    try:
        create_url = f"{NOTION_API_BASE}/pages"
        resp = requests.post(
            create_url, headers=get_notion_headers(key), json=payload, timeout=15
        )

        if resp.status_code in [200, 201]:
            page_data = resp.json()
            notion_url = page_data.get(
                "url", f"https://notion.so/{page_data.get('id', '').replace('-', '')}"
            )
            logger.info(f"สร้างการ์ดใน Notion สำเร็จ: {notion_url}")
            return {
                "success": True,
                "message": f"ส่งข้อมูลตำแหน่ง **{role}** ที่ **{company}** เข้า Notion สำเร็จเรียบร้อย!",
                "url": notion_url,
                "page_id": page_data.get("id", ""),
                "image_url": final_image_url,
            }
        else:
            err_json = resp.json() if resp.text else {}
            err_msg = err_json.get("message", resp.text)
            logger.error(
                f"Notion API error on page creation: {resp.status_code} - {err_msg}"
            )
            return {
                "success": False,
                "message": f"ไม่สามารถสร้างการ์ดใน Notion ได้ ({resp.status_code}): {err_msg}",
                "url": "",
            }

    except Exception as e:
        logger.exception("Unexpected error while sending to Notion")
        return {
            "success": False,
            "message": f"เกิดข้อผิดพลาดในการส่งข้อมูลเข้า Notion: {e}",
            "url": "",
        }


def save_notion_credentials(
    api_key: str, database_id: str, persist_to_env: bool = True
) -> bool:
    """
    บันทึก Notion API Token และ Database ID ลงใน session_state และไฟล์ .env
    """
    clean_db = clean_notion_database_id(database_id)
    key_clean = api_key.strip()

    try:
        import streamlit as st

        if hasattr(st, "session_state"):
            st.session_state["custom_notion_key"] = key_clean
            st.session_state["custom_notion_db_id"] = clean_db
    except Exception:  # noqa: BLE001, S110 — optional Streamlit session state
        pass

    if persist_to_env:
        try:
            from config.settings import ENV_FILE, reload_env

            env_content = ""
            if ENV_FILE.exists():
                with open(ENV_FILE, "r", encoding="utf-8") as f:
                    env_content = f.read()

            # อัปเดต NOTION_API_KEY
            if re.search(r"^NOTION_API_KEY=.*$", env_content, flags=re.MULTILINE):
                env_content = re.sub(
                    r"^NOTION_API_KEY=.*$",
                    f"NOTION_API_KEY={key_clean}",
                    env_content,
                    flags=re.MULTILINE,
                )
            else:
                env_content += f"\nNOTION_API_KEY={key_clean}\n"

            # อัปเดต NOTION_DATABASE_ID
            if re.search(r"^NOTION_DATABASE_ID=.*$", env_content, flags=re.MULTILINE):
                env_content = re.sub(
                    r"^NOTION_DATABASE_ID=.*$",
                    f"NOTION_DATABASE_ID={clean_db}",
                    env_content,
                    flags=re.MULTILINE,
                )
            else:
                env_content += f"NOTION_DATABASE_ID={clean_db}\n"

            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.write(env_content)

            reload_env()
            return True
        except OSError as e:
            logger.error(f"ไม่สามารถบันทึกค่าลง .env ได้: {e}")
            return False

    return True


def render_notion_config_expander(
    key_prefix: str = "main",
    title: str = "⚙️ ตั้งค่าและเชื่อมต่อ Notion Database (1-Click Sync)",
) -> bool:
    """
    แสดง Widget ตั้งค่า Notion Token และ Database ID ใน Streamlit
    คืนค่า True หากระบบพร้อมเชื่อมต่อ Notion
    """
    import streamlit as st

    current_key = get_notion_api_key()
    current_db = get_notion_database_id()
    configured = is_notion_configured()

    status_icon = "🟢" if configured else "⚪"
    status_text = "พร้อมเชื่อมต่อ Notion" if configured else "ยังไม่ได้ตั้งค่า Notion"

    with st.expander(f"{title} — {status_icon} {status_text}", expanded=not configured):
        st.markdown(
            """
            เชื่อมต่อ Notion เข้ากับระบบ เพื่อให้สามารถกดปุ่ม **"🚀 ส่งเข้า Notion ทันที"** แล้วข้อมูลตำแหน่งงานและเนื้อหาอีเมลจะเข้าไปปรากฏในการ์ดตาราง Notion ของคุณอัตโนมัติ
            """
        )

        n_col1, n_col2 = st.columns(2)
        with n_col1:
            token_input = st.text_input(
                "Notion Internal Integration Secret (Token) *",
                value=current_key,
                type="password",
                placeholder="ntn_... หรือ secret_...",
                help="คัดลอกจากหน้า Notion Developers (Connections)",
                key=f"{key_prefix}_notion_token_input",
            )
        with n_col2:
            db_input = st.text_input(
                "Notion Database ID หรือ URL ตาราง Notion *",
                value=current_db,
                placeholder="วาง URL ตาราง Notion หรือ 32-char ID",
                help="วางลิงก์ตาราง Notion ได้เลย ระบบจะสกัดรหัสให้เองอัตโนมัติ",
                key=f"{key_prefix}_notion_db_input",
            )

        btn_col1, btn_col2, _ = st.columns([2, 2, 3])
        with btn_col1:
            test_clicked = st.button(
                "🔌 ทดสอบการเชื่อมต่อ",
                key=f"{key_prefix}_test_notion_btn",
                use_container_width=True,
            )
        with btn_col2:
            save_clicked = st.button(
                "💾 บันทึกการตั้งค่า",
                key=f"{key_prefix}_save_notion_btn",
                use_container_width=True,
            )

        if test_clicked:
            if not token_input.strip() or not db_input.strip():
                st.warning("กรุณากรอกทั้ง Notion Token และ Database ID ก่อนทดสอบ")
            else:
                with st.spinner("กำลังทดสอบการเชื่อมต่อไปยัง Notion..."):
                    res = test_notion_connection(
                        api_key=token_input, database_id=db_input
                    )
                    if res["success"]:
                        st.success(f"🎉 {res['message']}")
                    else:
                        st.error(f"❌ {res['message']}")
                        found_dbs = res.get("found_databases", [])
                        if found_dbs:
                            st.info(
                                "💡 ตรวจพบตารางที่คุณ Connect ไว้แล้ว ต้องการสลับมาใช้อัตโนมัติหรือไม่?"
                            )
                            for f_idx, fdb in enumerate(found_dbs):
                                if st.button(
                                    f"👉 สลับมาใช้ตาราง '{fdb['title']}' นี้ทันที",
                                    key=f"{key_prefix}_use_found_db_{f_idx}",
                                ):
                                    save_notion_credentials(
                                        token_input, fdb["id"], persist_to_env=True
                                    )
                                    st.success(
                                        f"✅ บันทึกการเชื่อมต่อกับตาราง '{fdb['title']}' เรียบร้อยแล้ว!"
                                    )
                                    st.rerun()

        if save_clicked:
            if not token_input.strip() or not db_input.strip():
                st.warning("กรุณากรอกข้อมูลให้ครบถ้วนก่อนบันทึก")
            else:
                save_notion_credentials(token_input, db_input, persist_to_env=True)
                st.success("✅ บันทึกการตั้งค่า Notion ลงในระบบและไฟล์ .env เรียบร้อยแล้ว!")
                st.rerun()

        # คู่มือวิธีเชื่อมต่อ 3 ขั้นตอน
        with st.expander(
            "📖 วิธีหา Token และ Database ID ใน Notion (ทำครั้งเดียวเสร็จใน 1 นาที)"
        ):
            st.markdown(
                """
                1. **สร้าง Integration:**
                   * เข้าเว็บ [Notion My Integrations](https://www.notion.com/my-integrations)
                   * กดปุ่ม **"+ New integration"** ตั้งชื่อ เช่น `CareerWorkAgent`
                   * เลือก Workspace ของคุณ แล้วกด **Save**
                   * คัดลอกรหัส **"Internal Integration Secret"** (ขึ้นต้นด้วย `ntn_...` หรือ `secret_...`) มาวางในช่อง Token
                2. **ดึง Database ID:**
                   * เปิดหน้าตาราง/Database ใน Notion ที่ต้องการเก็บข้อมูล
                   * คัดลอก URL ของหน้านั้นจาก Address Bar มาวางในช่อง Database ID ได้ทันที
                3. **กดแชร์สิทธิ์ให้ Integration เข้าถึง (สำคัญมาก!):**
                   * ในหน้าตาราง Notion ของคุณ ให้คลิกที่ **จุดสามจุด `...`** ที่มุมขวาบนสุดของหน้า
                   * เลื่อนลงมาเลือก **"Connect to"** (หรือ **"Add connections"**)
                   * ค้นหาและคลิกเลือกชื่อ **CareerWorkAgent** ที่คุณสร้างไว้
                   * เพียงเท่านี้ก็พร้อมใช้งาน 1-Click Sync แล้ว!
                """
            )

    return is_notion_configured()
