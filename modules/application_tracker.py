"""
โมดูลที่ 6: ระบบติดตามการสมัครงาน (Application Tracker)
ระบบจัดการสถานะการสมัครงานแบบ CRUD บนฐานข้อมูล SQLite
รองรับการติดตามแบบไปป์ไลน์ (Kanban), ค้นหาตำแหน่งงาน, เก็บประวัติเนื้อหาอีเมลที่ส่ง และส่งออกเป็น Excel / Notion
"""

import io
from datetime import date

import pandas as pd
import streamlit as st

from database.db import get_db_connection
from services.notion_service import (
    create_notion_job_page,
    is_notion_configured,
    render_notion_config_expander,
)
from utils.helpers import format_date, get_current_date_str
from utils.logger import setup_logger

logger = setup_logger("application_tracker")

# รายการสถานะและป้ายแสดงสถานะ (Status Badges)
VALID_STATUSES = ["Wishlist", "Applied", "Interviewing", "Offered", "Rejected"]

STATUS_LABELS = {
    "Wishlist": "📌 สนใจ (Wishlist)",
    "Applied": "📨 สมัครแล้ว (Applied)",
    "Interviewing": "🎙️ สัมภาษณ์ (Interviewing)",
    "Offered": "🎉 ได้รับข้อเสนอ (Offered)",
    "Rejected": "❌ ไม่ผ่านคัดเลือก (Rejected)",
}


# ==========================================
# จัดการฐานข้อมูล (Database CRUD Operations)
# ==========================================


def add_application(
    company: str,
    role: str,
    location: str = "",
    salary: str = "",
    job_url: str = "",
    status: str = "Wishlist",
    applied_date: str = "",
    notes: str = "",
    email_subject: str = "",
    email_content: str = "",
    follow_up_date: str = "",
    image_url: str = "",
) -> int:
    """เพิ่มข้อมูลการสมัครงานใหม่ลงในฐานข้อมูล SQLite พร้อมบันทึกเนื้อหาอีเมลและรูปภาพโปสเตอร์"""
    if status not in VALID_STATUSES:
        status = "Wishlist"

    query = """
    INSERT INTO applications (
        company, role, location, salary, job_url, status,
        applied_date, notes, email_subject, email_content, follow_up_date, image_url
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    company.strip(),
                    role.strip(),
                    location.strip(),
                    salary.strip(),
                    job_url.strip(),
                    status,
                    applied_date,
                    notes.strip(),
                    email_subject.strip(),
                    email_content.strip(),
                    follow_up_date.strip(),
                    image_url.strip(),
                ),
            )
            new_id = cursor.lastrowid
            logger.info(f"เพิ่มงานใหม่สำเร็จ ID {new_id}: {company} - {role}")
            return new_id
    except Exception:
        logger.exception("เกิดข้อผิดพลาดในการเพิ่มงาน")
        raise


def get_all_applications(
    status_filter: str | None = None, search_term: str | None = None
) -> list[dict]:
    """ค้นหาและดึงข้อมูลการสมัครงานทั้งหมดตามตัวกรองและคำค้นหา"""
    query = "SELECT * FROM applications WHERE 1=1"
    params: list = []

    if status_filter and status_filter in VALID_STATUSES:
        query += " AND status = ?"
        params.append(status_filter)

    if search_term and search_term.strip():
        term = f"%{search_term.strip()}%"
        query += " AND (company LIKE ? OR role LIKE ? OR location LIKE ? OR notes LIKE ? OR email_subject LIKE ?)"
        params.extend([term, term, term, term, term])

    query += " ORDER BY updated_at DESC, id DESC;"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("เกิดข้อผิดพลาดในการดึงข้อมูลการสมัครงาน")
        return []


def update_application(
    app_id: int,
    company: str,
    role: str,
    location: str,
    salary: str,
    job_url: str,
    status: str,
    applied_date: str,
    notes: str,
    email_subject: str = "",
    email_content: str = "",
    follow_up_date: str = "",
    image_url: str = "",
) -> bool:
    """อัปเดตข้อมูลรายละเอียดการสมัครงาน"""
    if status not in VALID_STATUSES:
        status = "Wishlist"

    query = """
    UPDATE applications
    SET company = ?, role = ?, location = ?, salary = ?, job_url = ?, status = ?,
        applied_date = ?, notes = ?, email_subject = ?, email_content = ?, follow_up_date = ?,
        image_url = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?;
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    company.strip(),
                    role.strip(),
                    location.strip(),
                    salary.strip(),
                    job_url.strip(),
                    status,
                    applied_date,
                    notes.strip(),
                    email_subject.strip(),
                    email_content.strip(),
                    follow_up_date.strip(),
                    image_url.strip(),
                    app_id,
                ),
            )
            logger.info(f"อัปเดตข้อมูลงาน ID {app_id} สำเร็จ")
            return cursor.rowcount > 0
    except Exception:
        logger.exception(f"เกิดข้อผิดพลาดในการอัปเดตงาน ID {app_id}")
        raise


