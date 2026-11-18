"""
Career Agent - จุดเริ่มต้นหลักของแอปพลิเคชัน Streamlit
แดชบอร์ดศูนย์กลางสำหรับการจัดการและพัฒนาสายอาชีพอย่างชาญฉลาด
"""
import streamlit as st
from config.settings import OPENAI_MODEL, OPENAI_BASE_URL, is_openai_configured
from database.db import init_db, check_db_health, get_db_connection
from services.ai_service import ai_service
from utils.logger import setup_logger

# นำเข้าโมดูลหลักทั้ง 6 โมดูล
from modules import (
    resume_analyzer,
    job_hunter,
    job_matching,
    interview_coach,
    career_planner,
    application_tracker,
)

logger = setup_logger("app")

# 1. ตั้งค่าหน้าเพจ Streamlit
st.set_page_config(
    page_title="Career Agent | ผู้ช่วยอัจฉริยะด้านการหางานและสายอาชีพ",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. เริ่มต้นฐานข้อมูล SQLite
@st.cache_resource
def initialize_database():
    """ตรวจสอบและสร้างตารางฐานข้อมูลเมื่อเริ่มเปิดแอปพลิเคชัน"""
    try:
        init_db()
        return True
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเริ่มต้นฐานข้อมูล: {e}")
        return False

db_ready = initialize_database()


def get_quick_stats():
    """ดึงข้อมูลสถิติภาพรวมจากฐานข้อมูล"""
    stats = {
        "applications": 0,
        "resumes": 0,
        "interviews": 0,
        "goals": 0,
    }
    if not db_ready:
        return stats

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM applications;")
            stats["applications"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM resumes;")
            stats["resumes"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM interview_sessions;")
            stats["interviews"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM career_goals;")
            stats["goals"] = cursor.fetchone()[0]
    except Exception as e:
        logger.warning(f"ไม่สามารถโหลดสถิติภาพรวมได้: {e}")

    return stats


def render_dashboard_overview():
    """แสดงผลหน้าแรก (ภาพรวมแดชบอร์ด)"""
    st.title("💼 Career Agent — ศูนย์บัญชาการสายอาชีพอัจฉริยะ")
    st.markdown(
        "ยินดีต้อนรับสู่ **Career Agent** ผู้ช่วยส่วนตัวที่จะช่วยคุณบริหารจัดการการหางานแบบครบวงจร "
        "ตั้งแต่การปรับแต่งเรซูเม่ ค้นหาตำแหน่งงาน วิเคราะห์ความเข้ากันได้ ซ้อมสัมภาษณ์ ไปจนถึงการติดตามสถานะการสมัครงาน"
    )
    st.divider()

    # การ์ดแสดงสถิติภาพรวม (Metric Cards)
    stats = get_quick_stats()
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="📌 งานที่ติดตามอยู่", value=f"{stats['applications']} งาน")
    with col2:
        st.metric(label="📄 เรซูเม่ที่วิเคราะห์แล้ว", value=f"{stats['resumes']} ฉบับ")
    with col3:
        st.metric(label="🎙️ รอบซ้อมสัมภาษณ์", value=f"{stats['interviews']} ครั้ง")
    with col4:
        st.metric(label="📈 เป้าหมายสายอาชีพ", value=f"{stats['goals']} เป้าหมาย")

    st.divider()

    # แผนการพัฒนาและสถานะของระบบ
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("🚀 แผนการพัฒนาระบบ (Implementation Roadmap)")
        st.markdown(
            """
            | เฟส (Phase) | โมดูลการทำงาน | สถานะ |
            | :--- | :--- | :--- |
            | **Phase 1** | **โครงสร้างโปรเจกต์และการตั้งค่าระบบ (Setup & Architecture)** | 🟢 **เสร็จสมบูรณ์** |
            | **Phase 2** | **ระบบติดตามการสมัครงาน (Application Tracker - CRUD & SQLite)** | 🟢 **เสร็จสมบูรณ์** |
            | **Phase 3** | **ระบบวิเคราะห์เรซูเม่ด้วย AI & รองรับ PDF (Resume Analyzer & ATS)** | 🟢 **เสร็จสมบูรณ์** |
            | **Phase 4** | **ระบบค้นหาตำแหน่งงานอัจฉริยะ (Job Hunter & Query Builder)** | 🟢 **เสร็จสมบูรณ์** |
            | **Phase 5** | **ระบบจับคู่งานและทักษะ (Job Matching & Fit Score)** | 🟢 **เสร็จสมบูรณ์** |
            | **Phase 6** | **โค้ชจำลองการสัมภาษณ์งาน (Interview Coach & STAR Feedback)** | 🟢 **เสร็จสมบูรณ์** |
            | **Phase 7** | **แผนที่เส้นทางสายอาชีพ (Career Planner & Roadmaps)** | 🟢 **เสร็จสมบูรณ์** |
            """
        )

    with col_right:
        st.subheader("⚙️ สถานะระบบ (System Status)")
        if db_ready and check_db_health():
            st.success("🟢 ฐานข้อมูล SQLite: เชื่อมต่อและทำงานปกติ")
        else:
            st.error("🔴 ฐานข้อมูล SQLite: พบปัญหาการเชื่อมต่อ")

        provider_label = f"Custom ({OPENAI_BASE_URL})" if OPENAI_BASE_URL else "OpenAI Official"
        if is_openai_configured():
            st.success(f"🟢 ผู้ให้บริการ AI: {provider_label}\n\nโมเดล: `{OPENAI_MODEL}`")
        else:
            st.warning("🟡 AI Provider: ยังไม่ได้ระบุคีย์ (โปรดเพิ่มในไฟล์ `.env`)")

        with st.expander("ทดสอบการเชื่อมต่อกับ AI Provider"):
            st.caption(f"ทดสอบยิงคำสั่ง Ping ไปยัง {provider_label}")
            if st.button("ทดสอบ Ping API", use_container_width=True):
                with st.spinner("กำลังตรวจสอบการเชื่อมต่อกับ AI..."):
                    result = ai_service.test_connection()
                    if result["success"]:
                        st.success(result["message"])
                    else:
                        st.error(result["message"])


def main():
    # แถบเมนูด้านข้าง (Sidebar Navigation)
    st.sidebar.title("💼 Career Agent")
    st.sidebar.caption("v0.3.0 • ภาษาไทยเต็มรูปแบบ")

    menu_options = [
        "ภาพรวมแดชบอร์ด",
        "1. วิเคราะห์เรซูเม่ (Resume Analyzer)",
        "2. ค้นหาตำแหน่งงาน (Job Hunter)",
        "3. จับคู่งานและทักษะ (Job Matching)",
        "4. ฝึกซ้อมสัมภาษณ์ (Interview Coach)",
        "5. วางแผนเส้นทางอาชีพ (Career Planner)",
        "6. ติดตามการสมัครงาน (Application Tracker)",
    ]

    selected_page = st.sidebar.radio("เมนูหลัก", menu_options, index=0)

    st.sidebar.divider()
    st.sidebar.subheader("ข้อมูลสภาพแวดล้อม")
    st.sidebar.write(f"**โมเดล AI:** `{OPENAI_MODEL}`")
    if OPENAI_BASE_URL:
        st.sidebar.caption(f"Endpoint: `{OPENAI_BASE_URL}`")
    st.sidebar.write(f"**ฐานข้อมูล:** `{'พร้อมใช้งาน' if db_ready else 'ขัดข้อง'}`")
    st.sidebar.write(f"**API Key:** `{'เชื่อมต่อแล้ว' if is_openai_configured() else 'ยังไม่ตั้งค่า'}`")

    # การนำทางไปยังแต่ละโมดูล
    try:
        if selected_page == "ภาพรวมแดชบอร์ด":
            render_dashboard_overview()
        elif selected_page == "1. วิเคราะห์เรซูเม่ (Resume Analyzer)":
            resume_analyzer.render()
        elif selected_page == "2. ค้นหาตำแหน่งงาน (Job Hunter)":
            job_hunter.render()
        elif selected_page == "3. จับคู่งานและทักษะ (Job Matching)":
            job_matching.render()
        elif selected_page == "4. ฝึกซ้อมสัมภาษณ์ (Interview Coach)":
            interview_coach.render()
        elif selected_page == "5. วางแผนเส้นทางอาชีพ (Career Planner)":
            career_planner.render()
        elif selected_page == "6. ติดตามการสมัครงาน (Application Tracker)":
            application_tracker.render()
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการโหลดหน้า '{selected_page}': {e}", exc_info=True)
        st.error(f"เกิดข้อผิดพลาดขณะโหลดหน้านี้: {e}")


if __name__ == "__main__":
    main()
