"""
โมดูลที่ 2: ค้นหาตำแหน่งงานอัจฉริยะ (Job Hunter)
ช่วยสร้างลิงก์และคำค้นหาอัจฉริยะสำหรับเว็บหางานชั้นนำ (LinkedIn, Indeed, Google Jobs, JobsDB)
วางกลยุทธ์การค้นหาด้วย AI และนำเข้าตำแหน่งงานที่สนใจเข้าสู่ระบบติดตามงาน (Application Tracker) ได้ทันที
"""
import urllib.parse
from typing import Dict, List, Optional
import streamlit as st
from config.settings import is_openai_configured
from modules.application_tracker import add_application, VALID_STATUSES, STATUS_LABELS
from services.ai_service import AIServiceError, ai_service
from utils.helpers import get_current_date_str
from utils.logger import setup_logger

logger = setup_logger("job_hunter")


# ==========================================
# ฟังก์ชันสร้างลิงก์ค้นหางาน (Portal Link Generators)
# ==========================================

def build_job_portal_urls(role: str, location: str = "", remote_only: bool = False) -> Dict[str, str]:
    """
    สร้างลิงก์สำหรับเปิดหน้าค้นหางานบนแพลตฟอร์มต่างๆ โดยอัตโนมัติ
    """
    clean_role = role.strip()
    clean_loc = location.strip()

    if remote_only:
        search_query = f"{clean_role} remote"
        search_loc = "Remote" if not clean_loc else clean_loc
    else:
        search_query = clean_role
        search_loc = clean_loc

    q_encoded = urllib.parse.quote_plus(search_query)
    loc_encoded = urllib.parse.quote_plus(search_loc)

    # รวม query สำหรับ google
    google_query = urllib.parse.quote_plus(f"jobs {search_query} {search_loc}".strip())

    urls = {
        "LinkedIn Jobs": f"https://www.linkedin.com/jobs/search/?keywords={q_encoded}&location={loc_encoded}",
        "Google Jobs": f"https://www.google.com/search?q={google_query}&ibp=htl;jobs",
        "Indeed": f"https://www.indeed.com/jobs?q={q_encoded}&l={loc_encoded}",
        "JobsDB (Thailand)": f"https://th.jobsdb.com/th/search-jobs/{urllib.parse.quote(search_query)}/1",
        "JobThai": f"https://www.jobthai.com/th/jobs?keyword={q_encoded}",
    }

    if remote_only:
        urls["RemoteOK"] = f"https://remoteok.com/remote-{q_encoded.replace('+', '-')}-jobs"
        urls["Wellfound (AngelList)"] = f"https://wellfound.com/jobs?role={q_encoded}"

    return urls


# ==========================================
# ตรรกะการวางกลยุทธ์ค้นหางานด้วย AI
# ==========================================

def generate_search_strategy_with_ai(
    role: str,
    skills: str,
    experience_level: str,
    location: str,
) -> str:
    """
    ใช้ OpenAI วางแผนกลยุทธ์การค้นหาคีย์เวิร์ด ชื่อตำแหน่งทางเลือก และ Boolean Search Query
    """
    if not role.strip():
        raise ValueError("กรุณาระบุตำแหน่งงานเป้าหมาย")

    system_prompt = (
        "คุณคือที่ปรึกษาด้านการจัดหางานและสรรหาบุคลากรมืออาชีพ (Senior Technical Recruiter)\n"
        "หน้าที่ของคุณคือแนะนำกลยุทธ์การค้นหาตำแหน่งงานที่มีประสิทธิภาพสูงสุดให้แก่ผู้สมัคร\n\n"
        "โปรดตอบกลับเป็นภาษาไทยที่กระชับ ตรงไปตรงมา และมีโครงสร้าง Markdown ดังนี้:\n"
        "### 1. 🎯 ชื่อตำแหน่งงานทางเลือกที่ควรใช้ค้นหา (Alternative Job Titles)\n"
        "- แนะนำ 4-5 ชื่อตำแหน่งที่บริษัทต่างๆ มักใช้เรียกแทนกัน\n\n"
        "### 2. 🔑 คำค้นหาและคีย์เวิร์ดทองคำ (Target Keywords)\n"
        "- คีย์เวิร์ดด้านเทคนิค, เครื่องมือ, และใบรับรองที่ HR มักใช้เป็นตัวกรอง\n\n"
        "### 3. ⚡ สูตรค้นหาขั้นสูงแบบบูลีน (Boolean Search Strings)\n"
        "- สร้างสูตรคำค้นหาพร้อมเครื่องมือ AND, OR, NOT, เครื่องหมายคำพูด \" \" สำหรับนำไปก๊อปปี้ค้นหาบน LinkedIn หรือ Google ได้ทันที 2-3 สูตร\n\n"
        "### 4. 💡 แหล่งและช่องทางค้นหาแนะนำ (Top Recommended Channels)\n"
        "- แนะนำกลุ่มชุมชน แพลตฟอร์ม หรือแหล่งงานที่เหมาะกับสายงานนี้เป็นพิเศษ\n"
    )

    user_prompt = (
        f"ตำแหน่งงานเป้าหมาย: {role}\n"
        f"ทักษะและความถนัดหลัก: {skills or 'ไม่ได้ระบุเจาะจง'}\n"
        f"ระดับประสบการณ์: {experience_level}\n"
        f"สถานที่ทำงานที่ต้องการ: {location or 'ไม่จำกัด / ทั่วไป'}\n"
    )

    logger.info(f"ขอคำแนะนำกลยุทธ์ค้นหางานจาก AI สำหรับ: {role}")
    return ai_service.generate_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.4,
    )


