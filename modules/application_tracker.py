"""
โมดูลที่ 6: ระบบติดตามการสมัครงาน (Application Tracker)
ระบบจัดการสถานะการสมัครงานแบบ CRUD บนฐานข้อมูล SQLite
รองรับการติดตามแบบไปป์ไลน์ (Kanban), ค้นหาตำแหน่งงาน และจัดการข้อมูลแบบภาษาไทยเต็มรูปแบบ
"""
from datetime import date
from typing import Dict, List, Optional
import streamlit as st
from database.db import get_db_connection
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
) -> int:
    """เพิ่มข้อมูลการสมัครงานใหม่ลงในฐานข้อมูล SQLite"""
    if status not in VALID_STATUSES:
        status = "Wishlist"

    query = """
    INSERT INTO applications (company, role, location, salary, job_url, status, applied_date, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
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
                ),
            )
            new_id = cursor.lastrowid
            logger.info(f"เพิ่มงานใหม่สำเร็จ ID {new_id}: {company} - {role}")
            return new_id
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเพิ่มงาน: {e}", exc_info=True)
        raise


def get_all_applications(status_filter: Optional[str] = None, search_term: Optional[str] = None) -> List[Dict]:
    """ค้นหาและดึงข้อมูลการสมัครงานทั้งหมดตามตัวกรองและคำค้นหา"""
    query = "SELECT * FROM applications WHERE 1=1"
    params: list = []

    if status_filter and status_filter in VALID_STATUSES:
        query += " AND status = ?"
        params.append(status_filter)

    if search_term and search_term.strip():
        term = f"%{search_term.strip()}%"
        query += " AND (company LIKE ? OR role LIKE ? OR location LIKE ? OR notes LIKE ?)"
        params.extend([term, term, term, term])

    query += " ORDER BY updated_at DESC, id DESC;"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลการสมัครงาน: {e}", exc_info=True)
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
) -> bool:
    """อัปเดตข้อมูลรายละเอียดการสมัครงาน"""
    if status not in VALID_STATUSES:
        status = "Wishlist"

    query = """
    UPDATE applications
    SET company = ?, role = ?, location = ?, salary = ?, job_url = ?, status = ?, applied_date = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
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
                    app_id,
                ),
            )
            logger.info(f"อัปเดตข้อมูลงาน ID {app_id} สำเร็จ")
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการอัปเดตงาน ID {app_id}: {e}", exc_info=True)
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
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเปลี่ยนสถานะงาน ID {app_id}: {e}", exc_info=True)
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
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการลบงาน ID {app_id}: {e}", exc_info=True)
        raise


def get_status_counts() -> Dict[str, int]:
    """คำนวณจำนวนงานในแต่ละสถานะ"""
    counts = {s: 0 for s in VALID_STATUSES}
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) as cnt FROM applications GROUP BY status;")
            for row in cursor.fetchall():
                if row["status"] in counts:
                    counts[row["status"]] = row["cnt"]
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการคำนวณสถิติสถานะ: {e}")
    return counts


# ==========================================
# หน้าจอแสดงผล (Streamlit UI Views)
# ==========================================

