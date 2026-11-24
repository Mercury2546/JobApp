"""
โมดูลที่ 7: ผู้ช่วยร่างอีเมลสมัครงาน & จดหมายปะหน้า (AI Application Email & Cover Letter Generator)
ช่วยสร้างอีเมลสมัครงาน, Cover Letter, อีเมลติดตามผล (Follow-up) และอีเมลขอบคุณหลังสัมภาษณ์
พร้อมระบบบันทึกเข้าสู่ Application Tracker ในคลิกเดียว และส่งออกข้อมูล
"""

from datetime import date, timedelta

import streamlit as st

from config.settings import is_openai_configured
from database.db import get_db_connection
from modules.application_tracker import STATUS_LABELS, VALID_STATUSES, add_application
from services.ai_service import AIServiceError, ai_service
from services.notion_service import (
    create_notion_job_page,
    is_notion_configured,
    render_notion_config_expander,
)
from utils.helpers import (
    extract_job_details_from_image,
    fetch_job_description_from_url,
)
from utils.logger import setup_logger

logger = setup_logger("email_writer")

EMAIL_TYPES = [
    "📨 อีเมลสมัครงาน (Job Application / Cold Email)",
    "📄 จดหมายปะหน้าแบบทางการ (Formal Cover Letter)",
    "⏰ อีเมลติดตามผล (Follow-up Email หลัง 1-2 สัปดาห์)",
    "🤝 อีเมลขอบคุณหลังสัมภาษณ์ (Post-Interview Thank You)",
]

TONES = [
    "💼 มืออาชีพและน่าเชื่อถือ (Formal & Corporate)",
    "🚀 ทันสมัย มั่นใจ สไตล์ Tech (Confident & Modern Tech)",
    "⚡ กระตือรือร้น คล่องตัว สไตล์ Startup (Energetic & Startup)",
]

LANGUAGES = [
    "🇹🇭 ภาษาไทย (สุภาพ ระดับทางการ)",
    "🇬🇧 English (Business Professional)",
]