# ==========================================
# หน้าจอแสดงผล (Streamlit UI Views)
# ==========================================

def render_smart_query_view():
    """หน้าจอสร้างคำค้นหาและเปิดลิงก์ไปยังเว็บหางานต่างๆ"""
    st.subheader("🔍 ค้นหาและสร้างลิงก์ตำแหน่งงานด่วน")
    st.write("พิมพ์ตำแหน่งงานที่คุณต้องการ ระบบจะสร้างคำค้นหาและลิงก์ตรงไปยังเว็บรับสมัครงานชั้นนำทันที")

    col1, col2 = st.columns([2, 1])
    with col1:
        target_role = st.text_input("ตำแหน่งงานที่ต้องการค้นหา *", placeholder="เช่น Senior Python Engineer, Data Analyst, UX Designer", value="Software Engineer")
    with col2:
        target_location = st.text_input("สถานที่ทำงาน / เมือง", placeholder="เช่น Bangkok, Thailand หรือ Remote", value="Bangkok")

    remote_checkbox = st.checkbox("เน้นงานแบบทำงานระยะไกล (Remote 100%)", value=False)

    if target_role.strip():
        portal_urls = build_job_portal_urls(target_role, target_location, remote_checkbox)

        st.divider()
        st.write(f"ผลลัพธ์ลิงก์ค้นหางานสำหรับตำแหน่ง **{target_role}** ({'Remote' if remote_checkbox else target_location or 'ทุกพื้นที่'}):")

        # จัดแสดงเป็นการ์ดปุ่มกดเปิดลิงก์
        cols = st.columns(3)
        for idx, (portal_name, url) in enumerate(portal_urls.items()):
            col_target = cols[idx % 3]
            with col_target:
                with st.container(border=True):
                    st.markdown(f"**🌐 {portal_name}**")
                    st.link_button(f"เปิดดูงานบน {portal_name}", url, use_container_width=True)


def render_ai_strategy_view():
    """หน้าจอขอคำแนะนำกลยุทธ์ค้นหางานด้วย AI"""
    st.subheader("🤖 วางกลยุทธ์ค้นหาตำแหน่งงานด้วย AI")
    st.write("ให้ AI ช่วยแนะนำคีย์เวิร์ดที่นายจ้างมองหา และสร้างสูตรค้นหาขั้นสูง (Boolean Search) เพื่อค้นพบโอกาสที่คนอื่นมองข้าม")

    if not is_openai_configured():
        st.warning("⚠️ **ยังไม่ได้ตั้งค่า OpenAI API Key** โปรดระบุคีย์ในไฟล์ `.env` เพื่อใช้งานคำแนะนำจาก AI")

    col1, col2 = st.columns(2)
    with col1:
        role = st.text_input("ตำแหน่งงานเป้าหมาย *", placeholder="เช่น Full Stack Developer", key="ai_role_input")
        location = st.text_input("สถานที่ทำงานที่ต้องการ", placeholder="เช่น กรุงเทพฯ, Hybrid, Remote", key="ai_loc_input")
    with col2:
        exp_level = st.selectbox(
            "ระดับประสบการณ์",
            ["เด็กจบใหม่ / ไม่มีประสบการณ์ (Entry Level)", "ระดับกลาง (Mid-Level 2-4 ปี)", "ระดับอาวุโส (Senior 5+ ปี)", "หัวหน้าทีม / ผู้จัดการ (Lead / Manager)"],
            index=1,
        )
        skills = st.text_input("ทักษะหลักของคุณ (คั่นด้วยจุลภาค)", placeholder="เช่น React, Node.js, PostgreSQL, Docker")

    if st.button("🚀 สร้างกลยุทธ์และคำค้นหาอัจฉริยะ", type="primary", use_container_width=True):
        if not role.strip():
            st.error("กรุณาระบุตำแหน่งงานเป้าหมาย")
        else:
            with st.spinner("AI กำลังวิเคราะห์แนวโน้มตลาดและสร้างสูตรค้นหา..."):
                try:
                    strategy_result = generate_search_strategy_with_ai(
                        role=role,
                        skills=skills,
                        experience_level=exp_level,
                        location=location,
                    )
                    st.session_state["job_search_strategy"] = strategy_result
                    st.success("สร้างกลยุทธ์ค้นหางานสำเร็จแล้ว!")
                except AIServiceError as e:
                    st.error(f"เกิดข้อผิดพลาดจาก AI Service: {e}")
                except Exception as e:
                    logger.error(f"ข้อผิดพลาด: {e}", exc_info=True)
                    st.error(f"เกิดข้อผิดพลาด: {e}")

    if "job_search_strategy" in st.session_state:
        st.divider()
        st.subheader("📑 แผนกลยุทธ์และสูตรค้นหาจาก AI")
        st.markdown(st.session_state["job_search_strategy"])