def update_application_status(app_id: int, new_status: str) -> bool:
    """เปลี่ยนสถานะงานอย่างรวดเร็ว (สำหรับบอร์ด Kanban)"""
    if new_status not in VALID_STATUSES:
        raise ValueError(f"สถานะไม่ถูกต้อง: {new_status}")

    query = "UPDATE applications SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (new_status, app_id))
            logger.info(f"เปลี่ยนสถานะงาน ID {app_id} เป็น {new_status}")
            return cursor.rowcount > 0
    except Exception:
        logger.exception(f"เกิดข้อผิดพลาดในการเปลี่ยนสถานะงาน ID {app_id}")
        raise


def delete_application(app_id: int) -> bool:
    """ลบข้อมูลการสมัครงานตาม ID"""
    query = "DELETE FROM applications WHERE id = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (app_id,))
            logger.info(f"ลบข้อมูลงาน ID {app_id} สำเร็จ")
            return cursor.rowcount > 0
    except Exception:
        logger.exception(f"เกิดข้อผิดพลาดในการลบงาน ID {app_id}")
        raise


def get_status_counts() -> dict[str, int]:
    """คำนวณจำนวนงานในแต่ละสถานะ"""
    counts = {s: 0 for s in VALID_STATUSES}
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status;"
            )
            for row in cursor.fetchall():
                if row["status"] in counts:
                    counts[row["status"]] = row["cnt"]
    except Exception as e:  # noqa: BLE001 — fallback to zero counts
        logger.error(f"เกิดข้อผิดพลาดในการคำนวณสถิติสถานะ: {e}")
    return counts


# ==========================================
# ระบบส่งออกข้อมูล (Export to Excel & Notion)
# ==========================================


def get_applications_dataframe(
    status_filter: str | None = None, search_term: str | None = None
) -> pd.DataFrame:
    """สร้าง pandas DataFrame สรุปข้อมูลทั้งหมดพร้อมหัวคอลัมน์ภาษาไทยสำหรับเปิดใน Excel"""
    apps = get_all_applications(status_filter=status_filter, search_term=search_term)
    if not apps:
        return pd.DataFrame()

    rows = []
    for app in apps:
        rows.append(
            {
                "รหัส": app.get("id"),
                "บริษัท": app.get("company"),
                "ตำแหน่งงาน": app.get("role"),
                "สถานะ": STATUS_LABELS.get(app.get("status"), app.get("status")),
                "วันที่สมัคร": app.get("applied_date") or "-",
                "วันที่ต้องติดตามผล (Follow-up)": app.get("follow_up_date") or "-",
                "สถานที่": app.get("location") or "-",
                "เงินเดือน": app.get("salary") or "-",
                "หัวข้ออีเมล": app.get("email_subject") or "-",
                "เนื้อหาอีเมล/Cover Letter": app.get("email_content") or "-",
                "ลิงก์งาน": app.get("job_url") or "-",
                "บันทึกเพิ่มเติม": app.get("notes") or "-",
                "บันทึกเข้าระบบ": app.get("created_at") or "-",
                "อัปเดตล่าสุด": app.get("updated_at") or "-",
            }
        )
    return pd.DataFrame(rows)


def get_notion_ready_dataframe(
    status_filter: str | None = None, search_term: str | None = None
) -> pd.DataFrame:
    """สร้าง DataFrame สำหรับส่งออกเป็น Notion-Ready CSV ที่แมปเข้า Properties ของ Notion ได้ทันที"""
    apps = get_all_applications(status_filter=status_filter, search_term=search_term)
    if not apps:
        return pd.DataFrame()

    rows = []
    for app in apps:
        rows.append(
            {
                "Name": f"{app.get('role')} @ {app.get('company')}",
                "Company": app.get("company"),
                "Role": app.get("role"),
                "Status": app.get("status"),
                "Applied Date": app.get("applied_date") or "",
                "Follow-up Date": app.get("follow_up_date") or "",
                "Location": app.get("location") or "",
                "Salary": app.get("salary") or "",
                "Job URL": app.get("job_url") or "",
                "Email Subject": app.get("email_subject") or "",
                "Email Body": app.get("email_content") or "",
                "Notes": app.get("notes") or "",
            }
        )
    return pd.DataFrame(rows)