def get_available_resumes() -> list[dict]:
    """ดึงข้อมูลเรซูเม่ที่เคยวิเคราะห์ไว้ในระบบเพื่อนำมาใช้อ้างอิง"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, title, raw_text, file_name, created_at FROM resumes ORDER BY id DESC;"
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:  # noqa: BLE001 — fallback to empty resume list
        logger.warning(f"ไม่สามารถโหลดข้อมูลเรซูเม่ได้: {e}")
        return []


def extract_company_and_role_from_jd(jd_text: str) -> tuple[str, str]:
    """ใช้ AI ช่วยสกัดชื่อบริษัทและตำแหน่งงานจากเนื้อหาประกาศงานอย่างรวดเร็ว"""
    if not is_openai_configured() or not jd_text.strip():
        return "", ""
    try:
        sys_prompt = "You extract the Company Name and Job Role from a job posting. Reply strictly in this format:\nCOMPANY: <company name>\nROLE: <job title>"
        user_prompt = f"Extract the target company name and job role from this job posting:\n{jd_text[:1200]}"
        response = ai_service.generate_response(
            sys_prompt, user_prompt, temperature=0.1, max_tokens=60
        )
        company, role = "", ""
        for line in response.splitlines():
            if line.upper().startswith("COMPANY:"):
                company = line.split(":", 1)[1].strip()
            elif line.upper().startswith("ROLE:"):
                role = line.split(":", 1)[1].strip()
        return company, role
    except Exception as e:  # noqa: BLE001 — optional AI extraction
        logger.warning(f"ไม่สามารถสกัดชื่อบริษัทและตำแหน่งได้: {e}")
        return "", ""


def generate_email_prompt(
    email_type: str,
    language: str,
    tone: str,
    company: str,
    role: str,
    recipient: str,
    job_description: str,
    candidate_profile: str,
    extra_notes: str,
    candidate_name: str = "",
    candidate_pronoun: str = "ผม",
) -> tuple[str, str]:
    """
    สร้าง System Prompt และ User Prompt อิงตามมาตรฐานการคัดเลือกบุคลากรสากล (SHRM, Harvard Career Services, Google XYZ Formula)
    เน้นความน่าเชื่อถือสูง กระชับ ตรงประเด็น และตัดคำเยินยอหรือสำนวนหุ่นยนต์ (AI Clichés) ทิ้งทั้งหมด
    พร้อมรองรับชื่อผู้สมัครภาษาไทย/อังกฤษ และสรรพนามแทนตัวเอง (ผม / ดิฉัน) อย่างถูกต้อง
    """
    is_english = "English" in language
    clean_name = candidate_name.strip()

    if is_english:
        name_instruction = (
            f"Candidate Name: '{clean_name}'. Use this exact name in the email signature block and subject line options."
            if clean_name
            else "Candidate Name: Not specified. Use [Your Name] as a clear placeholder token."
        )
        system_prompt = (
            "You are a Senior Executive Recruiter and Career Communication Expert following Harvard Career Services "
            "and Google's XYZ hiring communication standards. You write high-credibility, concise, and impact-driven "
            "job application emails that hiring managers and recruiters take seriously.\n\n"
            "STRICT RULES TO ENSURE HIGH CREDIBILITY:\n"
            "1. NO FLUFF OR AI CLICHÉS: Never use phrases like 'I hope this email finds you well', 'prestigious company', "
            "'esteemed organization', 'thrilled to apply', or empty self-praise.\n"
            f"2. CANDIDATE SIGNATURE: {name_instruction}\n"
            "3. THE 3-PARAGRAPH RECRUITER FRAMEWORK:\n"
            "   - Hook (2-3 sentences): Direct statement of the role, referral/source, and high-level fit.\n"
            "   - Proof (2-3 crisp bullet points): Concrete evidence using Google's XYZ formula (Achieved [X], measured by [Y], by doing [Z]).\n"
            "   - Call-to-Action & Enclosures: Reference attached Resume/Portfolio and propose a concise 15-minute introductory call.\n"
            "4. REALISTIC & SCANNABLE: Keep total body length strictly between 120 - 180 words. Recruiters scan in 7 seconds."
        )
    else:
        if candidate_pronoun in ["ผม", "ดิฉัน"]:
            pronoun_rule = f"ใช้สรรพนามแทนตัวเองว่า '{candidate_pronoun}' อย่างสม่ำเสมอ เป็นธรรมชาติ สุภาพ ห้ามใช้ 'ข้าพเจ้า' เด็ดขาด"
        else:
            pronoun_rule = "ใช้สรรพนามสุภาพและเป็นกลางตามแบบแผนงานบุคคล"

        if clean_name:
            name_rule = f"ลงชื่อท้ายอีเมลด้วย '{clean_name}' และระบุชื่อนี้ใน Subject Line ห้ามใส่ placeholder ลอย ๆ เช่น [ชื่อของคุณ] หรือ [ชื่อผู้สมัคร]"
        else:
            name_rule = "หากไม่ระบุชื่อ ให้ใส่ [ชื่อ-นามสกุล ของคุณ]"

        system_prompt = (
            "คุณคือผู้เชี่ยวชาญด้านการสรรหาบุคลากรระดับ Senior HR & Executive Headhunter ในไทย "
            "ที่เข้าใจพฤติกรรมการคัดเลือกใบสมัครขององค์กรชั้นนำ (อิงมาตรฐานการสื่อสารของ SHRM, Harvard Career Services "
            "และแนวทางคัดกรองเรซูเม่ของ Adecco / Tech Recruiters ในไทย)\n\n"
            "กฎเหล็กเพื่อสร้างความน่าเชื่อถือสูงสุด (High-Trust Standards):\n"
            "1. ห้ามใช้สำนวนหุ่นยนต์และคำเยินยอเกินจริงเด็ดขาด (No AI Fluff): ห้ามใช้ 'บริษัทอันทรงเกียรติ', 'วิสัยทัศน์อันกว้างไกล', "
            "'ข้าพเจ้า', 'รู้สึกเป็นเกียรติอย่างยิ่ง', 'มีความกระตือรือร้นเป็นล้นพ้น', 'ทักษะอันล้ำค่า' เพราะทำให้ผู้สมัครดูไม่น่าเชื่อถือและเหมือนใช้ AI สแปม\n"
            f"2. สรรพนามและการลงชื่อ: {pronoun_rule} และ {name_rule}\n"
            "3. โครงสร้าง 3 ส่วนที่ HR ตัวจริงต้องการอ่าน (อ่านจบใน 7 วินาที):\n"
            "   - ส่วนที่ 1 (จุดประสงค์ตรงประเด็น): ระบุตำแหน่งที่สมัคร ช่องทางที่ทราบข่าว และ 1 ประโยคสรุปจุดเด่น\n"
            "   - ส่วนที่ 2 (หลักฐานความสามารถ 2-3 Bullet Points): นำทักษะหรือผลงานจริงของผู้สมัครมาจับคู่กับสิ่งที่ JD ต้องการ ใช้ตัวเลข/เครื่องมือที่ชัดเจน (ไม่ใช่แค่คำชมตัวเองลอยๆ)\n"
            "   - ส่วนที่ 3 (การนัดหมายและเอกสารแนบ): แจ้งเอกสารที่แนบมา (Resume, Portfolio) พร้อมเสนอความพร้อมในการพูดคุยสัมภาษณ์ และลงท้ายด้วยลายเซ็นต์ติดต่อมาตรฐาน\n"
            "4. ความยาวกระชับ: เนื้อหาอีเมลต้องไม่เกิน 150-200 คำ สุภาพแบบมืออาชีพ ถูกกาลเทศะ และเหมือนคนทำงานจริงเขียนเอง"
        )

    signoff_name = clean_name if clean_name else "[ชื่อ-นามสกุล ของคุณ]"
    subject_candidate = clean_name if clean_name else "[ชื่อผู้สมัคร]"

    user_prompt = f"""
กรุณาร่างข้อความการสื่อสารเพื่อสมัครงานที่ 'น่าเชื่อถือ สมจริง และทรงพลัง' ตามเกณฑ์มาตรฐาน HR สากล:

📌 **ประเภทของข้อความ:** {email_type}
🌐 **ภาษา:** {language}
🎭 **ระดับของน้ำเสียง (Tone):** {tone}
🏢 **บริษัทเป้าหมาย:** {company}
💼 **ตำแหน่งงาน:** {role}
👤 **ชื่อผู้สมัคร (Applicant Name):** {clean_name if clean_name else "ไม่ระบุ (ใช้รูปแบบมาตรฐาน)"}
🗣️ **สรรพนามแทนตัวเอง (Preferred Pronoun):** {candidate_pronoun}
👤 **ผู้รับข้อความ (Recipient):** {recipient if recipient.strip() else "ฝ่ายทรัพยากรบุคคล / Hiring Manager"}

📝 **คำอธิบายงาน / ข้อกำหนดตำแหน่ง (Job Description & Requirements):**
{job_description.strip() if job_description.strip() else "ไม่ระบุ ให้ร่างตามมาตรฐานตำแหน่งงานจริงในอุตสาหกรรม"}

👤 **ข้อมูลและจุดเด่นของผู้สมัคร (Candidate Profile / Key Strengths):**
{candidate_profile.strip() if candidate_profile.strip() else "มีประสบการณ์และทักษะที่เกี่ยวข้องโดยตรงกับตำแหน่งงาน"}

💡 **ข้อมูลเพิ่มเติมหรือเงื่อนไขพิเศษ:**
{extra_notes.strip() if extra_notes.strip() else "ไม่มี"}

---

🎯 **รูปแบบผลลัพธ์ที่ต้องการ (Strict High-Trust Output Format):**

