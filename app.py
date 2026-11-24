"""
Career Agent - จุดเริ่มต้นหลักของแอปพลิเคชัน Streamlit
แดชบอร์ดศูนย์กลางสำหรับการจัดการและพัฒนาสายอาชีพอย่างชาญฉลาด
มาพร้อม UI ดีไซน์ทันสมัย สไตล์ Modern SaaS Studio-Grade
"""

import html
import os

import streamlit as st

from config.settings import (
    get_openai_base_url,
    get_openai_model,
    is_notion_configured,
    is_openai_configured,
    reload_env,
)
from database.db import check_db_health, get_db_connection, init_db

# นำเข้าโมดูลหลักทั้ง 7 โมดูล
from modules import (
    application_tracker,
    career_planner,
    email_writer,
    interview_coach,
    job_hunter,
    job_matching,
    resume_analyzer,
)
from services.ai_service import ai_service
from utils.logger import setup_logger

logger = setup_logger("app")

# 1. ตั้งค่าหน้าเพจ Streamlit
st.set_page_config(
    page_title="Career Agent | ศูนย์บัญชาการสายอาชีพอัจฉริยะ AI",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)


# 2. เริ่มต้นฐานข้อมูล SQLite
def initialize_database():
    """ตรวจสอบและสร้างตารางฐานข้อมูลเมื่อเริ่มเปิดแอปพลิเคชัน"""
    if st.session_state.get("db_ready"):
        return True
    try:
        init_db()
        st.session_state["db_ready"] = True
        return True
    except Exception as e:  # noqa: BLE001 — prevent startup crash on DB failure
        logger.error(f"เกิดข้อผิดพลาดในการเริ่มต้นฐานข้อมูล: {e}")
        return False


db_ready = initialize_database()


@st.cache_data
def _load_css_files(theme: str) -> str:
    """อ่านและแคชไฟล์ CSS เพื่อลดการอ่านดิสก์ซ้ำทุก rerun"""
    css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
    light_css_path = os.path.join(
        os.path.dirname(__file__), "assets", "light_theme.css"
    )

    css_combined = ""
    if os.path.exists(css_path):
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                css_combined += f.read() + "\n"
        except OSError as e:
            logger.warning(f"ไม่สามารถโหลดไฟล์ style.css ได้: {e}")

    if theme == "light" and os.path.exists(light_css_path):
        try:
            with open(light_css_path, "r", encoding="utf-8") as f:
                css_combined += f.read() + "\n"
        except OSError as e:
            logger.warning(f"ไม่สามารถโหลดไฟล์ light_theme.css ได้: {e}")

    return css_combined


def apply_custom_styles(theme: str = "dark"):
    """โหลดไฟล์ CSS สำหรับตกแต่ง UI ให้สวยงามระดับ Modern SaaS รองรับ Dark Mode และ Light Mode"""
    css_combined = _load_css_files(theme)
    if css_combined:
        st.markdown(f"<style>{css_combined}</style>", unsafe_allow_html=True)

    # Fallback CSS หากไม่พบไฟล์
    fallback_bg = "#F8FAFC" if theme == "light" else "#090D16"
    fallback_color = "#0F172A" if theme == "light" else "#F1F5F9"
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Google+Sans:ital,wght@0,400..700;1,400..700&family=Prompt:wght@400;500;600;700&display=swap');
        @import url('https://cdn.jsdelivr.net/gh/mortezaom/google-sans-cdn@master/fonts.css');
        html, body {{
            font-family: 'Google Sans', 'Prompt', sans-serif;
            font-size: 18px !important;
        }}
        .stMarkdown, p, h1, h2, h3, h4, h5, h6, label, input, textarea {{
            font-family: 'Google Sans', 'Prompt', sans-serif !important;
            font-size: 18px !important;
        }}
        [data-testid*="Icon"], [data-testid*="icon"], .material-symbols-rounded, span[translate="no"] {{
            font-family: "Material Symbols Rounded" !important;
        }}
        .stApp {{
            background-color: {fallback_bg} !important;
            color: {fallback_color} !important;
        }}
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
    except Exception as e:  # noqa: BLE001 — non-critical dashboard stats
        logger.warning(f"ไม่สามารถโหลดสถิติภาพรวมได้: {e}")

    return stats