def generate_excel_bytes(df: pd.DataFrame) -> bytes:
    """แปลง DataFrame เป็นไฟล์ Excel (.xlsx) แบบ Binary ด้วย openpyxl"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Job Applications")
    return output.getvalue()


# ==========================================
# หน้าจอแสดงผล (Streamlit UI Views)
# ==========================================


def render_add_application_form():
    """ฟอร์มสำหรับเพิ่มข้อมูลการสมัครงานใหม่"""
    st.subheader("➕ บันทึกข้อมูลการสมัครงานใหม่")
    st.write("บันทึกตำแหน่งงาน บริษัท ขั้นตอน และประวัติอีเมลที่ส่งเพื่อไม่ให้พลาดทุกโอกาส")

    # ตัวเลือกตำแหน่งงานอยู่นอก form เพื่อให้สลับช่องพิมพ์เองได้ทันที
    role_presets = [
        "🎨 Graphic Designer",
        "✨ UX/UI Designer",
        "🖌️ Graphic & Content Creator",
        "📱 Product Designer (UI/UX)",
        "💻 Web & Graphic Designer",
        "✏️ พิมพ์ระบุตำแหน่งอื่นเอง...",
    ]
    selected_preset = st.radio(
        "ตำแหน่งงานที่สมัคร * (กดเลือกได้ทันที)",
        role_presets,
        index=0,
        horizontal=True,
        key="add_app_role_preset",
    )

    with st.form("add_application_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input(
                "ชื่อบริษัท / องค์กร *", placeholder="เช่น Google, SCB TechX, Agoda"
            )
            if selected_preset == "✏️ พิมพ์ระบุตำแหน่งอื่นเอง...":
                role = st.text_input(
                    "พิมพ์ชื่อตำแหน่งงาน *",
                    placeholder="เช่น Senior UX/UI Specialist, Motion Artist",
                )
            else:
                role = (
                    selected_preset.replace("🎨 ", "")
                    .replace("✨ ", "")
                    .replace("🖌️ ", "")
                    .replace("📱 ", "")
                    .replace("💻 ", "")
                    .replace("🎯 ", "")
                    .strip()
                )
                st.text_input("ตำแหน่งงานที่เลือก", value=role, disabled=True)

            location = st.text_input(
                "สถานที่ทำงาน", placeholder="เช่น กรุงเทพฯ / Hybrid / Remote 100%"
            )
        with col2:
            status_index = 0
            status_selected = st.selectbox(
                "สถานะปัจจุบัน",
                VALID_STATUSES,
                format_func=lambda s: STATUS_LABELS.get(s, s),
                index=status_index,
            )
            salary = st.text_input(
                "ฐานเงินเดือน / ผลตอบแทน", placeholder="เช่น 80,000 - 120,000 บาท/เดือน"
            )
            applied_date = st.date_input("วันที่สมัคร", value=date.today())

        col3, col4 = st.columns(2)
        with col3:
            follow_up_date = st.date_input(
                "วันที่ควรติดตามผล (Follow-up Date)", value=date.today()
            )
        with col4:
            job_url = st.text_input(
                "ลิงก์ประกาศรับสมัครงาน (URL)",
                placeholder="https://linkedin.com/jobs/view/...",
            )

        with st.expander("✉️ บันทึกหัวข้อและเนื้อหาอีเมล / Cover Letter ที่ส่งไป (ไม่บังคับ)"):
            email_subject = st.text_input(
                "หัวข้ออีเมล (Subject Line)",
                placeholder="เช่น Application for Senior Python Engineer - Somchai",
            )
            email_content = st.text_area(
                "เนื้อหาอีเมล / จดหมายปะหน้า (Email Body)",
                height=150,
                placeholder="วางเนื้อหาอีเมลหรือ Cover letter ที่ส่งไปจริง...",
            )

        notes = st.text_area(
            "บันทึกเพิ่มเติม / ข้อมูลผู้ติดต่อ",
            placeholder="ชื่อผู้ติดต่อ HR, ข้อมูลรอบสัมภาษณ์, ข้อมูลผู้แนะนำ (Referral)...",
        )

        submitted = st.form_submit_button(
            "💾 บันทึกข้อมูลการสมัครงาน", use_container_width=True
        )

        if submitted:
            if not company.strip() or not role.strip():
                st.error("กรุณาระบุทั้งชื่อบริษัทและตำแหน่งงาน")
            else:
                try:
                    add_application(
                        company=company,
                        role=role,
                        location=location,
                        salary=salary,
                        job_url=job_url,
                        status=status_selected,
                        applied_date=str(applied_date),
                        notes=notes,
                        email_subject=email_subject,
                        email_content=email_content,
                        follow_up_date=str(follow_up_date),
                    )
                    st.toast(f"✅ บันทึกตำแหน่ง {role} ที่ {company} เรียบร้อยแล้ว!")
                    st.rerun()
                except Exception as e:  # noqa: BLE001 — show DB error in UI
                    st.error(f"เกิดข้อผิดพลาดในการบันทึก: {e}")


def render_pipeline_view():
    """มุมมองกระดาน Kanban ติดตามสถานะงาน"""
    st.subheader("📊 กระดานติดตามสถานะการสมัครงาน (Kanban Pipeline)")
    counts = get_status_counts()
    today_str = str(date.today())

    # แสดงตัวเลขสถิติสรุป
    cols = st.columns(len(VALID_STATUSES))
    for i, st_name in enumerate(VALID_STATUSES):
        with cols[i]:
            st.metric(label=STATUS_LABELS[st_name], value=f"{counts[st_name]} งาน")

    st.divider()

    # เสาคอลัมน์ Kanban
    kanban_cols = st.columns(len(VALID_STATUSES))
    badge_classes = {
        "Wishlist": "badge-indigo",
        "Applied": "badge-cyan",
        "Interviewing": "badge-amber",
        "Offered": "badge-emerald",
        "Rejected": "badge-rose",
    }

    for idx, st_name in enumerate(VALID_STATUSES):
        with kanban_cols[idx]:
            b_class = badge_classes.get(st_name, "badge-indigo")
            st.markdown(
                f"""
                <div style="margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
                    <span class="card-badge {b_class}" style="margin: 0; font-size: 12px; padding: 5px 10px;">
                        {STATUS_LABELS[st_name]}
                    </span>
                    <span style="font-size: 12px; font-weight: 700; color: #94A3B8; background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 10px;">
                        {counts[st_name]}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            apps_in_stage = get_all_applications(status_filter=st_name)

            if not apps_in_stage:
                st.caption("ยังไม่มีรายการในขั้นตอนนี้")
            else:
                for app in apps_in_stage:
                    is_light_theme = st.session_state.get("app_theme") == "light"
                    company_color = "#0F172A" if is_light_theme else "#FFFFFF"
                    role_color = "#4338CA" if is_light_theme else "#A5B4FC"
                    with st.container(border=True):
                        st.markdown(
                            f"<div style='font-size: 15px; font-weight: 700; color: {company_color};'>{app['company']}</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f"<div style='font-size: 13px; font-weight: 600; color: {role_color}; margin-bottom: 6px;'>💼 {app['role']}</div>",
                            unsafe_allow_html=True,
                        )

                        meta_items = []
                        if app.get("location"):
                            meta_items.append(f"📍 {app['location']}")
                        if app.get("salary"):
                            meta_items.append(f"💰 {app['salary']}")
                        if app.get("applied_date"):
                            meta_items.append(f"📅 {format_date(app['applied_date'])}")

                        for m in meta_items:
                            st.caption(m)

                        # แจ้งเตือน Follow-up
                        if app.get("follow_up_date"):
                            f_date = app["follow_up_date"]
                            if app["status"] == "Applied" and f_date <= today_str:
                                st.warning(f"⚠️ ถึงวัน Follow-up! ({format_date(f_date)})")
                            else:
                                st.caption(f"⏰ Follow-up: {format_date(f_date)}")

                        # ป้ายบอกว่ามีอีเมลแนบไว้
                        if app.get("email_content"):
                            st.info("✉️ มีประวัติอีเมลที่บันทึกไว้")

                        # เลือดย้ายสถานะอย่างรวดเร็ว
                        current_idx = (
                            VALID_STATUSES.index(app["status"])
                            if app.get("status") in VALID_STATUSES
                            else 0
                        )
                        new_status = st.selectbox(
                            "ย้ายสถานะ",
                            VALID_STATUSES,
                            format_func=lambda s: STATUS_LABELS.get(s, s),
                            index=current_idx,
                            key=f"move_{app['id']}",
                            label_visibility="collapsed",
                        )
                        if new_status != app["status"]:
                            update_application_status(app["id"], new_status)
                            st.rerun()

                        # ปุ่มส่งเข้า Notion ทันที
                        if st.button(
                            "🚀 ส่งเข้า Notion",
                            key=f"kanban_notion_{app['id']}",
                            use_container_width=True,
                        ):
                            if not is_notion_configured():
                                st.warning(
                                    "ยังไม่ได้ตั้งค่า Notion กรุณาไปที่แท็บ '📥 ส่งออกข้อมูล' เพื่อเชื่อมต่อ"
                                )
                            else:
                                with st.spinner("กำลังส่งเข้า Notion..."):
                                    n_res = create_notion_job_page(
                                        company=app["company"],
                                        role=app["role"],
                                        status=app["status"],
                                        applied_date=app.get("applied_date") or "",
                                        follow_up_date=app.get("follow_up_date") or "",
                                        location=app.get("location") or "",
                                        salary=app.get("salary") or "",
                                        job_url=app.get("job_url") or "",
                                        email_subject=app.get("email_subject") or "",
                                        email_content=app.get("email_content") or "",
                                        notes=app.get("notes") or "",
                                        image_url=app.get("image_url") or "",
                                    )
                                    if n_res["success"]:
                                        st.success("✅ ส่งเข้า Notion แล้ว!")
                                        st.markdown(
                                            f"[👉 เปิดใน Notion]({n_res['url']})"
                                        )
                                    else:
                                        st.error(n_res["message"])