### 1. 🎯 หัวข้ออีเมลมาตรฐานที่ HR เปิดอ่านทันที (Subject Line Options)
(เสนอ 3 ตัวเลือกที่ใช้โครงสร้างตามมาตรฐาน Recruiter เช่น `สมัครงานตำแหน่ง {role} - {subject_candidate}`)

### 2. ✉️ เนื้อหาอีเมลฉบับสมบูรณ์ (Complete High-Trust Email Body)
(เขียนเนื้อหาพร้อมส่งจริง ใช้สรรพนาม '{candidate_pronoun}' อย่างสม่ำเสมอ มี 2-3 Bullet points ที่เป็นหลักฐานผลงานจริง **ห้ามมีคำเยินยอเว่อร์เด็ดขาด** พร้อมลงชื่อ '{signoff_name}' ในส่วนลายเซ็นต์ท้ายอีเมล)

### 3. 🔍 วิเคราะห์หลักความน่าเชื่อถือที่ใช้ (Credibility Breakdown)
- **Framework ที่ใช้:** (เช่น Harvard 3-Paragraph Rule + Google XYZ Metric)
- **จุดที่ตรงใจ HR:** (ทำไมเนื้อหานี้ถึงผ่านเกณฑ์การสแกน 7 วินาทีของ Recruiter)
"""
    return system_prompt, user_prompt


def render():
    """เรนเดอร์หน้าจอโมดูลร่างอีเมลสมัครงาน & Cover Letter"""
    st.header("✉️ ผู้ช่วยร่างอีเมลสมัครงาน & Cover Letter (AI Job Emailer)")
    st.caption(
        "สร้างอีเมลสมัครงาน, Cover Letter และ Follow-up สไตล์มืออาชีพ พร้อมบันทึกลงระบบติดตามงานในคลิกเดียว"
    )

    if not is_openai_configured():
        st.warning(
            "⚠️ ยังไม่ได้ระบุ API Key สำหรับบริการ AI กรุณาตั้งค่าในไฟล์ `.env` ก่อนใช้งานฟังก์ชันร่างอีเมล"
        )

    tab_generator, tab_history_guide = st.tabs(
        [
            "✨ ร่างอีเมลใหม่ด้วย AI",
            "📖 คู่มือและเทมเพลตมาตรฐาน",
        ]
    )

    with tab_generator:
        col_type, col_lang, col_tone = st.columns(3)
        with col_type:
            selected_type = st.selectbox("📌 ประเภทข้อความ", EMAIL_TYPES, index=0)
        with col_lang:
            selected_lang = st.selectbox("🌐 ภาษาที่ต้องการ", LANGUAGES, index=0)
        with col_tone:
            selected_tone = st.selectbox("🎭 โทนเสียง (Tone)", TONES, index=0)

        # --- ข้อมูลและตัวตนผู้สมัคร (Candidate Identity & Pronouns) ---
        with st.container(border=True):
            st.markdown("##### 👤 ข้อมูลและตัวตนผู้สมัคร (Candidate Profile & Identity)")
            id_col1, id_col2 = st.columns([1, 1])
            with id_col1:
                saved_name = st.session_state.get("user_candidate_name", "")
                candidate_name = st.text_input(
                    "ชื่อ-นามสกุล ผู้สมัคร (ภาษาไทย หรือ อังกฤษ)",
                    value=saved_name,
                    placeholder="เช่น กานต์ วรเมธ หรือ Karn Worameth",
                    help="AI จะนำชื่อนี้ไปใส่ในหัวข้ออีเมลและลงชื่อท้ายอีเมลให้อัตโนมัติ",
                    key="input_candidate_name",
                )
                if candidate_name != saved_name:
                    st.session_state["user_candidate_name"] = candidate_name

            with id_col2:
                saved_pronoun = st.session_state.get("user_candidate_pronoun", "ผม")
                pronoun_options = ["ผม", "ดิฉัน", "ไม่ระบุ (ใช้สรรพนามกลาง / ภาษาอังกฤษ)"]
                pronoun_idx = (
                    pronoun_options.index(saved_pronoun)
                    if saved_pronoun in pronoun_options
                    else 0
                )
                selected_pronoun = st.radio(
                    "สรรพนามแทนตัวเองในอีเมล / Cover Letter",
                    pronoun_options,
                    index=pronoun_idx,
                    horizontal=True,
                    help="เลือก 'ผม' หรือ 'ดิฉัน' เพื่อให้ AI ใช้สรรพนามอย่างสม่ำเสมอและสุภาพตามกาลเทศะ",
                    key="radio_candidate_pronoun",
                )
                st.session_state["user_candidate_pronoun"] = selected_pronoun

        # --- กล่องตัวช่วยนำเข้าข้อมูล JD อัตโนมัติ (URL & ภาพโปสเตอร์ Facebook) ---
        with st.expander(
            "🪄 ตัวช่วยพิเศษ: ดึงเนื้อหา JD จากลิงก์ หรือ รูปภาพโปสเตอร์ (Facebook / Screenshot)",
            expanded=False,
        ):
            tab_opt_url, tab_opt_image = st.tabs(
                [
                    "🔗 ดึงจากลิงก์เว็บ (Job URL)",
                    "🖼️ สแกนจากรูปภาพ / โปสเตอร์ (Facebook / Screenshot)",
                ]
            )

            with tab_opt_url:
                st.caption(
                    "คัดลอกลิงก์ประกาศรับสมัครงานจากเว็บ เช่น JobsDB, LinkedIn, Blognone, เว็บไซต์บริษัท เพื่อให้ AI ดึงเนื้อหาให้อัตโนมัติ"
                )
                col_url, col_fetch = st.columns([4, 1])
                with col_url:
                    job_url_input = st.text_input(
                        "ลิงก์ประกาศรับสมัครงาน (URL)",
                        value=st.session_state.get("attached_job_url", ""),
                        placeholder="เช่น https://th.jobsdb.com/job/... หรือ https://careers.company.com/...",
                        key="input_job_url_fetcher",
                    )
                with col_fetch:
                    fetch_btn = st.button(
                        "🌐 ดึงข้อมูล JD", use_container_width=True, key="btn_do_fetch_jd"
                    )

                if fetch_btn:
                    if not job_url_input.strip():
                        st.warning("กรุณาระบุ URL ของประกาศงานก่อน")
                    else:
                        with st.spinner(
                            "🌐 กำลังเชื่อมต่อไปยังเว็บไซต์เพื่ออ่านเนื้อหาประกาศงาน..."
                        ):
                            fetch_result = fetch_job_description_from_url(job_url_input)
                            if fetch_result["success"]:
                                st.session_state["attached_job_url"] = fetch_result[
                                    "url"
                                ]
                                st.session_state["fetched_jd_text"] = fetch_result[
                                    "text"
                                ]
                                st.session_state["shared_job_url"] = fetch_result["url"]
                                st.session_state["shared_jd_text"] = fetch_result[
                                    "text"
                                ]
                                st.toast(
                                    f"✅ ดึงเนื้อหาประกาศงานสำเร็จ! ({len(fetch_result['text'])} ตัวอักษร)"
                                )

                                # ลองให้ AI สกัดชื่อบริษัทและตำแหน่ง
                                extracted_c, extracted_r = (
                                    extract_company_and_role_from_jd(
                                        fetch_result["text"]
                                    )
                                )
                                if extracted_c:
                                    st.session_state["extracted_company"] = extracted_c
                                    st.session_state["shared_company"] = extracted_c
                                if extracted_r:
                                    st.session_state["extracted_role"] = extracted_r
                                    st.session_state["shared_role"] = extracted_r
                                if extracted_c or extracted_r:
                                    st.toast(
                                        f"💡 สกัดข้อมูล: {extracted_c} — {extracted_r}"
                                    )
                                st.rerun()
                            else:
                                st.error(f"❌ {fetch_result['error']}")
                                st.info(
                                    "💡 คำแนะนำ: หากหน้าเว็บล็อกอินหรือมีระบบป้องกัน Bot (เช่น Facebook) คุณสามารถแคปหน้าจอแล้วมาใช้แท็บ 'สแกนจากรูปภาพ' ได้เลยครับ"
                                )

            with tab_opt_image:
                st.caption(
                    "สำหรับประกาศงานบน Facebook, LINE หรือโปสเตอร์ Infographic: เพียงแคปหน้าจอหรือบันทึกรูปมาอัปโหลดที่นี่"
                )
                uploaded_poster = st.file_uploader(
                    "อัปโหลดรูปภาพประกาศงาน (PNG, JPG, JPEG, WEBP)",
                    type=["png", "jpg", "jpeg", "webp"],
                    key="uploader_job_poster",
                )

                if uploaded_poster:
                    col_img_prev, col_img_action = st.columns([1, 2])
                    with col_img_prev:
                        st.image(
                            uploaded_poster,
                            caption="ภาพประกาศงานที่อัปโหลด",
                            use_container_width=True,
                        )
                    with col_img_action:
                        st.write(
                            f"📁 ชื่อไฟล์: `{uploaded_poster.name}` ({uploaded_poster.size // 1024} KB)"
                        )
                        scan_btn = st.button(
                            "🔍 ให้ AI Vision สแกนและถอดข้อมูลจากภาพทันที",
                            type="primary",
                            use_container_width=True,
                            key="btn_scan_poster",
                        )

                        if scan_btn:
                            with st.spinner(
                                "🤖 AI Vision กำลังสแกนภาพ ถอดตัวหนังสือ สกัดบริษัท ตำแหน่ง เงินเดือน และอีเมล HR..."
                            ):
                                img_bytes = uploaded_poster.getvalue()
                                mime_t = uploaded_poster.type or "image/jpeg"
                                scan_res = extract_job_details_from_image(
                                    img_bytes, mime_type=mime_t
                                )

                                if scan_res["success"]:
                                    # บันทึกรูปภาพโปสเตอร์ไว้ใน session_state เพื่อส่งขึ้น Notion ด้วย
                                    st.session_state["attached_poster_bytes"] = (
                                        img_bytes
                                    )
                                    st.session_state["attached_poster_name"] = (
                                        uploaded_poster.name
                                    )
                                    st.session_state["attached_poster_mime"] = mime_t

                                    if scan_res.get("company"):
                                        st.session_state["extracted_company"] = (
                                            scan_res["company"]
                                        )
                                        st.session_state["shared_company"] = scan_res[
                                            "company"
                                        ]
                                    if scan_res.get("role"):
                                        st.session_state["extracted_role"] = scan_res[
                                            "role"
                                        ]
                                        st.session_state["shared_role"] = scan_res[
                                            "role"
                                        ]
                                    if scan_res.get("salary"):
                                        st.session_state["extracted_salary"] = scan_res[
                                            "salary"
                                        ]
                                    if scan_res.get("email_contact"):
                                        st.session_state["extracted_recipient"] = (
                                            scan_res["email_contact"]
                                        )
                                    if scan_res.get("job_description"):
                                        st.session_state["fetched_jd_text"] = scan_res[
                                            "job_description"
                                        ]
                                        st.session_state["shared_jd_text"] = scan_res[
                                            "job_description"
                                        ]

                                    st.toast(
                                        f"🎉 สแกนภาพสำเร็จ: {scan_res.get('company') or 'ตามระบุ'} — "
                                        f"{scan_res.get('role') or 'ตามระบุ'}"
                                    )
                                    st.rerun()
                                else:
                                    st.error(f"❌ {scan_res['error']}")

        col1, col2 = st.columns(2)
        with col1:
            company_default = st.session_state.get(
                "extracted_company"
            ) or st.session_state.get("shared_company", "")
            company_input = st.text_input(
                "ชื่อบริษัท / องค์กร *",
                value=company_default,
                placeholder="เช่น Agoda, SCB TechX, LINE MAN Wongnai",
                key="input_company_name",
            )

            # --- ส่วนเลือกตำแหน่งงาน ---
            extracted_r = (
                st.session_state.get("extracted_role")
                or st.session_state.get("shared_role", "")
            ).strip()
            role_options = []
            if extracted_r and extracted_r not in [
                "Graphic Designer",
                "UX/UI Designer",
                "Graphic & Content Creator",
                "Product Designer (UI/UX)",
                "Web & Graphic Designer",
            ]:
                role_options.append(f"🎯 {extracted_r} (ดึงจากประกาศ/รูปภาพ)")

            role_options.extend(
                [
                    "🎨 Graphic Designer",
                    "✨ UX/UI Designer",
                    "🖌️ Graphic & Content Creator",
                    "📱 Product Designer (UI/UX)",
                    "💻 Web & Graphic Designer",
                    "✏️ พิมพ์ระบุตำแหน่งอื่นเอง...",
                ]
            )

            # ตรวจสอบตัวเลือกเริ่มต้น
            saved_choice = st.session_state.get("selected_role_choice")
            default_idx = 0
            if saved_choice and saved_choice in role_options:
                default_idx = role_options.index(saved_choice)
            elif extracted_r and role_options:
                default_idx = 0

            chosen_role_preset = st.radio(
                "ตำแหน่งงานที่สมัคร * (กดเลือกได้ทันที)",
                options=role_options,
                index=default_idx,
                key="radio_selected_role_choice",
                help="คลิกเลือกตำแหน่งงานที่ต้องการได้ทันที ไม่มีเคอร์เซอร์พิมพ์กวนใจ",
            )
            st.session_state["selected_role_choice"] = chosen_role_preset

            if chosen_role_preset == "✏️ พิมพ์ระบุตำแหน่งอื่นเอง...":
                role_input = st.text_input(
                    "ระบุชื่อตำแหน่งงาน *",
                    value=st.session_state.get("custom_role_text", ""),
                    placeholder="เช่น Senior Motion Graphic Designer, Brand Designer",
                    key="input_custom_role_text",
                )
                st.session_state["custom_role_text"] = role_input
            elif chosen_role_preset.startswith("🎯 "):
                role_input = extracted_r
            else:
                role_input = (
                    chosen_role_preset.replace("🎨 ", "")
                    .replace("✨ ", "")
                    .replace("🖌️ ", "")
                    .replace("📱 ", "")
                    .replace("💻 ", "")
                    .replace("🎯 ", "")
                    .strip()
                )

            st.caption(f"📌 ตำแหน่งที่เลือกใช้: **{role_input}**")

        with col2:
            recipient_default = st.session_state.get("extracted_recipient", "")
            recipient_input = st.text_input(
                "ชื่อผู้รับ / อีเมล HR (ถ้าทราบ)",
                value=recipient_default,
                placeholder="เช่น คุณสมศักดิ์ (HR) หรือ hr@company.com",
                help="หากสแกนจากภาพโปสเตอร์ AI จะดึงอีเมลที่ระบุในภาพมากรอกให้อัตโนมัติ",
            )

            # ดึง Resume ที่เคยวิเคราะห์ไว้ในระบบมาช่วยกรอกข้อมูล
            saved_resumes = get_available_resumes()
            has_shared_res = bool(
                st.session_state.get("shared_resume_text", "").strip()
            )
            resume_options = ["(พิมพ์ข้อมูลจุดเด่นเอง)"]
            if has_shared_res:
                resume_options.append("✨ ใช้เรซูเม่ล่าสุดในเซสชัน")
            resume_options.extend(
                [f"#{r['id']} {r['title']} ({r['file_name']})" for r in saved_resumes]
            )
            default_res_idx = 1 if has_shared_res else 0
            selected_resume_option = st.selectbox(
                "📂 ดึงข้อมูลจาก Resume ในระบบ", resume_options, index=default_res_idx
            )

        # ข้อมูลเงินเดือนที่สกัดได้จากภาพ (ถ้ามี)
        extracted_sal = st.session_state.get("extracted_salary")
        if extracted_sal:
            st.info(f"💰 **ฐานเงินเดือนที่ระบุในประกาศ/รูปภาพ:** {extracted_sal}")

        # ข้อมูลโปรไฟล์ผู้สมัคร (ถ้าเลือก Resume ในระบบจะดึงข้อความมาให้อัตโนมัติ)
        default_candidate_text = ""
        if selected_resume_option == "✨ ใช้เรซูเม่ล่าสุดในเซสชัน":
            default_candidate_text = st.session_state.get("shared_resume_text", "")[
                :1400
            ]
        elif selected_resume_option != "(พิมพ์ข้อมูลจุดเด่นเอง)" and saved_resumes:
            offset = 2 if has_shared_res else 1
            sel_idx = resume_options.index(selected_resume_option) - offset
            if 0 <= sel_idx < len(saved_resumes):
                res = saved_resumes[sel_idx]
                default_candidate_text = res.get("raw_text", "")[:1200]
                if res.get("analysis_summary"):
                    default_candidate_text += (
                        f"\n\n[สรุปจุดแข็ง]:\n{res.get('analysis_summary')[:600]}"
                    )

        candidate_profile = st.text_area(
            "จุดเด่นและประสบการณ์สำคัญของคุณ (Candidate Highlights) *",
            value=default_candidate_text,
            height=130,
            placeholder="เช่น มีประสบการณ์ออกแบบ UX/UI Web & Mobile App 3 ปี, เชี่ยวชาญ Figma, Adobe Creative Cloud, มีทักษะ Graphic และ Design System...",
            help="ระบุทักษะเด่น ความสำเร็จ หรือตัวเลขผลงาน เพื่อให้ AI ดึงไปเขียนเป็น Hook ดึงดูด HR",
        )

        jd_default_val = st.session_state.get(
            "fetched_jd_text"
        ) or st.session_state.get("shared_jd_text", "")
        job_desc = st.text_area(
            "คำอธิบายงาน / คุณสมบัติที่ต้องการ (Job Description / Requirements) *",
            value=jd_default_val,
            height=150,
            placeholder="วางเนื้อหาประกาศรับสมัครงาน หรือใส่ลิงก์ด้านบนแล้วกด 'ดึงข้อมูล JD'...",
            help="AI จะนำข้อความนี้มาวิเคราะห์หา Keywords สำคัญเพื่อใส่ลงในอีเมลให้ตรงใจผู้คัดเลือก",
        )

        extra_notes = st.text_input(
            "ข้อมูลเพิ่มเติม (ถ้ามี)",
            placeholder="เช่น แนบลิงก์ Portfolio www.behance.net/... หรือ Dribbble, ทราบตำแหน่งนี้จาก LinkedIn",
        )

        generate_btn = st.button(
            "✨ ให้ AI ร่างอีเมลและ Cover Letter ทันที",
            type="primary",
            use_container_width=True,
        )

        if generate_btn:
            if not company_input.strip() or not role_input.strip():
                st.error("กรุณาระบุชื่อบริษัทและตำแหน่งงานก่อนเริ่มร่างอีเมล")
            elif not candidate_profile.strip() and not job_desc.strip():
                st.error("กรุณากรอกข้อมูลจุดเด่นของคุณหรือรายละเอียดงานอย่างน้อย 1 รายการ")
            else:
                with st.spinner("🤖 กำลังวิเคราะห์ JD และร้อยเรียงอีเมลสมัครงานระดับมืออาชีพ..."):
                    try:
                        system_prompt, user_prompt = generate_email_prompt(
                            email_type=selected_type,
                            language=selected_lang,
                            tone=selected_tone,
                            company=company_input,
                            role=role_input,
                            recipient=recipient_input,
                            job_description=job_desc,
                            candidate_profile=candidate_profile,
                            extra_notes=extra_notes,
                            candidate_name=candidate_name,
                            candidate_pronoun=selected_pronoun,
                        )

                        generated_content = ai_service.generate_response(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            temperature=0.65,
                        )

                        # บันทึกผลลัพธ์ลงใน session_state
                        st.session_state["last_generated_email"] = {
                            "company": company_input.strip(),
                            "role": role_input.strip(),
                            "recipient": recipient_input.strip(),
                            "candidate_name": candidate_name.strip(),
                            "pronoun": selected_pronoun,
                            "type": selected_type,
                            "content": generated_content,
                        }
                        st.success("🎉 ร่างอีเมลและจดหมายแนะนำตัวสำเร็จเรียบร้อย!")
                    except AIServiceError as e:
                        st.error(f"เกิดข้อผิดพลาดจากบริการ AI: {e}")
                    except Exception as e:
                        logger.exception("Unexpected error while generating email")
                        st.error(f"เกิดข้อผิดพลาดในการประมวลผล: {e}")

        # แสดงผลลัพธ์ที่สร้างไว้
        last_result = st.session_state.get("last_generated_email")
        if last_result:
            st.divider()
            st.subheader(
                f"📋 ผลลัพธ์: {last_result['type']} สำหรับ {last_result['company']}"
            )

            result_text = last_result["content"]
            st.markdown(result_text)

            st.divider()

            # ส่วนการทำงานด่วน: บันทึกลง Notion Database และ Tracker ในคลิกเดียว
            st.markdown("### 🚀 ส่งข้อมูลการสมัครงานเข้า Notion & บันทึกลงระบบติดตาม")
            st.caption(
                "ส่งข้อมูลบริษัท ตำแหน่ง วันที่ และเนื้อหาอีเมลที่ AI ร่างไว้ เข้าสู่ Notion Database ของคุณทันที หรือบันทึกลงระบบภายในเครื่อง"
            )

            # กล่องตั้งค่า Notion แบบพับได้
            render_notion_config_expander(key_prefix="email_writer_save")

            save_col1, save_col2, save_col3 = st.columns([2, 2, 2])
            with save_col1:
                tracker_status = st.selectbox(
                    "สถานะเริ่มต้น",
                    VALID_STATUSES,
                    format_func=lambda s: STATUS_LABELS.get(s, s),
                    index=VALID_STATUSES.index("Applied"),
                    key="save_email_status",
                )
            with save_col2:
                applied_date_val = st.date_input(
                    "วันที่ส่งสมัคร", value=date.today(), key="save_email_applied_date"
                )
            with save_col3:
                follow_up_days = st.number_input(
                    "แจ้งเตือน Follow-up (อีกกี่วัน)",
                    min_value=1,
                    max_value=60,
                    value=7,
                    key="save_email_follow_days",
                )
                follow_up_date_val = applied_date_val + timedelta(days=follow_up_days)

            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                save_location = st.text_input(
                    "สถานที่ทำงาน (Location)",
                    value=st.session_state.get("extracted_location", ""),
                    placeholder="เช่น กรุงเทพฯ / Hybrid / Remote",
                    key="save_email_location",
                )
            with detail_col2:
                save_salary = st.text_input(
                    "เงินเดือน / ค่าตอบแทน (Salary)",
                    value=st.session_state.get("extracted_salary", ""),
                    placeholder="เช่น 30,000 - 45,000 บาท",
                    key="save_email_salary",
                )

            subj_name = last_result.get("candidate_name") or st.session_state.get(
                "user_candidate_name", ""
            )
            default_subj = (
                f"Application for {last_result['role']} - {subj_name}"
                if subj_name
                else f"Application for {last_result['role']} - {last_result['company']}"
            )
            custom_subject = st.text_input(
                "หัวข้ออีเมลที่ใช้จริง (Subject Line)",
                value=default_subj,
                key="save_email_subject",
            )

            # --- จัดการรูปภาพประกาศงาน / โปสเตอร์ (Poster / Screenshot) ---
            attached_img_bytes = st.session_state.get("attached_poster_bytes")
            attached_img_name = st.session_state.get(
                "attached_poster_name", "job_poster.png"
            )
            attached_img_mime = st.session_state.get(
                "attached_poster_mime", "image/png"
            )

            with st.expander(
                "🖼️ รูปภาพประกาศงาน / โปสเตอร์ (แนบขึ้น Notion เป็นรูปหน้าปกและการ์ด)",
                expanded=bool(attached_img_bytes),
            ):
                if attached_img_bytes:
                    st.success(f"✅ มีภาพโปสเตอร์แนบอยู่: **{attached_img_name}**")
                    p_col1, p_col2 = st.columns([3, 1])
                    with p_col1:
                        st.image(
                            attached_img_bytes,
                            caption=f"ภาพที่จะส่งเข้า Notion: {attached_img_name}",
                            width=250,
                        )
                    with p_col2:
                        if st.button("❌ ลบภาพนี้ออก", key="btn_remove_poster_save"):
                            st.session_state.pop("attached_poster_bytes", None)
                            st.session_state.pop("attached_poster_name", None)
                            st.session_state.pop("attached_poster_mime", None)
                            st.rerun()
                else:
                    st.caption(
                        "หากมีรูปภาพประกาศงานจาก Facebook, LINE หรือ Screenshot สามารถแนบที่นี่เพื่อส่งขึ้น Notion ได้ครับ"
                    )
                    extra_poster = st.file_uploader(
                        "แนบรูปภาพโปสเตอร์ (PNG, JPG, WEBP)",
                        type=["png", "jpg", "jpeg", "webp"],
                        key="uploader_save_email_extra_poster",
                    )
                    if extra_poster:
                        attached_img_bytes = extra_poster.getvalue()
                        attached_img_name = extra_poster.name
                        attached_img_mime = extra_poster.type or "image/png"
                        st.session_state["attached_poster_bytes"] = attached_img_bytes
                        st.session_state["attached_poster_name"] = attached_img_name
                        st.session_state["attached_poster_mime"] = attached_img_mime
                        st.image(
                            attached_img_bytes,
                            caption="ตัวอย่างภาพที่จะส่งเข้า Notion",
                            width=250,
                        )

            sync_sqlite_too = st.checkbox(
                "💾 บันทึกสำเนาลง Application Tracker ในเครื่อง (SQLite) ด้วยพร้อมกัน",
                value=True,
                key="sync_sqlite_when_notion",
                help="เปิดไว้เพื่อให้มีข้อมูลทั้งในตาราง Notion และในระบบค้นหาบนเว็บไซต์นี้",
            )

            btn_notion_col, btn_local_col = st.columns(2)

            with btn_notion_col:
                notion_btn = st.button(
                    "🚀 ส่งเข้า Notion ทันที (Direct Notion Sync)",
                    type="primary",
                    use_container_width=True,
                    key="send_to_notion_btn",
                )

            with btn_local_col:
                local_btn = st.button(
                    "💾 บันทึกลง Tracker ในเครื่องเท่านั้น",
                    use_container_width=True,
                    key="save_to_tracker_btn",
                )

            # 1. ส่งตรงเข้า Notion
            if notion_btn:
                if not is_notion_configured():
                    st.warning(
                        "⚠️ ยังไม่ได้ตั้งค่า Notion Token หรือ Database ID โปรดเปิดกล่อง '⚙️ ตั้งค่าและเชื่อมต่อ Notion Database' ด้านบนเพื่อกรอกข้อมูลก่อนครับ"
                    )
                else:
                    with st.spinner(
                        "🚀 กำลังส่งข้อมูลตำแหน่งงาน ภาพโปสเตอร์ และเนื้อหาอีเมลตรงเข้าสู่ Notion Database..."
                    ):
                        notion_res = create_notion_job_page(
                            company=last_result["company"],
                            role=last_result["role"],
                            status=tracker_status,
                            applied_date=str(applied_date_val),
                            follow_up_date=str(follow_up_date_val),
                            location=save_location.strip(),
                            salary=save_salary.strip(),
                            job_url=st.session_state.get("attached_job_url", ""),
                            email_subject=custom_subject.strip(),
                            email_content=result_text.strip(),
                            notes=f"ส่งตรงจาก AI Email Generator ({last_result['type']})",
                            image_bytes=attached_img_bytes,
                            image_name=attached_img_name,
                            image_mime=attached_img_mime,
                        )

                        if notion_res["success"]:
                            st.success(f"🎉 {notion_res['message']}")
                            st.markdown(
                                f"🔗 [👉 คลิกที่นี่เพื่อเปิดดูการ์ดงานนี้ใน Notion ทันที]({notion_res['url']})"
                            )

                            if sync_sqlite_too:
                                try:
                                    new_id = add_application(
                                        company=last_result["company"],
                                        role=last_result["role"],
                                        location=save_location.strip(),
                                        salary=save_salary.strip(),
                                        job_url=st.session_state.get(
                                            "attached_job_url", ""
                                        ),
                                        status=tracker_status,
                                        applied_date=str(applied_date_val),
                                        follow_up_date=str(follow_up_date_val),
                                        email_subject=custom_subject.strip(),
                                        email_content=result_text.strip(),
                                        notes=f"บันทึกอัตโนมัติพร้อมส่ง Notion ({last_result['type']})",
                                        image_url=notion_res.get("image_url", ""),
                                    )
                                    st.info(
                                        f"💾 บันทึกสำเนาลง Application Tracker ในเครื่องเรียบร้อยแล้วด้วย (ID: #{new_id})"
                                    )
                                except Exception as e_sql:  # noqa: BLE001 — non-critical local SQLite backup
                                    logger.warning(
                                        f"Failed to auto-save to local sqlite: {e_sql}"
                                    )
                        else:
                            st.error(f"❌ {notion_res['message']}")

            # 2. บันทึกลง SQLite ภายในเครื่อง
            if local_btn:
                try:
                    new_id = add_application(
                        company=last_result["company"],
                        role=last_result["role"],
                        location=save_location.strip(),
                        salary=save_salary.strip(),
                        job_url=st.session_state.get("attached_job_url", ""),
                        status=tracker_status,
                        applied_date=str(applied_date_val),
                        follow_up_date=str(follow_up_date_val),
                        email_subject=custom_subject.strip(),
                        email_content=result_text.strip(),
                        notes=f"บันทึกอัตโนมัติจากโมดูล AI Email Generator ({last_result['type']})",
                        image_url="",
                    )
                    st.session_state["email_saved_to_tracker_msg"] = (
                        f"✅ บันทึกตำแหน่ง **{last_result['role']}** ที่ **{last_result['company']}** "
                        f"ลงใน Application Tracker สำเร็จแล้ว! (ID: #{new_id}) "
                        f"กำหนดวันติดตามผล: {follow_up_date_val}"
                    )
                except Exception as e:  # noqa: BLE001 — show DB error in UI
                    st.error(f"ไม่สามารถบันทึกลงฐานข้อมูลได้: {e}")

            if st.session_state.get("email_saved_to_tracker_msg"):
                st.success(st.session_state["email_saved_to_tracker_msg"])
                if st.button(
                    "👉 ไปที่ Application Tracker ทันที", key="jump_to_tracker_btn"
                ):
                    st.session_state.pop("email_saved_to_tracker_msg", None)
                    st.session_state["nav_selection"] = "📋 ติดตามการสมัครงาน"
                    st.rerun()

            # ปุ่มดาวน์โหลดข้อความเป็นไฟล์
            st.markdown("#### 📥 ดาวน์โหลดเนื้อหา")
            dcol1, dcol2 = st.columns(2)
            with dcol1:
                st.download_button(
                    label="📄 ดาวน์โหลดเป็นไฟล์ข้อความ (.txt)",
                    data=result_text,
                    file_name=f"application_email_{last_result['company'].replace(' ', '_')}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with dcol2:
                st.download_button(
                    label="📝 ดาวน์โหลดเป็น Markdown (.md)",
                    data=result_text,
                    file_name=f"application_email_{last_result['company'].replace(' ', '_')}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

    with tab_history_guide:
        st.subheader("📚 แหล่งอ้างอิงและมาตรฐานการเขียนอีเมลสมัครงานระดับสากล")
        st.caption(
            "ระบบนี้ไม่ได้คิดรูปแบบขึ้นเองลอยๆ แต่อ้างอิงจากมาตรฐานของสถาบันสายอาชีพและแนวปฏิบัติของ HR ชั้นนำ 4 แหล่งหลัก:"
        )

        st.markdown(
            """
            ---
            ### 🏛️ 4 แหล่งอ้างอิงมาตรฐานที่ใช้ในโมดูลนี้:

            #### 1. Harvard Career Services — The 3-Paragraph Outreach Architecture
            * **หลักการ:** ฝ่ายบุคคล (HR) ได้รับใบสมัครวันละหลักร้อยฉบับ การเขียนเป็นเรียงความยาวพรืดจะถูกมองข้ามทันที Harvard จึงกำหนดโครงสร้าง **3 ย่อหน้ากระชับ (Hook - Proof - Close)**:
              * **ย่อหน้า 1 (Hook & Position):** บอกทันทีว่าสมัครตำแหน่งอะไร ทราบจากช่องทางไหน และทำไมโปรไฟล์ถึงแมปกับองค์กรนี้
              * **ย่อหน้า 2 (Proof of Competence):** 2-3 Bullet Points สรุปผลงานจริงที่มีตัวเลขชัดเจน (Metrics / ROI)
              * **ย่อหน้า 3 (Call-to-Action & Enclosures):** สรุปเอกสารแนบ (Resume / Portfolio) และเสนอความพร้อมในการพูดคุย 15 นาที

            #### 2. Google Recruitment Formula (Laszlo Bock — Ex-Google SVP of People Operations)
            * **หลักการ (XYZ Formula):** *"Accomplished [X], as measured by [Y], by doing [Z]"*
            * **ทำไมถึงสร้างความน่าเชื่อถือ:** แทนที่จะใช้คำชมตัวเองลอยๆ เช่น *"เป็นคนขยัน มีภาวะผู้นำ"* (ซึ่ง HR ไม่เชื่อ) ระบบจะบังคับให้เขียนแบบมีหลักฐาน เช่น *"เคยนำทีม 4 คน พัฒนาระบบ X ช่วยลดเวลาทำงานลง 25%"*

            #### 3. SHRM (Society for Human Resource Management) — The 7-Second Scan Rule
            * **งานวิจัยของ SHRM:** HR ใช้เวลาสแกนอีเมลครั้งแรกเฉลี่ยเพียง **6-8 วินาที** ก่อนตัดสินใจเปิดเรซูเม่
            * **ข้อกำหนด:** ความยาวรวมต้องอยู่ระหว่าง **120 - 180 คำ** ใช้หัวข้ออีเมลมาตรฐานที่ระบุ `[ตำแหน่ง] - [ชื่อผู้สมัคร] [เบอร์โทร / ประสบการณ์]`

            #### 4. Adecco Thailand & LinkedIn Talent Solutions — Anti-AI Cliché & Thai Corporate Etiquette
            * **ข้อห้ามเด็ดขาด (สิ่งที่ทำให้เมลดูปลอม/ไม่น่าเชื่อถือ):**
              * ❌ ห้ามใช้คำเยินยอเว่อร์ เช่น *"บริษัทอันทรงเกียรติ", "วิสัยทัศน์อันกว้างไกล", "ข้าพเจ้า", "I hope this email finds you well"*
              * ✅ ใช้ภาษาเขียนทางการระดับคนทำงานจริง (เช่น *"เรียน ฝ่ายทรัพยากรบุคคล...", "ขอแสดงความนับถือ"*)
            """
        )