def render_quick_import_view():
    """หน้าจอบันทึกตำแหน่งงานที่พบลัดเข้าสู่ Application Tracker ทันที"""
    st.subheader("📥 นำเข้าตำแหน่งงานสู่ระบบติดตาม (Quick Importer)")
    st.write("เมื่องานที่คุณสนใจจากเว็บต่างๆ เข้าตา คุณสามารถบันทึกเก็บไว้ในระบบ Application Tracker ได้ทันทีที่นี่")

    with st.form("quick_import_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input("ชื่อบริษัท *", placeholder="เช่น Tech Startup Ltd.")
            role = st.text_input("ชื่อตำแหน่งงาน *", placeholder="เช่น Backend Engineer")
            location = st.text_input("สถานที่ทำงาน", placeholder="เช่น Remote / สีลม, กรุงเทพฯ")
        with col2:
            status_selected = st.selectbox(
                "บันทึกไว้ในสถานะ",
                VALID_STATUSES,
                format_func=lambda s: STATUS_LABELS.get(s, s),
                index=0,  # Default: Wishlist
            )
            salary = st.text_input("เงินเดือนที่ระบุในประกาศ", placeholder="เช่น 60,000 - 90,000 บาท")
            applied_date = st.text_input("วันที่สมัคร (ถ้าสมัครแล้ว)", value=get_current_date_str())

        job_url = st.text_input("ลิงก์ประกาศงาน (URL) *", placeholder="https://www.linkedin.com/jobs/view/...")
        notes = st.text_area("หมายเหตุสั้นๆ เกี่ยวกับงานนี้", placeholder="จุดเด่นของบริษัท, ผู้แนะนำงาน, หรือกำหนดการปิดรับสมัคร...")

        submitted = st.form_submit_button("💾 นำเข้าเข้าสู่ Application Tracker ทันที", use_container_width=True)

        if submitted:
            if not company.strip() or not role.strip():
                st.error("กรุณาระบุทั้งชื่อบริษัทและตำแหน่งงาน")
            else:
                try:
                    new_id = add_application(
                        company=company,
                        role=role,
                        location=location,
                        salary=salary,
                        job_url=job_url,
                        status=status_selected,
                        applied_date=applied_date if status_selected != "Wishlist" else "",
                        notes=notes,
                    )
                    st.success(f"🎉 นำเข้าตำแหน่ง **{role}** ที่ **{company}** เข้าสู่ระบบเรียบร้อย (รหัสงาน #{new_id})!")
                    st.info("คุณสามารถไปตรวจสอบและย้ายขั้นตอนได้ที่เมนู **'ติดตามการสมัครงาน (Application Tracker)'**")
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดในการนำเข้างาน: {e}")


def render():
    """
    จุดเริ่มต้นการแสดงผลของโมดูล Job Hunter
    """
    st.header("🔍 ค้นหาตำแหน่งงานอัจฉริยะ (Job Hunter)")
    st.caption("ค้นหา รวบรวมคำค้นหา และนำเข้าตำแหน่งงานเป้าหมายเข้าสู่ท่อส่งการสมัครงาน")

    tab_query, tab_ai, tab_import = st.tabs([
        "🌐 ลิงก์ค้นหางานด่วน (Smart Links)",
        "🤖 วางกลยุทธ์และคีย์เวิร์ด (AI Strategy)",
        "📥 นำเข้าสู่งานที่ติดตาม (Quick Import)",
    ])

    with tab_query:
        render_smart_query_view()

    with tab_ai:
        render_ai_strategy_view()

    with tab_import:
        render_quick_import_view()