def render_list_view():
    """มุมมองตารางรายการ ค้นหา และแก้ไข/ลบ"""
    st.subheader("📋 คลังรายการสมัครงานทั้งหมด")

    col_search, col_filter = st.columns([3, 1])
    with col_search:
        search_query = st.text_input(
            "🔍 ค้นหาตามชื่อบริษัท, ตำแหน่ง, หรือคีย์เวิร์ด", placeholder="พิมพ์เพื่อค้นหา..."
        )
    with col_filter:
        filter_options = ["ทั้งหมด"] + VALID_STATUSES
        filter_status = st.selectbox(
            "กรองตามสถานะ",
            filter_options,
            format_func=lambda s: "ทั้งหมด" if s == "ทั้งหมด" else STATUS_LABELS.get(s, s),
        )

    selected_status = None if filter_status == "ทั้งหมด" else filter_status
    applications = get_all_applications(
        status_filter=selected_status, search_term=search_query
    )

    st.write(f"พบรายการทั้งหมด **{len(applications)}** รายการ")

    if not applications:
        st.info(
            "ไม่พบรายการสมัครงานที่ตรงกับเงื่อนไข สามารถเพิ่มได้ที่แท็บ 'เพิ่มข้อมูลการสมัครงาน' หรือใช้โมดูล '✉️ ร่างอีเมลสมัครงาน'"
        )
        return

    today_str = str(date.today())

    for app in applications:
        badge = STATUS_LABELS.get(app["status"], app["status"])
        email_indicator = " ✉️" if app.get("email_content") else ""
        header_text = f"{badge} — **{app['company']}** : {app['role']}{email_indicator}"

        with st.expander(header_text):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**บริษัท:** {app['company']}")
                st.write(f"**ตำแหน่ง:** {app['role']}")
                st.write(f"**สถานที่:** {app['location'] or 'ไม่ระบุ'}")
                st.write(f"**เงินเดือน:** {app['salary'] or 'ไม่ระบุ'}")
            with col2:
                st.write(
                    f"**สถานะ:** {STATUS_LABELS.get(app['status'], app['status'])}"
                )
                st.write(f"**วันที่สมัคร:** {format_date(app['applied_date'])}")
                if app.get("follow_up_date"):
                    if (
                        app["status"] == "Applied"
                        and app["follow_up_date"] <= today_str
                    ):
                        st.error(
                            f"⚠️ **วันที่ต้องติดตามผล (Follow-up):** {format_date(app['follow_up_date'])} (ถึงกำหนดแล้ว)"
                        )
                    else:
                        st.write(
                            f"**วันที่ต้องติดตามผล (Follow-up):** {format_date(app['follow_up_date'])}"
                        )
                if app.get("job_url"):
                    st.markdown(f"**ลิงก์งาน:** [เปิดดูประกาศรับสมัคร]({app['job_url']})")
                st.write(f"**บันทึกเมื่อ:** {app['created_at']}")

            # ส่วนแสดงเนื้อหาอีเมลที่เคยเขียนไว้
            if app.get("email_content"):
                with st.expander("✉️ ดูเนื้อหาอีเมล / Cover Letter ที่บันทึกไว้", expanded=False):
                    if app.get("email_subject"):
                        st.markdown(f"**หัวข้ออีเมล:** `{app['email_subject']}`")
                    st.text_area(
                        "เนื้อหาที่ส่งไป",
                        value=app["email_content"],
                        height=200,
                        disabled=True,
                        key=f"view_email_{app['id']}",
                    )

            if app.get("notes"):
                st.info(f"**บันทึกเพิ่มเติม:**\n\n{app['notes']}")

            # ปุ่มแก้ไข, ลบ และส่งเข้า Notion
            bcol1, bcol2, bcol3 = st.columns([1, 1, 2])
            with bcol1:
                if st.button("✏️ แก้ไข", key=f"edit_btn_{app['id']}"):
                    st.session_state["edit_app_id"] = app["id"]
                    st.rerun()
            with bcol2:
                if st.button("🗑️ ลบ", key=f"del_btn_{app['id']}", type="secondary"):
                    delete_application(app["id"])
                    st.toast(f"🗑️ ลบรายการของบริษัท {app['company']} เรียบร้อยแล้ว")
                    st.rerun()
            with bcol3:
                if st.button("🚀 ส่งเข้า Notion ทันที", key=f"list_notion_btn_{app['id']}"):
                    if not is_notion_configured():
                        st.warning(
                            "ยังไม่ได้ตั้งค่า Notion กรุณาไปที่แท็บ '📥 ส่งออกข้อมูล' ด้านบนเพื่อเชื่อมต่อ"
                        )
                    else:
                        with st.spinner("กำลังส่งเข้า Notion..."):
                            n_res = create_notion_job_page(
                                company=app["company"],
                                role=app["role"],
                                status=app["status"],
                                applied_date=app.get("applied_date") or "",
                                follow_up_date=app.get("follow_up_date") or "",
                                location=app.get("location") or "",
                                salary=app.get("salary") or "",
                                job_url=app.get("job_url") or "",
                                email_subject=app.get("email_subject") or "",
                                email_content=app.get("email_content") or "",
                                notes=app.get("notes") or "",
                                image_url=app.get("image_url") or "",
                            )
                            if n_res["success"]:
                                st.success(
                                    f"✅ ส่งตำแหน่ง {app['role']} เข้า Notion สำเร็จ!"
                                )
                                st.markdown(
                                    f"[👉 เปิดดูการ์ดงานนี้ใน Notion]({n_res['url']})"
                                )
                            else:
                                st.error(f"❌ {n_res['message']}")