def render_metric_card(
    icon: str,
    label: str,
    value: str,
    subtext: str,
    gradient: str,
    is_light: bool = False,
):
    """สร้างการ์ดสถิติแบบกระจกโปร่งแสง (Glassmorphic Metric Card) สไตล์สตาร์ทอัปยุคใหม่ ปรับสีตามธีม"""
    if is_light:
        bg_card = "#FFFFFF"
        border_card = "1px solid #E2E8F0"
        shadow_card = "0 2px 12px rgba(0, 0, 0, 0.04)"
        label_color = "#475569"
        val_color = "#0F172A"
        sub_color = "#475569"
    else:
        bg_card = "linear-gradient(145deg, rgba(23, 31, 51, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%)"
        border_card = "1px solid rgba(255, 255, 255, 0.08)"
        shadow_card = "0 4px 22px rgba(0, 0, 0, 0.28)"
        label_color = "#94A3B8"
        val_color = "#FFFFFF"
        sub_color = "#94A3B8"

    return f"""
    <div style="
        background: {bg_card};
        border: {border_card};
        border-radius: 16px;
        padding: 18px 20px;
        box-shadow: {shadow_card};
        backdrop-filter: blur(12px);
        display: flex;
        align-items: center;
        gap: 16px;
        transition: all 0.25s ease;
        margin-bottom: 8px;
    ">
        <div style="
            width: 50px;
            height: 50px;
            border-radius: 14px;
            background: {gradient};
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2);
            flex-shrink: 0;
        ">{icon}</div>
        <div style="overflow: hidden;">
            <div style="font-size: 11px; font-weight: 700; color: {label_color}; text-transform: uppercase; letter-spacing: 0.5px;">{label}</div>
            <div style="font-size: 24px; font-weight: 800; color: {val_color}; letter-spacing: -0.5px; margin-top: 2px;">{value}</div>
            <div style="font-size: 11px; color: {sub_color}; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{subtext}</div>
        </div>
    </div>
    """


