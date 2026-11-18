"""
Career Agent - จุดเริ่มต้นหลักของแอปพลิเคชัน Streamlit
แดชบอร์ดศูนย์กลางสำหรับการจัดการและพัฒนาสายอาชีพอย่างชาญฉลาด
มาพร้อม UI ดีไซน์ทันสมัย เมนูนำทางแบบ Modern Pill Cards และ Quick Access Hub
"""
import streamlit as st
from config.settings import (
    get_openai_model,
    get_openai_base_url,
    is_openai_configured,
    reload_env,
)
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


def apply_custom_styles():
    """เพิ่ม CSS ตกแต่งเมนูหลักและการ์ดให้สวยงาม สไตล์ Modern SaaS"""
    st.markdown(
        """
        <style>
        /* ซ่อนวงกลม Radio Button และเปลี่ยนเป็น Modern Navigation Pill Card */
        div[role="radiogroup"] > label {
            display: flex;
            align-items: center;
            padding: 10px 14px !important;
            margin-bottom: 6px !important;
            border-radius: 10px !important;
            background: rgba(255, 255, 255, 0.02) !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
            cursor: pointer !important;
            font-size: 14px !important;
            font-weight: 500 !important;
        }

        /* เอฟเฟกต์เมื่อ Hover เมนู */
        div[role="radiogroup"] > label:hover {
            background: rgba(99, 102, 241, 0.12) !important;
            border-color: rgba(129, 140, 248, 0.4) !important;
            transform: translateX(5px);
        }

        /* สไตล์เมื่อเมนูถูกเลือก (Active State) */
        div[role="radiogroup"] > label:has(input:checked),
        div[role="radiogroup"] > label[data-checked="true"] {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(168, 85, 247, 0.25) 100%) !important;
            border-color: #818cf8 !important;
            color: #ffffff !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.2) !important;
        }

        /* ซ่อนวงกลม Radio ดั้งเดิม */
        div[role="radiogroup"] input[type="radio"] {
            display: none !important;
        }

        /* ตกแต่งการ์ดสถิติ (Metrics) */
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 16px;
            transition: all 0.2s ease;
        }
        div[data-testid="stMetric"]:hover {
            border-color: rgba(129, 140, 248, 0.5);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
            transform: translateY(-2px);
        }

        /* แบนเนอร์หัวเรื่อง */
        .hero-banner {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(168, 85, 247, 0.12) 50%, rgba(236, 72, 153, 0.1) 100%);
            border: 1px solid rgba(129, 140, 248, 0.25);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
        }

        /* การ์ด Quick Access Hub */
        .quick-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.07);
            border-radius: 14px;
            padding: 18px;
            height: 100%;
            transition: all 0.25s ease;
        }
        .quick-card:hover {
            border-color: rgba(129, 140, 248, 0.45);
            transform: translateY(-3px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.25);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
    # Hero Banner สวยงาม
    st.markdown(
        """
        <div class="hero-banner">
            <h1 style="margin: 0; font-size: 30px; font-weight: 800; background: linear-gradient(90deg, #818cf8, #c084fc, #f472b6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                💼 Career Agent — ศูนย์บัญชาการสายอาชีพอัจฉริยะ
            </h1>
            <p style="margin-top: 8px; margin-bottom: 0; font-size: 15px; color: #cbd5e1; line-height: 1.6;">
                ผู้ช่วยส่วนตัวขับเคลื่อนด้วย AI ที่จะดูแลการสมัครงานและพัฒนาสายอาชีพของคุณแบบครบวงจร 
                ตั้งแต่การปรับปรุงเรซูเม่ ค้นหางาน จับคู่ทักษะ ซ้อมสัมภาษณ์ ไปจนถึงการวางแผนก้าวสู่ตำแหน่งระดับสูง
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # การ์ดแสดงสถิติภาพรวม (Metric Cards)
    stats = get_quick_stats()
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="📌 งานที่กำลังติดตาม", value=f"{stats['applications']} ตำแหน่ง", help="บันทึกอยู่ใน Application Tracker")
    with col2:
        st.metric(label="📄 เรซูเม่ที่ผ่านการวิเคราะห์", value=f"{stats['resumes']} ฉบับ", help="บันทึกอยู่ใน Resume Analyzer")
    with col3:
        st.metric(label="🎙️ รอบจำลองการสัมภาษณ์", value=f"{stats['interviews']} ครั้ง", help="บันทึกอยู่ใน Interview Coach")
    with col4:
        st.metric(label="📈 เป้าหมายสายอาชีพ", value=f"{stats['goals']} เป้าหมาย", help="บันทึกอยู่ใน Career Planner")

    st.markdown("---")

    # ส่วน Quick Access Hub (การ์ดเข้าถึงเมนูด่วน)
    st.subheader("⚡ ศูนย์รวมเครื่องมืออัจฉริยะ (Quick Access Hub)")
    st.caption("คลิกเพื่อเข้าสู่แต่ละโมดูลได้ทันที")

    q_col1, q_col2, q_col3 = st.columns(3)

    with q_col1:
        with st.container(border=True):
            st.markdown("### 📄 วิเคราะห์เรซูเม่")
            st.write("ตรวจคะแนน ATS จากไฟล์ PDF วิเคราะห์จุดแข็ง-จุดอ่อน และรีไรท์ด้วยสูตร XYZ")
            if st.button("เข้าสู่ Resume Analyzer", key="hub_btn_resume", use_container_width=True):
                st.session_state["nav_selection"] = "📄 1. วิเคราะห์เรซูเม่"
                st.rerun()

    with q_col2:
        with st.container(border=True):
            st.markdown("### 🔍 ค้นหาตำแหน่งงาน")
            st.write("สร้าง Smart Search Links 7 เว็บดัง พร้อมขอสูตรค้นหา Boolean จาก AI")
            if st.button("เข้าสู่ Job Hunter", key="hub_btn_hunter", use_container_width=True):
                st.session_state["nav_selection"] = "🔍 2. ค้นหาตำแหน่งงาน"
                st.rerun()

    with q_col3:
        with st.container(border=True):
            st.markdown("### 🎯 จับคู่งานและทักษะ")
            st.write("คำนวณ % Match Score เทียบเรซูเม่อย่างละเอียดและแนะนำวิธีกลบจุดอ่อน")
            if st.button("เข้าสู่ Job Matching", key="hub_btn_matching", use_container_width=True):
                st.session_state["nav_selection"] = "🎯 3. จับคู่งานและทักษะ"
                st.rerun()

    q2_col1, q2_col2, q2_col3 = st.columns(3)

    with q2_col1:
        with st.container(border=True):
            st.markdown("### 🎙️ ซ้อมสัมภาษณ์งาน")
            st.write("จำลองคำถามสัมภาษณ์ระดับสากล และประเมินคำตอบตามเกณฑ์ STAR Method")
            if st.button("เข้าสู่ Interview Coach", key="hub_btn_coach", use_container_width=True):
                st.session_state["nav_selection"] = "🎙️ 4. ฝึกซ้อมสัมภาษณ์"
                st.rerun()

    with q2_col2:
        with st.container(border=True):
            st.markdown("### 📈 วางแผนเส้นทางอาชีพ")
            st.write("สร้าง Roadmap ก้าวสู่ตำแหน่งในฝัน พร้อมเช็คลิสต์หมุดหมายรายความสำเร็จ")
            if st.button("เข้าสู่ Career Planner", key="hub_btn_planner", use_container_width=True):
                st.session_state["nav_selection"] = "📈 5. วางแผนเส้นทางอาชีพ"
                st.rerun()

    with q2_col3:
        with st.container(border=True):
            st.markdown("### 📋 ติดตามการสมัครงาน")
            st.write("กระดานไปป์ไลน์ Kanban จัดการทุกสถานะการสมัครงานในที่เดียวบน SQLite")
            if st.button("เข้าสู่ Application Tracker", key="hub_btn_tracker", use_container_width=True):
                st.session_state["nav_selection"] = "📋 6. ติดตามการสมัครงาน"
                st.rerun()

    st.markdown("---")

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

        active_base_url = get_openai_base_url()
        active_model = get_openai_model()
        provider_label = f"Custom ({active_base_url})" if active_base_url else "OpenAI Official"

        if is_openai_configured():
            st.success(f"🟢 ผู้ให้บริการ AI: {provider_label}\n\nโมเดล: `{active_model}`")
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
    # ใช้งานสไตล์ตกแต่งหน้าตา
    apply_custom_styles()

    # โหลดค่าล่าสุดจาก .env ทุกครั้งที่เรนเดอร์หน้าจอ
    reload_env()
    current_model = get_openai_model()
    current_base_url = get_openai_base_url()

    # --- ส่วนหัวของ Sidebar Navigation ---
    st.sidebar.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(30, 27, 75, 0.7) 0%, rgba(49, 46, 129, 0.7) 100%); padding: 18px; border-radius: 14px; margin-bottom: 18px; border: 1px solid rgba(129, 140, 248, 0.25); text-align: center;">
            <div style="font-size: 32px; margin-bottom: 4px;">💼</div>
            <div style="font-size: 19px; font-weight: 800; letter-spacing: 0.5px; background: linear-gradient(90deg, #818cf8, #c084fc, #f472b6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                CAREER AGENT
            </div>
            <div style="font-size: 11px; color: #94a3b8; margin-top: 4px; font-weight: 500;">
                All-in-One AI Career Assistant
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    menu_options = [
        "🏠 ภาพรวมแดชบอร์ด",
        "📄 1. วิเคราะห์เรซูเม่",
        "🔍 2. ค้นหาตำแหน่งงาน",
        "🎯 3. จับคู่งานและทักษะ",
        "🎙️ 4. ฝึกซ้อมสัมภาษณ์",
        "📈 5. วางแผนเส้นทางอาชีพ",
        "📋 6. ติดตามการสมัครงาน",
    ]

    # ตรวจสอบว่ามีหน้าเพจที่เลือกผ่านปุ่ม Hub หรือไม่
    current_nav = st.session_state.get("nav_selection", menu_options[0])
    if current_nav not in menu_options:
        current_nav = menu_options[0]

    st.sidebar.markdown("<p style='font-size: 12px; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.8px;'>เมนูนำทางหลัก</p>", unsafe_allow_html=True)
    selected_page = st.sidebar.radio(
        "เมนูหลัก",
        menu_options,
        index=menu_options.index(current_nav),
        label_visibility="collapsed",
    )
    # อัปเดต session state ให้ตรงกัน
    st.session_state["nav_selection"] = selected_page

    # --- กล่องแสดงข้อมูลสภาพแวดล้อมที่ Sidebar ---
    st.sidebar.markdown("<p style='font-size: 12px; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin-top: 20px; margin-bottom: 8px; letter-spacing: 0.8px;'>ข้อมูลระบบ</p>", unsafe_allow_html=True)
    with st.sidebar.container(border=True):
        st.markdown(f"🤖 **โมเดล AI:** `{current_model}`")
        if current_base_url:
            st.caption(f"🌐 `{current_base_url}`")
        st.markdown(f"💾 **ฐานข้อมูล:** `{'พร้อมใช้งาน' if db_ready else 'ขัดข้อง'}`")
        st.markdown(f"🔑 **API Key:** `{'เชื่อมต่อแล้ว' if is_openai_configured() else 'ยังไม่ตั้งค่า'}`")

    # การนำทางไปยังแต่ละโมดูล
    try:
        if selected_page == "🏠 ภาพรวมแดชบอร์ด":
            render_dashboard_overview()
        elif selected_page == "📄 1. วิเคราะห์เรซูเม่":
            resume_analyzer.render()
        elif selected_page == "🔍 2. ค้นหาตำแหน่งงาน":
            job_hunter.render()
        elif selected_page == "🎯 3. จับคู่งานและทักษะ":
            job_matching.render()
        elif selected_page == "🎙️ 4. ฝึกซ้อมสัมภาษณ์":
            interview_coach.render()
        elif selected_page == "📈 5. วางแผนเส้นทางอาชีพ":
            career_planner.render()
        elif selected_page == "📋 6. ติดตามการสมัครงาน":
            application_tracker.render()
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการโหลดหน้า '{selected_page}': {e}", exc_info=True)
        st.error(f"เกิดข้อผิดพลาดขณะโหลดหน้านี้: {e}")


if __name__ == "__main__":
    main()