def render_edit_view(app_id: int):
    """หน้าจอแก้ไขข้อมูลงาน"""
    st.subheader(f"✏️ แก้ไขข้อมูลการสมัครงาน #{app_id}")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM applications WHERE id = ?;", (app_id,))
            row = cursor.fetchone()
            if not row:
                st.error("ไม่พบรายการสมัครงานนี้ในระบบ")
                if st.button("กลับไปยังหน้ารายการ"):
                    st.session_state.pop("edit_app_id", None)
                    st.rerun()
                return
            app = dict(row)
    except Exception as e:  # noqa: BLE001 — show DB error in UI
        st.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")
        return

    with st.form(f"edit_form_{app_id}"):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input("ชื่อบริษัท / องค์กร *", value=app["company"])
            role = st.text_input("ตำแหน่งงานที่สมัคร *", value=app["role"])
            location = st.text_input("สถานที่ทำงาน", value=app["location"] or "")
        with col2:
            status_index = (
                VALID_STATUSES.index(app["status"])
                if app["status"] in VALID_STATUSES
                else 0
            )
            status = st.selectbox(
                "สถานะปัจจุบัน",
                VALID_STATUSES,
                format_func=lambda s: STATUS_LABELS.get(s, s),
                index=status_index,
            )
            salary = st.text_input("ฐานเงินเดือน / ผลตอบแทน", value=app["salary"] or "")
            applied_date = st.text_input(
                "วันที่สมัคร (YYYY-MM-DD)",
                value=app["applied_date"] or get_current_date_str(),
            )

        col3, col4 = st.columns(2)
        with col3:
            follow_up_date = st.text_input(
                "วันที่ควรติดตามผล (YYYY-MM-DD)", value=app.get("follow_up_date") or ""
            )
        with col4:
            job_url = st.text_input(
                "ลิงก์ประกาศรับสมัครงาน (URL)", value=app["job_url"] or ""
            )

        with st.expander("✉️ แก้ไขหัวข้อและเนื้อหาอีเมล / Cover Letter ที่บันทึกไว้"):
            email_subject = st.text_input(
                "หัวข้ออีเมล (Subject Line)", value=app.get("email_subject") or ""
            )
            email_content = st.text_area(
                "เนื้อหาอีเมล / Cover Letter",
                value=app.get("email_content") or "",
                height=180,
            )

        notes = st.text_area("บันทึกเพิ่มเติม", value=app["notes"] or "")

        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            save_clicked = st.form_submit_button(
                "💾 บันทึกการแก้ไข", use_container_width=True
            )
        with sub_col2:
            cancel_clicked = st.form_submit_button("ยกเลิก", use_container_width=True)

        if save_clicked:
            if not company.strip() or not role.strip():
                st.error("ชื่อบริษัทและตำแหน่งงานต้องไม่เว้นว่าง")
            else:
                update_application(
                    app_id=app_id,
                    company=company,
                    role=role,
                    location=location,
                    salary=salary,
                    job_url=job_url,
                    status=status,
                    applied_date=applied_date,
                    notes=notes,
                    email_subject=email_subject,
                    email_content=email_content,
                    follow_up_date=follow_up_date,
                    image_url=app.get("image_url") or "",
                )
                st.session_state.pop("edit_app_id", None)
                st.toast("✅ อัปเดตข้อมูลเรียบร้อยแล้ว!")
                st.rerun()

        if cancel_clicked:
            st.session_state.pop("edit_app_id", None)
            st.rerun()