def render_dashboard_overview():
    """แสดงผลหน้าแรก (ภาพรวมแดชบอร์ด) สไตล์ Modern SaaS Studio-Grade"""
    is_light = st.session_state.get("app_theme", "dark") == "light"
    head_color = "#0F172A" if is_light else "#F1F5F9"
    sub_color = "#64748B" if is_light else "#94A3B8"
    card_head_color = "#0F172A" if is_light else "#FFFFFF"
    status_bg_green = (
        "rgba(16, 185, 129, 0.08)" if is_light else "rgba(16, 185, 129, 0.1)"
    )
    status_border_green = (
        "1px solid rgba(16, 185, 129, 0.3)"
        if is_light
        else "1px solid rgba(52, 211, 153, 0.3)"
    )
    status_text_green = "#047857" if is_light else "#34D399"
    status_bg_indigo = (
        "rgba(99, 102, 241, 0.08)" if is_light else "rgba(99, 102, 241, 0.1)"
    )
    status_border_indigo = (
        "1px solid rgba(99, 102, 241, 0.3)"
        if is_light
        else "1px solid rgba(129, 140, 248, 0.3)"
    )
    status_text_indigo = "#4338CA" if is_light else "#818CF8"
    text_primary = "#1E293B" if is_light else "#E2E8F0"

    # 1. Hero Banner สวยงามระดับสตูดิโอ
    st.markdown(
        """
        <div class="hero-banner">
            <div class="hero-pill-badge">
                <span>✨</span>
                <span>AI-POWERED CAREER OPERATING SYSTEM</span>
            </div>
            <h1 class="hero-title">
                💼 Career Agent — ศูนย์บัญชาการสายอาชีพอัจฉริยะ
            </h1>
            <p class="hero-subtitle">
                ระบบจัดการและเร่งการเติบโตทางสายอาชีพแบบครบวงจร ขับเคลื่อนด้วย Generative AI อัจฉริยะ 
                ตั้งแต่การถอดรหัสเรซูเม่เกณฑ์ ATS, ค้นหางาน 7 เว็บดัง, จำลองคำถามสัมภาษณ์ตามเกณฑ์ STAR, ไปจนถึงการจัดท่อส่งงานสไตล์ Kanban
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. การ์ดแสดงสถิติภาพรวม (Custom Metric Cards)
    stats = get_quick_stats()
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            render_metric_card(
                icon="📌",
                label="งานที่กำลังติดตาม",
                value=f"{stats['applications']} ตำแหน่ง",
                subtext="Application Tracker Pipeline",
                gradient="linear-gradient(135deg, #4F46E5 0%, #3B82F6 100%)",
                is_light=is_light,
            ),
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            render_metric_card(
                icon="📄",
                label="เรซูเม่ในระบบ",
                value=f"{stats['resumes']} ฉบับ",
                subtext="Resume Analyzer & ATS",
                gradient="linear-gradient(135deg, #7C3AED 0%, #A855F7 100%)",
                is_light=is_light,
            ),
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            render_metric_card(
                icon="🎙️",
                label="ซ้อมสัมภาษณ์แล้ว",
                value=f"{stats['interviews']} ครั้ง",
                subtext="Interview Coach Sessions",
                gradient="linear-gradient(135deg, #D97706 0%, #F59E0B 100%)",
                is_light=is_light,
            ),
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            render_metric_card(
                icon="📈",
                label="เป้าหมายอาชีพ",
                value=f"{stats['goals']} หมุดหมาย",
                subtext="Career Roadmap Milestones",
                gradient="linear-gradient(135deg, #059669 0%, #10B981 100%)",
                is_light=is_light,
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

    # 3. ส่วน Quick Access Hub (การ์ดเข้าถึงเมนูด่วน)
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
            <div>
                <h3 style="margin: 0; font-size: 20px; font-weight: 700; color: {head_color};">⚡ ศูนย์รวมเครื่องมืออัจฉริยะ (Quick Access Hub)</h3>
                <p style="margin: 4px 0 0 0; font-size: 13px; color: {sub_color};">เลือกเครื่องมือที่ต้องการ เพื่อเริ่มพัฒนาโอกาสการทำงานทันที</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    q_col1, q_col2, q_col3 = st.columns(3)

    with q_col1, st.container(border=True):
        st.markdown("#### 📄 วิเคราะห์ & รีไรท์เรซูเม่")
        st.caption("ตรวจคะแนน ATS จาก PDF วิเคราะห์จุดอ่อน และรีไรท์สูตร XYZ")
        if st.button(
            "เข้าสู่ Resume Analyzer →",
            key="hub_btn_resume",
            use_container_width=True,
            type="primary",
        ):
            st.session_state["nav_selection"] = "📄 วิเคราะห์เรซูเม่"
            st.rerun()

    with q_col2, st.container(border=True):
        st.markdown("#### 🔍 ค้นหาตำแหน่งงาน")
        st.caption("สร้าง Smart Search Links 7 เว็บดัง พร้อมสูตรค้นหา Boolean")
        if st.button(
            "เข้าสู่ Job Hunter →", key="hub_btn_hunter", use_container_width=True
        ):
            st.session_state["nav_selection"] = "🔍 ค้นหาตำแหน่งงาน"
            st.rerun()

    with q_col3, st.container(border=True):
        st.markdown("#### 🎯 จับคู่งานและทักษะ")
        st.caption("คำนวณ % Match Score เทียบเรซูเม่และหาจุดอ่อนก่อนสัมภาษณ์")
        if st.button(
            "เข้าสู่ Job Matching →", key="hub_btn_matching", use_container_width=True
        ):
            st.session_state["nav_selection"] = "🎯 จับคู่งานและทักษะ"
            st.rerun()

    q2_col1, q2_col2, q2_col3, q2_col4 = st.columns(4)

    with q2_col1, st.container(border=True):
        st.markdown("#### 🎙️ ซ้อมสัมภาษณ์งาน")
        st.caption("จำลองคำถามจริงและประเมินตามเกณฑ์ STAR")
        if st.button("เข้าสู่ Coach →", key="hub_btn_coach", use_container_width=True):
            st.session_state["nav_selection"] = "🎙️ ฝึกซ้อมสัมภาษณ์"
            st.rerun()

    with q2_col2, st.container(border=True):
        st.markdown("#### 📈 วางแผนเส้นทางอาชีพ")
        st.caption("สร้าง Roadmap พร้อมเช็คลิสต์หมุดหมาย")
        if st.button("เข้าสู่ Planner →", key="hub_btn_planner", use_container_width=True):
            st.session_state["nav_selection"] = "📈 วางแผนเส้นทางอาชีพ"
            st.rerun()

    with q2_col3, st.container(border=True):
        st.markdown("#### ✉️ ร่างอีเมลสมัครงาน")
        st.caption("ร่าง Email/Cover Letter พร้อมสแกนโปสเตอร์ OCR")
        if st.button(
            "เข้าสู่ Email Writer →", key="hub_btn_email", use_container_width=True
        ):
            st.session_state["nav_selection"] = "✉️ ร่างอีเมลสมัครงาน"
            st.rerun()

    with q2_col4, st.container(border=True):
        st.markdown("#### 📋 ติดตามการสมัครงาน")
        st.caption("กระดาน Kanban พร้อมส่งออก Excel & Notion")
        if st.button("เข้าสู่ Tracker →", key="hub_btn_tracker", use_container_width=True):
            st.session_state["nav_selection"] = "📋 ติดตามการสมัครงาน"
            st.rerun()

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    # 4. แผนการพัฒนาและสถานะของระบบ
    col_left, col_right = st.columns([3, 2])

    with col_left, st.container(border=True):
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                <div style="font-size: 17px; font-weight: 700; color: {card_head_color};">🚀 สถาปัตยกรรมระบบ (System Architecture)</div>
                <span class="card-badge badge-emerald">ALL PHASES OPERATIONAL</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            | เฟส (Phase) | โมดูลการทำงาน | การทำงานหลัก | สถานะ |
            | :--- | :--- | :--- | :--- |
            | **Phase 1** | **Core Architecture** | โครงสร้างโปรเจกต์ & SQLite Connection | 🟢 พร้อมใช้งาน |
            | **Phase 2** | **Application Tracker** | ไปป์ไลน์ Kanban, CRUD & ตัวกรองงาน | 🟢 พร้อมใช้งาน |
            | **Phase 3** | **Resume Analyzer** | ตรวจเกณฑ์ ATS & รีไรท์สูตร Google XYZ | 🟢 พร้อมใช้งาน |
            | **Phase 4** | **Job Hunter** | Smart Search 7 เว็บ & Boolean Generator | 🟢 พร้อมใช้งาน |
            | **Phase 5** | **Job Matching** | คำนวณ % Fit Score & วิเคราะห์ทักษะที่ขาด | 🟢 พร้อมใช้งาน |
            | **Phase 6** | **Interview Coach** | ซ้อมสัมภาษณ์เสมือนจริง & STAR Feedback | 🟢 พร้อมใช้งาน |
            | **Phase 7** | **Career Planner** | แผนที่ Roadmaps & เช็คลิสต์ก้าวหน้า | 🟢 พร้อมใช้งาน |
            | **Phase 8** | **Email Writer & OCR** | ร่างจดหมาย, สแกนรูปภาพ & ส่งออก Excel | 🟢 พร้อมใช้งาน |
            """
        )

    with col_right, st.container(border=True):
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                <div style="font-size: 17px; font-weight: 700; color: {card_head_color};">⚙️ สถานะระบบ (System Health)</div>
                <span class="card-badge badge-indigo">LIVE MONITOR</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ตรวจสอบสถานะ DB
        if db_ready and check_db_health():
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: {status_bg_green}; border: {status_border_green}; border-radius: 10px; margin-bottom: 8px;">
                    <span style="font-size: 13px; font-weight: 600; color: {text_primary};">💾 ฐานข้อมูล SQLite</span>
                    <span style="font-size: 12px; font-weight: 700; color: {status_text_green};">🟢 ปกติ (Healthy)</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.error("🔴 ฐานข้อมูล SQLite: พบปัญหาการเชื่อมต่อ")

        active_base_url = get_openai_base_url()
        active_model = get_openai_model()
        provider_label = html.escape(
            f"Custom ({active_base_url})" if active_base_url else "OpenAI Official"
        )
        safe_active_model = html.escape(active_model)

        if is_openai_configured():
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: {status_bg_indigo}; border: {status_border_indigo}; border-radius: 10px; margin-bottom: 12px;">
                    <div>
                        <div style="font-size: 13px; font-weight: 600; color: {text_primary};">🤖 AI Engine: {provider_label}</div>
                        <div style="font-size: 11px; color: {sub_color}; margin-top: 2px;">โมเดล: <code style="color: {"#4338CA" if is_light else "#A5B4FC"};">{safe_active_model}</code></div>
                    </div>
                    <span style="font-size: 12px; font-weight: 700; color: {status_text_indigo};">🟢 เชื่อมต่อแล้ว</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.warning("🟡 AI Provider: ยังไม่ได้ระบุคีย์ (โปรดเพิ่มในไฟล์ `.env`)")

        with st.expander("📡 ทดสอบความหน่วงการเชื่อมต่อ API"):
            st.caption(f"ทดสอบยิงคำสั่ง Ping ไปยัง {provider_label}")
            if st.button("ทดสอบ Ping AI Provider", use_container_width=True):
                with st.spinner("กำลังทดสอบการเชื่อมต่อ..."):
                    result = ai_service.test_connection()
                    if result["success"]:
                        st.success(f"⚡ {result['message']}")
                    else:
                        st.error(f"❌ {result['message']}")