def render_add_application_form():
    """ฟอร์มสำหรับเพิ่มข้อมูลการสมัครงานใหม่"""
    st.subheader("➕ บันทึกข้อมูลการสมัครงานใหม่")
    st.write("บันทึกตำแหน่งงาน บริษัท และขั้นตอนที่คุณกำลังดำเนินการเพื่อไม่ให้พลาดทุกโอกาส")

    with st.form("add_application_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input("ชื่อบริษัท / องค์กร *", placeholder="เช่น Google, SCB TechX, Agoda")
            role = st.text_input("ตำแหน่งงานที่สมัคร *", placeholder="เช่น Senior Python Engineer, Data Analyst")
            location = st.text_input("สถานที่ทำงาน", placeholder="เช่น กรุงเทพฯ / Hybrid / Remote 100%")
        with col2:
            status_index = 0
            status_selected = st.selectbox(
                "สถานะปัจจุบัน",
                VALID_STATUSES,
                format_func=lambda s: STATUS_LABELS.get(s, s),
                index=status_index,
            )
            salary = st.text_input("ฐานเงินเดือน / ผลตอบแทน", placeholder="เช่น 80,000 - 120,000 บาท/เดือน")
            applied_date = st.date_input("วันที่สมัคร", value=date.today())

        job_url = st.text_input("ลิงก์ประกาศรับสมัครงาน (URL)", placeholder="https://linkedin.com/jobs/view/...")
        notes = st.text_area("บันทึกเพิ่มเติม / ข้อมูลผู้ติดต่อ", placeholder="ชื่อผู้ติดต่อ HR, ข้อมูลรอบสัมภาษณ์, ข้อมูลผู้แนะนำ (Referral)...")

        submitted = st.form_submit_button("💾 บันทึกข้อมูลการสมัครงาน", use_container_width=True)

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
                    )
                    st.success(f"บันทึกตำแหน่ง **{role}** ที่ **{company}** เรียบร้อยแล้ว!")
                    st.rerun()
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดในการบันทึก: {e}")


def render_pipeline_view():
    """มุมมองกระดาน Kanban ติดตามสถานะงาน"""
    st.subheader("📊 กระดานติดตามสถานะการสมัครงาน (Kanban Pipeline)")
    counts = get_status_counts()

    # แสดงตัวเลขสถิติสรุป
    cols = st.columns(len(VALID_STATUSES))
    for i, st_name in enumerate(VALID_STATUSES):
        with cols[i]:
            st.metric(label=STATUS_LABELS[st_name], value=f"{counts[st_name]} งาน")

    st.divider()

    # เสาคอลัมน์ Kanban
    kanban_cols = st.columns(len(VALID_STATUSES))
    for idx, st_name in enumerate(VALID_STATUSES):
        with kanban_cols[idx]:
            st.markdown(f"#### {STATUS_LABELS[st_name]}")
            apps_in_stage = get_all_applications(status_filter=st_name)

            if not apps_in_stage:
                st.caption("ยังไม่มีรายการในขั้นตอนนี้")
            else:
                for app in apps_in_stage:
                    with st.container(border=True):
                        st.markdown(f"**{app['company']}**")
                        st.write(f"💼 {app['role']}")
                        if app["location"]:
                            st.caption(f"📍 {app['location']}")
                        if app["salary"]:
                            st.caption(f"💰 {app['salary']}")
                        if app["applied_date"]:
                            st.caption(f"📅 {format_date(app['applied_date'])}")

                        # เลือดย้ายสถานะอย่างรวดเร็ว
                        current_idx = VALID_STATUSES.index(app["status"])
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