def render_export_view():
    """หน้าจอสำหรับส่งออกข้อมูลการสมัครงานเป็น Excel และ Notion CSV"""
    st.subheader("📥 ศูนย์ส่งออกข้อมูลการสมัครงาน (Export to Excel & Notion)")
    st.write(
        "ดาวน์โหลดข้อมูลการสมัครงานทั้งหมดของคุณไปใช้งานต่อใน Microsoft Excel, Google Sheets หรือนำเข้า Notion Database ได้อย่างง่ายดาย"
    )

    df_thai = get_applications_dataframe()
    df_notion = get_notion_ready_dataframe()

    if df_thai.empty:
        st.info("ยังไม่มีข้อมูลการสมัครงานในระบบ กรุณาเพิ่มข้อมูลหรือใช้โมดูลร่างอีเมลเพื่อเริ่มบันทึกข้อมูล")
        return

    st.write(f"พร้อมส่งออกข้อมูลทั้งหมด **{len(df_thai)}** รายการ")

    # พรีวิวตารางข้อมูล
    with st.expander("👁️ พรีวิวตารางข้อมูลที่จะส่งออก", expanded=True):
        st.dataframe(
            df_thai[
                [
                    "บริษัท",
                    "ตำแหน่งงาน",
                    "สถานะ",
                    "วันที่สมัคร",
                    "วันที่ต้องติดตามผล (Follow-up)",
                    "หัวข้ออีเมล",
                ]
            ],
            use_container_width=True,
        )

    # --- ส่วนที่ 1: Direct Notion API Sync ---
    st.markdown(
        "### 🚀 ตัวเลือกที่ 1: ซิงค์ตรงเข้าสู่ Notion Database (1-Click Sync ไม่ต้องโหลดไฟล์)"
    )
    st.caption(
        "ส่งข้อมูลการสมัครงานทั้งหมดในระบบขึ้นไปสร้างเป็นการ์ดใน Notion Database ของคุณโดยตรงผ่าน Official Notion API"
    )

    render_notion_config_expander(key_prefix="tracker_export_view")

    if st.button(
        f"🚀 ซิงค์ข้อมูลทั้งหมด ({len(df_thai)} รายการ) เข้าสู่ Notion ทันที",
        type="primary",
        use_container_width=True,
        key="bulk_sync_notion_btn",
    ):
        if not is_notion_configured():
            st.warning(
                "⚠️ ยังไม่ได้ตั้งค่า Notion Token หรือ Database ID โปรดเปิดกล่องตั้งค่าด้านบนเพื่อระบุข้อมูลก่อนครับ"
            )
        else:
            apps = get_all_applications()
            if not apps:
                st.warning("ไม่มีรายการงานที่จะส่งเข้า Notion")
            else:
                progress_bar = st.progress(0.0)
                status_placeholder = st.empty()
                success_count = 0
                error_list = []
                total = len(apps)

                for idx, app in enumerate(apps):
                    status_placeholder.write(
                        f"⏳ กำลังส่ง ({idx + 1}/{total}): **{app['role']}** ที่ **{app['company']}**..."
                    )
                    res = create_notion_job_page(
                        company=app["company"],
                        role=app["role"],
                        status=app["status"],
                        applied_date=app.get("applied_date") or "",
                        follow_up_date=app.get("follow_up_date") or "",
                        location=app.get("location") or "",
                        salary=app.get("salary") or "",
                        job_url=app.get("job_url") or "",
                        email_subject=app.get("email_subject") or "",
                        email_content=app.get("email_content") or "",
                        notes=app.get("notes") or "",
                        image_url=app.get("image_url") or "",
                    )
                    if res["success"]:
                        success_count += 1
                    else:
                        error_list.append(
                            f"{app['company']} - {app['role']}: {res['message']}"
                        )

                    progress_bar.progress((idx + 1) / total)

                status_placeholder.empty()
                if success_count > 0:
                    st.success(
                        f"🎉 ซิงค์ข้อมูลเข้าสู่ Notion Database สำเร็จเรียบร้อย **{success_count}/{total}** รายการ!"
                    )
                if error_list:
                    st.warning(f"⚠️ มีบางรายการไม่สำเร็จ ({len(error_list)} รายการ):")
                    for err in error_list[:5]:
                        st.caption(f"• {err}")

    st.markdown("---")

    # --- ส่วนที่ 2: ดาวน์โหลดไฟล์ ---
    st.markdown("### 💾 ตัวเลือกที่ 2: ดาวน์โหลดไฟล์ (Excel / CSV / Notion CSV)")
    st.caption(
        "เหมาะสำหรับนำไปเปิดแบบออฟไลน์ด้วย Excel, Google Sheets หรือใช้ฟังก์ชัน Import CSV"
    )
    col_excel, col_csv, col_notion = st.columns(3)

    # 1. Excel (.xlsx)
    with col_excel, st.container(border=True):
        st.markdown("#### 📊 Microsoft Excel (.xlsx)")
        st.caption("เหมาะสำหรับเปิดในโปรแกรม Excel โดยตรง มีการจัดหน้าตารางเรียบร้อย")
        try:
            excel_bytes = generate_excel_bytes(df_thai)
            st.download_button(
                label="📥 ดาวน์โหลดไฟล์ .xlsx",
                data=excel_bytes,
                file_name=f"career_agent_applications_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:  # noqa: BLE001 — show export error in UI
            st.error(f"เกิดข้อผิดพลาดในการสร้างไฟล์ Excel: {e}")

    # 2. CSV (UTF-8 with BOM for Excel)
    with col_csv, st.container(border=True):
        st.markdown("#### 📄 ไฟล์ CSV มาตรฐาน")
        st.caption("ฟอร์แมต UTF-8 with BOM ภาษาไทยไม่เพี้ยนใน Excel และ Google Sheets")
        csv_bytes = df_thai.to_csv(index=False, encoding="utf-8-sig").encode(
            "utf-8-sig"
        )
        st.download_button(
            label="📥 ดาวน์โหลดไฟล์ .csv",
            data=csv_bytes,
            file_name=f"career_agent_applications_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # 3. Notion-Ready CSV
    with col_notion, st.container(border=True):
        st.markdown("#### 📝 Notion-Ready CSV")
        st.caption("ออกแบบคอลัมน์ให้ตรงกับ Database Properties ของ Notion นำเข้าได้ใน 1 คลิก")
        notion_csv_bytes = df_notion.to_csv(index=False, encoding="utf-8-sig").encode(
            "utf-8-sig"
        )
        st.download_button(
            label="📥 ดาวน์โหลด Notion CSV",
            data=notion_csv_bytes,
            file_name=f"notion_job_tracker_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("---")

    # คำแนะนำการนำเข้า Notion
    st.subheader("💡 วิธีนำเข้าไฟล์เข้าสู่ Notion (3 ขั้นตอน)")
    st.markdown(
        """
        1. **ดาวน์โหลดไฟล์:** กดปุ่ม **"📥 ดาวน์โหลด Notion CSV"** ด้านบน
        2. **เปิด Notion:** เปิดแอป Notion หรือเข้าผ่านเว็บ -> กดสร้างหน้าใหม่ (`+ New Page`)
        3. **นำเข้าข้อมูล:**
           * พิมพ์ `/import` หรือคลิกที่ไอคอนจุดสามจุด `...` ที่มุมขวาบนของหน้า Notion
           * เลือกเมนู **Merge with CSV** (ถ้ามีตารางอยู่แล้ว) หรือเลือก **CSV** (ถ้าสร้างฐานข้อมูลใหม่)
           * เลือกไฟล์ CSV ที่เพิ่งดาวน์โหลดไป ระบบจะสร้างตารางที่มี Properties: `Company`, `Role`, `Status`, `Applied Date`, `Follow-up Date`, `Email Subject`, `Email Body` ให้ทันที!
        """
    )


def render():
    """
    จุดเริ่มต้นการแสดงผลของโมดูล Application Tracker
    """
    st.header("📋 ติดตามการสมัครงาน (Application Tracker)")
    st.caption(
        "บริหารจัดการท่อส่งการสมัครงาน (Pipeline) ครบทุกขั้นตอนบนฐานข้อมูล SQLite พร้อมประวัติอีเมลและระบบส่งออก"
    )

    # ตรวจสอบว่ากำลังแก้ไขงานเฉพาะรายการอยู่หรือไม่
    edit_id = st.session_state.get("edit_app_id")
    if edit_id:
        render_edit_view(edit_id)
        return

    # แท็บการทำงานหลัก
    tab_pipeline, tab_list, tab_add, tab_export = st.tabs(
        [
            "📊 กระดานไปป์ไลน์ (Kanban)",
            "📋 คลังรายการและค้นหา",
            "➕ เพิ่มข้อมูลการสมัครงาน",
            "📥 ส่งออกข้อมูล (Excel / Notion)",
        ]
    )

    with tab_pipeline:
        render_pipeline_view()

    with tab_list:
        render_list_view()

    with tab_add:
        render_add_application_form()

    with tab_export:
        render_export_view()