def main():
    # ตรวจสอบและตั้งค่าธีมเริ่มต้น (Default: Dark)
    if "app_theme" not in st.session_state:
        st.session_state["app_theme"] = "dark"
    current_theme = st.session_state["app_theme"]
    is_light = current_theme == "light"

    # ใช้งานสไตล์ตกแต่งหน้าตา Modern SaaS ตามธีมที่เลือก
    apply_custom_styles(theme=current_theme)

    # โหลดค่าล่าสุดจาก .env ทุกครั้งที่เรนเดอร์หน้าจอ
    reload_env()
    current_model = get_openai_model()
    current_base_url = get_openai_base_url()

    # Dynamic styling สำหรับ Sidebar ตามธีม
    sb_bg = (
        "linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%)"
        if is_light
        else "linear-gradient(135deg, rgba(30, 27, 75, 0.7) 0%, rgba(49, 46, 129, 0.5) 100%)"
    )
    sb_border = (
        "1.5px solid #C7D2FE" if is_light else "1px solid rgba(129, 140, 248, 0.3)"
    )
    sb_shadow = (
        "0 4px 14px rgba(99, 102, 241, 0.12)"
        if is_light
        else "0 8px 24px rgba(0, 0, 0, 0.3)"
    )
    sb_title_color = "#312E81" if is_light else "#C7D2FE"
    sb_sub_color = "#475569" if is_light else "#94A3B8"

    # --- ส่วนหัวของ Sidebar Navigation ---
    st.sidebar.markdown(
        f"""
        <div style="
            background: {sb_bg};
            padding: 20px;
            border-radius: 16px;
            margin-bottom: 14px;
            border: {sb_border};
            text-align: center;
            box-shadow: {sb_shadow};
        ">
            <div style="
                display: inline-flex;
                width: 48px;
                height: 48px;
                border-radius: 14px;
                background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
                align-items: center;
                justify-content: center;
                font-size: 24px;
                box-shadow: 0 4px 16px rgba(79, 70, 229, 0.5);
                margin-bottom: 10px;
            ">💼</div>
            <div style="
                font-size: 22px;
                font-weight: 900;
                letter-spacing: 0.8px;
                color: {sb_title_color};
            ">
                CAREER AGENT
            </div>
            <div style="display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: {sb_sub_color}; margin-top: 6px; font-weight: 600;">
                <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #10B981; box-shadow: 0 0 8px #10B981;"></span>
                <span>v2.0 • AI Career OS</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- ตัวเลือกสลับธีม (Theme Switcher: Dark / Light) ---
    st.sidebar.markdown(
        f"<p style='font-size: 12px; font-weight: 800; color: {sb_sub_color}; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.8px;'>THEME / รูปแบบสี</p>",
        unsafe_allow_html=True,
    )
    th_col1, th_col2 = st.sidebar.columns(2)
    with th_col1:
        if (
            st.button(
                "🌙 Dark",
                key="btn_theme_dark",
                use_container_width=True,
                type="primary" if not is_light else "secondary",
            )
            and current_theme != "dark"
        ):
            st.session_state["app_theme"] = "dark"
            st.rerun()
    with th_col2:
        if (
            st.button(
                "☀️ Light",
                key="btn_theme_light",
                use_container_width=True,
                type="primary" if is_light else "secondary",
            )
            and current_theme != "light"
        ):
            st.session_state["app_theme"] = "light"
            st.rerun()

    st.sidebar.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    menu_options = [
        "🏠 ภาพรวมแดชบอร์ด",
        "📄 วิเคราะห์เรซูเม่",
        "🔍 ค้นหาตำแหน่งงาน",
        "🎯 จับคู่งานและทักษะ",
        "🎙️ ฝึกซ้อมสัมภาษณ์",
        "📈 วางแผนเส้นทางอาชีพ",
        "📋 ติดตามการสมัครงาน",
        "✉️ ร่างอีเมลสมัครงาน",
    ]

    # ทำความสะอาด nav_selection หากมีค่าเก่าที่มีตัวเลขนำหน้า
    if "nav_selection" in st.session_state:
        legacy_map = {
            "📄 1. วิเคราะห์เรซูเม่": "📄 วิเคราะห์เรซูเม่",
            "🔍 2. ค้นหาตำแหน่งงาน": "🔍 ค้นหาตำแหน่งงาน",
            "🎯 3. จับคู่งานและทักษะ": "🎯 จับคู่งานและทักษะ",
            "🎙️ 4. ฝึกซ้อมสัมภาษณ์": "🎙️ ฝึกซ้อมสัมภาษณ์",
            "📈 5. วางแผนเส้นทางอาชีพ": "📈 วางแผนเส้นทางอาชีพ",
            "📋 6. ติดตามการสมัครงาน": "📋 ติดตามการสมัครงาน",
            "✉️ 7. ร่างอีเมลสมัครงาน": "✉️ ร่างอีเมลสมัครงาน",
        }
        if st.session_state["nav_selection"] in legacy_map:
            st.session_state["nav_selection"] = legacy_map[
                st.session_state["nav_selection"]
            ]

    # ตรวจสอบและเริ่มต้นค่าหน้าเพจใน session_state หากยังไม่มี
    if (
        "nav_selection" not in st.session_state
        or st.session_state["nav_selection"] not in menu_options
    ):
        st.session_state["nav_selection"] = menu_options[0]

    current_nav = st.session_state["nav_selection"]

    st.sidebar.markdown(
        f"<p style='font-size: 12px; font-weight: 800; color: {sb_sub_color}; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.8px;'>NAVIGATION MENU</p>",
        unsafe_allow_html=True,
    )

    for item in menu_options:
        is_active = current_nav == item
        if (
            st.sidebar.button(
                item,
                key=f"sidebar_btn_{item}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            )
            and not is_active
        ):
            st.session_state["nav_selection"] = item
            st.rerun()

    selected_page = st.session_state.get("nav_selection", menu_options[0])

    # --- กล่องแสดงข้อมูลสภาพแวดล้อมที่ Sidebar ---
    info_text_color = "#0F172A" if is_light else "#F1F5F9"
    info_code_color = "#4338CA" if is_light else "#A5B4FC"
    st.sidebar.markdown(
        f"<p style='font-size: 12px; font-weight: 800; color: {sb_sub_color}; text-transform: uppercase; margin-top: 22px; margin-bottom: 8px; letter-spacing: 0.8px;'>SYSTEM OVERVIEW</p>",
        unsafe_allow_html=True,
    )
    with st.sidebar.container(border=True):
        st.markdown(
            f"""
            <div style="font-size: 14.5px; line-height: 2.0; color: {info_text_color};">
                <div>🤖 <b>Model:</b> <code style="color: {info_code_color}; font-size: 13px;">{html.escape(current_model)}</code></div>
                <div>💾 <b>Database:</b> <span style="color: {"#16A34A" if is_light else "#34D399"}; font-weight: 700;">{"Ready (SQLite)" if db_ready else "Error"}</span></div>
                <div>🔑 <b>API Key:</b> <span style="color: {"#16A34A" if is_light and is_openai_configured() else ("#34D399" if is_openai_configured() else "#D97706" if is_light else "#FBBF24")}; font-weight: 700;">{"Configured" if is_openai_configured() else "Missing"}</span></div>
                <div>📝 <b>Notion:</b> <span style="color: {"#16A34A" if is_light and is_notion_configured() else ("#34D399" if is_notion_configured() else sb_sub_color)}; font-weight: 700;">{"Connected" if is_notion_configured() else "Not configured"}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if current_base_url:
            st.caption(f"🌐 Custom: `{current_base_url}`")

    # การนำทางไปยังแต่ละโมดูล
    try:
        if selected_page == "🏠 ภาพรวมแดชบอร์ด":
            render_dashboard_overview()
        elif selected_page == "📄 วิเคราะห์เรซูเม่":
            resume_analyzer.render()
        elif selected_page == "🔍 ค้นหาตำแหน่งงาน":
            job_hunter.render()
        elif selected_page == "🎯 จับคู่งานและทักษะ":
            job_matching.render()
        elif selected_page == "🎙️ ฝึกซ้อมสัมภาษณ์":
            interview_coach.render()
        elif selected_page == "📈 วางแผนเส้นทางอาชีพ":
            career_planner.render()
        elif selected_page == "📋 ติดตามการสมัครงาน":
            application_tracker.render()
        elif selected_page == "✉️ ร่างอีเมลสมัครงาน":
            email_writer.render()
    except Exception as e:
        logger.exception(f"เกิดข้อผิดพลาดในการโหลดหน้า '{selected_page}'")
        st.error(f"เกิดข้อผิดพลาดขณะโหลดหน้านี้: {e}")


if __name__ == "__main__":
    main()