def render_list_view():
    """มุมมองตารางรายการ ค้นหา และแก้ไข/ลบ"""
    st.subheader("📋 คลังรายการสมัครงานทั้งหมด")

    col_search, col_filter = st.columns([3, 1])
    with col_search:
        search_query = st.text_input("🔍 ค้นหาตามชื่อบริษัท, ตำแหน่ง, หรือคีย์เวิร์ด", placeholder="พิมพ์เพื่อค้นหา...")
    with col_filter:
        filter_options = ["ทั้งหมด"] + VALID_STATUSES
        filter_status = st.selectbox(
            "กรองตามสถานะ",
            filter_options,
            format_func=lambda s: "ทั้งหมด" if s == "ทั้งหมด" else STATUS_LABELS.get(s, s),
        )

    selected_status = None if filter_status == "ทั้งหมด" else filter_status
    applications = get_all_applications(status_filter=selected_status, search_term=search_query)

    st.write(f"พบรายการทั้งหมด **{len(applications)}** รายการ")

    if not applications:
        st.info("ไม่พบรายการสมัครงานที่ตรงกับเงื่อนไข สามารถเพิ่มได้ที่แท็บ 'เพิ่มงานใหม่'")
        return

    for app in applications:
        badge = STATUS_LABELS.get(app["status"], app["status"])
        with st.expander(f"{badge} — **{app['company']}** : {app['role']}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**บริษัท:** {app['company']}")
                st.write(f"**ตำแหน่ง:** {app['role']}")
                st.write(f"**สถานที่:** {app['location'] or 'ไม่ระบุ'}")
                st.write(f"**เงินเดือน:** {app['salary'] or 'ไม่ระบุ'}")
            with col2:
                st.write(f"**สถานะ:** {STATUS_LABELS.get(app['status'], app['status'])}")
                st.write(f"**วันที่สมัคร:** {format_date(app['applied_date'])}")
                if app["job_url"]:
                    st.markdown(f"**ลิงก์งาน:** [เปิดดูประกาศรับสมัคร]({app['job_url']})")
                st.write(f"**บันทึกเมื่อ:** {app['created_at']}")

            if app["notes"]:
                st.info(f"**บันทึกเพิ่มเติม:**\n\n{app['notes']}")

            # ปุ่มแก้ไขและลบ
            bcol1, bcol2, _ = st.columns([1, 1, 4])
            with bcol1:
                if st.button("✏️ แก้ไข", key=f"edit_btn_{app['id']}"):
                    st.session_state["edit_app_id"] = app["id"]
                    st.rerun()
            with bcol2:
                if st.button("🗑️ ลบ", key=f"del_btn_{app['id']}", type="secondary"):
                    delete_application(app["id"])
                    st.success(f"ลบรายการของบริษัท {app['company']} เรียบร้อยแล้ว")
                    st.rerun()


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
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")
        return

    with st.form(f"edit_form_{app_id}"):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input("ชื่อบริษัท / องค์กร *", value=app["company"])
            role = st.text_input("ตำแหน่งงานที่สมัคร *", value=app["role"])
            location = st.text_input("สถานที่ทำงาน", value=app["location"] or "")
        with col2:
            status_index = VALID_STATUSES.index(app["status"]) if app["status"] in VALID_STATUSES else 0
            status = st.selectbox(
                "สถานะปัจจุบัน",
                VALID_STATUSES,
                format_func=lambda s: STATUS_LABELS.get(s, s),
                index=status_index,
            )
            salary = st.text_input("ฐานเงินเดือน / ผลตอบแทน", value=app["salary"] or "")
            applied_date = st.text_input("วันที่สมัคร (YYYY-MM-DD)", value=app["applied_date"] or get_current_date_str())

        job_url = st.text_input("ลิงก์ประกาศรับสมัครงาน (URL)", value=app["job_url"] or "")
        notes = st.text_area("บันทึกเพิ่มเติม", value=app["notes"] or "")

        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            save_clicked = st.form_submit_button("💾 บันทึกการแก้ไข", use_container_width=True)
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
                )
                st.session_state.pop("edit_app_id", None)
                st.success("อัปเดตข้อมูลเรียบร้อยแล้ว!")
                st.rerun()

        if cancel_clicked:
            st.session_state.pop("edit_app_id", None)
            st.rerun()


def render():
    """
    จุดเริ่มต้นการแสดงผลของโมดูล Application Tracker
    """
    st.header("📋 ติดตามการสมัครงาน (Application Tracker)")
    st.caption("บริหารจัดการท่อส่งการสมัครงาน (Pipeline) ครบทุกขั้นตอนบนฐานข้อมูล SQLite")

    # ตรวจสอบว่ากำลังแก้ไขงานเฉพาะรายการอยู่หรือไม่
    edit_id = st.session_state.get("edit_app_id")
    if edit_id:
        render_edit_view(edit_id)
        return

    # แท็บการทำงานหลัก
    tab_pipeline, tab_list, tab_add = st.tabs([
        "📊 กระดานไปป์ไลน์ (Kanban)",
        "📋 คลังรายการและค้นหา",
        "➕ เพิ่มข้อมูลการสมัครงาน",
    ])

    with tab_pipeline:
        render_pipeline_view()

    with tab_list:
        render_list_view()

    with tab_add:
        render_add_application_form()
