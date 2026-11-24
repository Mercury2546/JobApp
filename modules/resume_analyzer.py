"""
โมดูลที่ 1: วิเคราะห์และรีไรท์เรซูเม่ (Resume Analyzer & Full Rewriter)
วิเคราะห์เรซูเม่เทียบกับมาตรฐานระบบคัดกรอง ATS และคำอธิบายงาน (JD) ด้วย AI
พร้อมระบบรีไรท์และแก้ไขเรซูเม่ใหม่ทั้งฉบับแบบมืออาชีพ (Google XYZ Formula) และส่งออกไฟล์
"""

import streamlit as st

from config.settings import is_openai_configured
from database.db import get_db_connection
from services.ai_service import AIServiceError, ai_service
from utils.helpers import (
    format_date,
)
from utils.logger import setup_logger

logger = setup_logger("resume_analyzer")


# ==========================================
# ฟังก์ชันจัดการฐานข้อมูล SQLite (Database Operations)
# ==========================================


def save_resume_analysis(
    title: str,
    raw_text: str,
    file_name: str,
    analysis_summary: str,
    rewritten_text: str = "",
) -> int:
    """บันทึกผลการวิเคราะห์เรซูเม่ลงใน SQLite"""
    query = """
    INSERT INTO resumes (title, raw_text, file_name, analysis_summary, rewritten_text)
    VALUES (?, ?, ?, ?, ?);
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    title.strip(),
                    raw_text.strip(),
                    file_name.strip() if file_name else "ข้อความที่วาง (Pasted Text)",
                    analysis_summary.strip(),
                    rewritten_text.strip(),
                ),
            )
            new_id = cursor.lastrowid
            logger.info(f"บันทึกผลวิเคราะห์เรซูเม่ ID {new_id} ('{title}') เรียบร้อย")
            return new_id
    except Exception:
        logger.exception("ไม่สามารถบันทึกผลการวิเคราะห์เรซูเม่ได้")
        raise


def update_resume_rewritten_text(resume_id: int, rewritten_text: str) -> bool:
    """อัปเดตเนื้อหาเรซูเม่ที่ผ่านการรีไรท์ลงใน SQLite"""
    query = "UPDATE resumes SET rewritten_text = ? WHERE id = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (rewritten_text.strip(), resume_id))
            logger.info(f"อัปเดตเนื้อหารีไรท์ของเรซูเม่ ID {resume_id} เรียบร้อย")
            return cursor.rowcount > 0
    except Exception:
        logger.exception(f"ไม่สามารถอัปเดตเนื้อหารีไรท์ของเรซูเม่ ID {resume_id} ได้")
        raise


def get_all_resumes() -> list[dict]:
    """ดึงข้อมูลประวัติการวิเคราะห์เรซูเม่ทั้งหมดจาก SQLite"""
    query = "SELECT * FROM resumes ORDER BY created_at DESC;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("เกิดข้อผิดพลาดในการดึงข้อมูลเรซูเม่")
        return []


def delete_resume_analysis(resume_id: int) -> bool:
    """ลบข้อมูลประวัติการวิเคราะห์เรซูเม่ตาม ID"""
    query = "DELETE FROM resumes WHERE id = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (resume_id,))
            logger.info(f"ลบผลวิเคราะห์เรซูเม่ ID {resume_id} เรียบร้อย")
            return cursor.rowcount > 0
    except Exception:
        logger.exception(f"ไม่สามารถลบผลวิเคราะห์เรซูเม่ ID {resume_id} ได้")
        raise


# ==========================================
# ฟังก์ชันสกัดข้อความจากไฟล์ (Text Extraction)
# ==========================================


def extract_text_from_file(uploaded_file) -> str:
    """
    อ่านและสกัดข้อความจากไฟล์ .pdf, .txt, .md
    รองรับไฟล์ภาษาไทยและ UTF-8 อย่างสมบูรณ์
    """
    if uploaded_file is None:
        return ""

    file_name = uploaded_file.name.lower()

    # สกัดข้อความจากไฟล์ Text / Markdown
    if file_name.endswith((".txt", ".md")):
        try:
            return uploaded_file.read().decode("utf-8")
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            return uploaded_file.read().decode("latin-1", errors="ignore")

    # สกัดข้อความจากไฟล์ PDF โดยใช้ pypdf
    if file_name.endswith(".pdf"):
        try:
            import pypdf

            reader = pypdf.PdfReader(uploaded_file)
            pages_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            extracted = "\n\n".join(pages_text).strip()
            if not extracted:
                raise AIServiceError(
                    "ไม่สามารถสกัดข้อความจากไฟล์ PDF ได้ (ไฟล์อาจเป็นภาพสแกนหรือติดการเข้ารหัส) "
                    "โปรดลองคัดลอกข้อความมาวางในช่องข้อความแทน"
                )
            return extracted
        except ImportError:
            raise AIServiceError("ไลบรารี 'pypdf' ยังไม่ได้ติดตั้ง กรุณาติดตั้งผ่าน pip")
        except Exception as e:  # noqa: BLE001 — wrap unexpected PDF parser error
            logger.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ PDF: {e}")
            raise AIServiceError(f"ไม่สามารถอ่านไฟล์ PDF ได้: {e}")

    raise AIServiceError("ไม่รองรับนามสกุลไฟล์นี้ (รองรับเฉพาะ .pdf, .txt, .md)")


# ==========================================
# ตรรกะการวิเคราะห์และรีไรท์ด้วย AI
# ==========================================


def analyze_resume_with_ai(resume_text: str, job_description: str = "") -> str:
    """
    ส่งข้อความเรซูเม่ให้ AI วิเคราะห์คะแนน ATS และจุดแข็ง-จุดอ่อนแบบเจาะลึก
    """
    if not resume_text.strip():
        raise ValueError("เนื้อหาของเรซูเม่ต้องไม่ว่างเปล่า")

    system_prompt = (
        "คุณคือผู้เชี่ยวชาญด้านการพัฒนาสายอาชีพระดับผู้บริหาร (Executive Career Coach) "
        "และผู้เชี่ยวชาญด้านระบบคัดกรองเรซูเม่อัตโนมัติ (ATS - Applicant Tracking System)\n"
        "หน้าที่ของคุณคือวิเคราะห์เรซูเม่อย่างตรงไปตรงมา ลึกซึ้ง และให้คำแนะนำที่นำไปปฏิบัติได้จริงทันที\n\n"
        "จงตอบกลับเป็นภาษาไทยที่สละสลวย ชัดเจน และเป็นมืออาชีพ โดยใช้โครงสร้าง Markdown ดังนี้:\n"
        "### 1. 📊 คะแนนความพร้อมและระบบ ATS (Estimated ATS Score)\n"
        "- ประเมินคะแนนความเข้ากันได้ตั้งแต่ 0 ถึง 100 คะแนน พร้อมเหตุผลประกอบสั้นๆ 2-3 บรรทัด\n\n"
        "### 2. ⭐ จุดเด่นและจุดแข็งหลัก (Key Strengths)\n"
        "- ระบุจุดแข็ง 3-4 ข้อที่โดดเด่น เช่น ประสบการณ์เฉพาะทาง ผลลัพธ์เชิงตัวเลข หรือโครงสร้างที่ดี\n\n"
        "### 3. ⚠️ จุดอ่อนและสัญญาณเตือนที่ควรแก้ไข (Areas for Improvement)\n"
        "- ข้อความที่คลุมเครือ, ขาดการวัดผลเชิงปริมาณ, คำกริยาที่อ่อนเกินไป, หรือจุดที่ระบบ ATS อาจอ่านตกหล่น\n\n"
        "### 4. 🔑 การวิเคราะห์คีย์เวิร์ดและทักษะที่ขาดหาย (Keyword & Skill Gap)\n"
        "- ทักษะสำคัญที่พบ และทักษะสำคัญที่ขาดหายไป (โดยเฉพาะเมื่อเทียบกับ Job Description หากมี)\n\n"
        "### 5. ✍️ ตัวอย่างการปรับแก้ข้อความผลงานจริง (Before & After Rewrites)\n"
        "- เลือก 2-3 บุลเล็ตจากเรซูเม่มาเขียนใหม่โดยใช้สูตร XYZ ของ Google: "
        "'สำเร็จผลงาน [X] วัดผลได้ด้วย [Y] โดยการลงมือทำ [Z]'\n"
    )

    jd_context = (
        f"\n\n--- ข้อมูลคำอธิบายตำแหน่งงานเป้าหมาย (Job Description) ---\n{job_description.strip()}"
        if job_description.strip()
        else "\n\n(ผู้ใช้ไม่ได้ระบุ Job Description เฉพาะเจาะจง ให้ประเมินเทียบกับมาตรฐานความเป็นเลิศในอุตสาหกรรมทั่วไป)"
    )

    user_prompt = f"--- ข้อมูลเรซูเม่ของผู้สมัคร ---\n{resume_text.strip()}{jd_context}"

    logger.info("กำลังส่งคำขอวิเคราะห์เรซูเม่ไปยัง AI Service...")
    return ai_service.generate_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.3,
    )


def rewrite_resume_with_ai(
    resume_text: str,
    job_description: str = "",
    target_language: str = "English",
    page_length: str = "1 หน้ากระดาษ",
    target_role: str = "",
) -> str:
    """
    รีไรท์และปรับปรุงเรซูเม่ทั้งฉบับใหม่ด้วย AI
    ยกระดับโครงสร้าง การใช้ Action Verbs, Google XYZ Formula, และสอดคล้องกับระบบ ATS 100%
    """
    if not resume_text.strip():
        raise ValueError("เนื้อหาของเรซูเม่ต้องไม่ว่างเปล่า")

    is_english = "English" in target_language

    if is_english:
        system_prompt = (
            "You are an elite, world-class Executive Resume Writer, Career Strategist, and ATS Optimization Specialist. "
            "Your objective is to rewrite the candidate's existing resume into a breathtaking, high-converting, ATS-compliant resume. "
            "Follow these strict principles:\n"
            "1. STRUCTURE: Standard, clean reverse-chronological format (Header, Professional Summary, Core Competencies/Technical Skills, Work Experience, Education, Projects/Certifications).\n"
            "2. BULLET POINTS: Transform all weak, passive job descriptions into high-impact accomplishment statements using Google's XYZ Formula ('Accomplished [X] measured by [Y], by doing [Z]').\n"
            "3. ACTION VERBS: Start every bullet point with strong, diverse action verbs (e.g., Spearheaded, Engineered, Accelerated, Overhauled, Orchestrated, Optimized).\n"
            "4. METRICS & IMPACT: Preserve or enhance realistic quantitative metrics (percentages, revenues, team sizes, efficiencies).\n"
            "5. ATS KEYWORDS: Seamlessly weave in relevant keywords from the target Job Description (if provided) without keyword stuffing.\n"
            "6. TRUTHFUL INTEGRITY: Elevate wording and professional stature while strictly preserving the candidate's authentic career facts, dates, and companies."
        )
    else:
        system_prompt = (
            "คุณคือนักเขียนเรซูเม่อาชีพและที่ปรึกษาสายอาชีพระดับสูง (Senior Career Strategist & Executive Resume Writer) "
            "มีความเชี่ยวชาญสูงสุดในการปรับปรุงและรีไรท์เรซูเม่ภาษาไทยให้สละสลวย เป็นทางการ โดดเด่น และผ่านระบบคัดกรอง ATS 100%\n"
            "หลักการรีไรท์ที่ต้องยึดถือ:\n"
            "1. โครงสร้างมาตรฐานสากล: ข้อมูลติดต่อ, บทสรุปโปรไฟล์ (Professional Summary), ทักษะความเชี่ยวชาญ (Core Competencies), ประสบการณ์การทำงาน, ประวัติการศึกษา, และผลงาน/ใบรับรอง\n"
            "2. การเขียนผลงาน: ปรับทุกบุลเล็ตให้อิงผลลัพธ์และความสำเร็จตามสูตร XYZ ('บรรลุผลงาน [X] วัดผลได้ด้วย [Y] โดยลงมือทำ [Z]')\n"
            "3. คำกริยาทรงพลัง: ใช้คำกริยาแสดงการลงมือทำจริง เช่น พัฒนา, บริหารจัดการ, ยกระดับ, เพิ่มประสิทธิภาพ, ออกแบบโครงสร้าง\n"
            "4. การสอดแทรกคีย์เวิร์ด: นำคำสำคัญจาก Job Description มาแทรกในจุดที่เกี่ยวข้องอย่างเป็นธรรมชาติ\n"
            "5. ยึดข้อเท็จจริงเดิมของผู้สมัคร แต่ยกระดับการนำเสนอให้น่าประทับใจที่สุด"
        )

    user_prompt = f"""
กรุณารีไรท์และเรียบเรียงเรซูเม่ใหม่ทั้งฉบับอย่างสมบูรณ์แบบตามข้อมูลด้านล่างนี้:

🌐 **ภาษาเป้าหมาย:** {target_language}
📄 **ความยาวเป้าหมาย:** {page_length}
💼 **ตำแหน่งเป้าหมาย (Target Role):** {target_role if target_role.strip() else "ตามสายงานเดิมในเรซูเม่"}

---
### 📄 เนื้อหาเรซูเม่ต้นฉบับของผู้สมัคร:
{resume_text.strip()}
---

### 🎯 คำอธิบายงานเป้าหมาย (Job Description) ที่ต้องการนำมาปรับจูน:
{job_description.strip() if job_description.strip() else "(ไม่ได้ระบุ JD ให้ปรับปรุงตามมาตรฐานสูงสุดของสายอาชีพนี้)"}

---
กรุณาส่งมอบผลลัพธ์เป็น **เรซูเม่ฉบับสมบูรณ์ (Complete Polished Resume)** ในรูปแบบ Markdown ที่พร้อมคัดลอกไปใช้งานได้ทันที มีการจัดหมวดหมู่ชัดเจน สวยงาม อ่านง่าย และเป็นมืออาชีพสูงสุด
"""

    return ai_service.generate_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.35,
    )


# ==========================================
# หน้าจอแสดงผล (Streamlit UI Views)
# ==========================================


def render_new_analysis_view():
    """หน้าจอวิเคราะห์เรซูเม่ใหม่"""
    st.subheader("🔍 วิเคราะห์และตรวจคะแนน ATS เรซูเม่")
    st.write(
        "อัปโหลดไฟล์เรซูเม่ของคุณ (รองรับไฟล์ PDF โดยตรง) หรือคัดลอกข้อความมาวาง เพื่อรับการตรวจคะแนน ATS และคำแนะนำปรับปรุงเรซูเม่"
    )

    if not is_openai_configured():
        st.warning(
            "⚠️ **ยังไม่ได้ตั้งค่า OpenAI API Key ในไฟล์ `.env`**\n\n"
            "ระบบจำเป็นต้องใช้ OpenAI API Key ในการวิเคราะห์ โปรดใส่ `OPENAI_API_KEY` ของคุณในไฟล์ `.env` ก่อนกดวิเคราะห์"
        )

    col_title, col_file = st.columns([1, 1])
    with col_title:
        title = st.text_input(
            "ชื่อชุดเรซูเม่ (สำหรับบันทึก) *",
            placeholder="เช่น เรซูเม่ตำแหน่ง Senior Developer 2026",
            value="เรซูเม่ของฉัน",
        )
    with col_file:
        uploaded_file = st.file_uploader(
            "📂 อัปโหลดไฟล์เรซูเม่ (.pdf, .txt, .md)",
            type=["pdf", "txt", "md"],
            key="uploader_analysis_pdf",
        )

    # จัดการสกัดข้อความจากไฟล์
    extracted_text = ""
    file_name = ""
    if uploaded_file is not None:
        file_name = uploaded_file.name
        try:
            extracted_text = extract_text_from_file(uploaded_file)
            st.success(
                f"✅ โหลดไฟล์ '{file_name}' สำเร็จ (อ่านได้ {len(extracted_text):,} ตัวอักษร)"
            )
        except Exception as e:  # noqa: BLE001 — show file extraction error in UI
            st.error(f"❌ {e}")

    # ช่องกรอกหรือแก้ไขเนื้อหาเรซูเม่
    resume_input = st.text_area(
        "เนื้อหาเรซูเม่ (ตรวจสอบหรือวางข้อความที่นี่) *",
        value=extracted_text,
        height=220,
        placeholder="ข้อความจากเรซูเม่ของคุณจะปรากฏที่นี่หลังอัปโหลด หรือสามารถวางข้อความได้โดยตรง...",
        key="analysis_resume_text_area",
    )

    with st.expander(
        "🎯 คำอธิบายตำแหน่งงานเป้าหมาย (Job Description) — แนะนำให้ใส่", expanded=False
    ):
        job_description = st.text_area(
            "คัดลอกประกาศรับสมัครงานมาวางที่นี่",
            height=130,
            placeholder="วางคุณสมบัติและหน้าที่ความรับผิดชอบของงานเป้าหมาย เพื่อให้ AI ตรวจสอบคีย์เวิร์ดที่ตรงกัน...",
            key="analysis_jd_text_area",
        )

    # ปุ่มสั่งการวิเคราะห์
    if st.button(
        "🚀 เริ่มวิเคราะห์เรซูเม่ด้วย AI",
        type="primary",
        use_container_width=True,
        key="btn_run_resume_analysis",
    ):
        final_text = resume_input.strip() or extracted_text.strip()
        if not final_text:
            st.error("กรุณาระบุเนื้อหาเรซูเม่ โดยการอัปโหลดไฟล์หรือวางข้อความ")
        elif not title.strip():
            st.error("กรุณาระบุชื่อเรซูเม่สำหรับบันทึก")
        else:
            with st.spinner("AI กำลังอ่านและประเมินเรซูเม่ตามเกณฑ์ ATS..."):
                try:
                    analysis_result = analyze_resume_with_ai(
                        final_text, job_description
                    )
                    st.session_state["latest_analysis"] = {
                        "title": title,
                        "raw_text": final_text,
                        "file_name": file_name,
                        "result": analysis_result,
                        "job_description": job_description,
                    }
                    st.session_state["shared_resume_text"] = final_text
                    if job_description.strip():
                        st.session_state["shared_jd_text"] = job_description.strip()
                    # บันทึกลงฐานข้อมูล SQLite
                    new_id = save_resume_analysis(
                        title=title,
                        raw_text=final_text,
                        file_name=file_name,
                        analysis_summary=analysis_result,
                    )
                    st.session_state["latest_analysis"]["id"] = new_id
                    st.success("🎉 วิเคราะห์เสร็จสิ้นและบันทึกลงฐานข้อมูลเรียบร้อยแล้ว!")
                except AIServiceError as e:
                    st.error(f"เกิดข้อผิดพลาดจาก AI Service: {e}")
                except Exception as e:
                    logger.exception("เกิดข้อผิดพลาดในการวิเคราะห์เรซูเม่")
                    st.error(f"เกิดข้อผิดพลาดไม่คาดคิด: {e}")

    # แสดงผลการวิเคราะห์ล่าสุด
    if "latest_analysis" in st.session_state:
        latest = st.session_state["latest_analysis"]
        st.divider()
        st.subheader(f"📑 รายงานผลการประเมิน: {latest['title']}")
        st.markdown(latest["result"])

        st.markdown("---")
        with st.container(border=True):
            st.markdown("### ✨ รีไรท์และแก้ไขเรซูเม่ฉบับสมบูรณ์ทันที (Full Resume Rewriter)")
            st.write(
                "ต้องการให้ AI นำผลวิเคราะห์และข้อความเรซูเม่นี้ไปรีไรท์แก้ไขเป็นเรซูเม่ฉบับสมบูรณ์ใหม่เลยหรือไม่?"
            )

            col_q_lang, col_q_len, col_q_btn = st.columns([2, 2, 2])
            with col_q_lang:
                quick_lang = st.selectbox(
                    "ภาษาเป้าหมาย",
                    [
                        "🇬🇧 English (Business Professional - แนะนำ)",
                        "🇹🇭 ภาษาไทย (ทางการ สละสลวย)",
                    ],
                    key="bridge_quick_lang",
                )
            with col_q_len:
                quick_len = st.selectbox(
                    "ความยาว",
                    [
                        "1 หน้ากระดาษ (กระชับ เจาะจง)",
                        "2 หน้ากระดาษ (ละเอียด ครบถ้วน)",
                    ],
                    key="bridge_quick_len",
                )
            with col_q_btn:
                st.write("")
                st.write("")
                if st.button(
                    "✨ รีไรท์เรซูเม่ฉบับใหม่ทันที",
                    type="primary",
                    use_container_width=True,
                    key="btn_bridge_to_rewrite",
                ):
                    st.session_state["rewrite_resume_source"] = latest["raw_text"]
                    st.session_state["rewrite_jd_source"] = latest.get(
                        "job_description", ""
                    )
                    st.session_state["rewrite_resume_title"] = latest["title"]
                    st.session_state["auto_run_rewrite_config"] = {
                        "lang": quick_lang,
                        "length": quick_len,
                    }
                    st.session_state["resume_active_tab"] = "✨ รีไรท์เรซูเม่ใหม่ทั้งฉบับ"
                    st.rerun()


def render_full_rewrite_view():
    """หน้าจอดำเนินการรีไรท์เรซูเม่ฉบับสมบูรณ์"""
    st.subheader("✨ ปรับปรุงและรีไรท์เรซูเม่ฉบับใหม่ (Full Resume Rewriter)")
    st.write(
        "ให้ AI เขียนแก้ไขเรซูเม่ของคุณใหม่ทั้งฉบับ ยกระดับการใช้ Action Verbs, โครงสร้าง Google XYZ Formula, และสอดคล้องกับมาตรฐาน ATS สากล"
    )

    # ตรวจสอบว่ามีการสั่ง Auto-run จากปุ่มหน้าแรกมาหรือไม่
    auto_config = st.session_state.pop("auto_run_rewrite_config", None)
    if auto_config:
        resume_source_text = st.session_state.get("rewrite_resume_source", "")
        rewrite_jd = st.session_state.get("rewrite_jd_source", "")
        with st.spinner(
            "🤖 AI กำลังยกระดับผลงาน สอดแทรกสูตร XYZ และจัดโครงสร้างเรซูเม่ฉบับใหม่..."
        ):
            try:
                rewritten_content = rewrite_resume_with_ai(
                    resume_text=resume_source_text,
                    job_description=rewrite_jd,
                    target_language=auto_config["lang"],
                    page_length=auto_config["length"],
                    target_role="",
                )
                st.session_state["latest_rewritten_resume"] = {
                    "content": rewritten_content,
                    "lang": auto_config["lang"],
                    "role": "",
                }
                st.session_state["shared_resume_text"] = rewritten_content
                st.success("🎉 รีไรท์เรซูเม่ฉบับสมบูรณ์เรียบร้อยแล้ว!")
            except AIServiceError as e:
                st.error(f"เกิดข้อผิดพลาดจาก AI: {e}")
            except Exception as e:
                logger.exception("เกิดข้อผิดพลาดในการรีไรท์เรซูเม่")
                st.error(f"เกิดข้อผิดพลาด: {e}")

    # แหล่งที่มาของเรซูเม่ต้นฉบับ
    saved_resumes = get_all_resumes()
    source_options = ["(พิมพ์หรือวางข้อความเรซูเม่เอง)"]
    if "rewrite_resume_source" in st.session_state:
        source_options.insert(0, "✨ ใช้เรซูเม่ล่าสุดที่เพิ่งวิเคราะห์")
    if saved_resumes:
        source_options.extend(
            [f"#{r['id']} {r['title']} ({r['file_name']})" for r in saved_resumes]
        )

    chosen_source = st.selectbox("📂 เลือกแหล่งที่มาของเรซูเม่ต้นฉบับ", source_options, index=0)

    prefilled_resume_text = ""
    if chosen_source == "✨ ใช้เรซูเม่ล่าสุดที่เพิ่งวิเคราะห์":
        prefilled_resume_text = st.session_state.get("rewrite_resume_source", "")
    elif chosen_source != "(พิมพ์หรือวางข้อความเรซูเม่เอง)":
        for r in saved_resumes:
            if chosen_source.startswith(f"#{r['id']} "):
                prefilled_resume_text = r.get("raw_text", "")
                break

    col_res_text, col_res_opt = st.columns([3, 2])

    with col_res_text:
        resume_source_text = st.text_area(
            "ข้อความเรซูเม่ต้นฉบับที่จะให้รีไรท์ *",
            value=prefilled_resume_text,
            height=250,
            placeholder="วางเนื้อหาเรซูเม่ปัจจุบันของคุณที่นี่...",
            key="rewrite_input_source_text",
        )

    with col_res_opt, st.container(border=True):
        st.markdown("#### ⚙️ ตัวเลือกการรีไรท์")
        rewrite_lang = st.selectbox(
            "🌐 ภาษาเป้าหมาย",
            [
                "🇬🇧 English (Business Professional - แนะนำสำหรับงานสากล)",
                "🇹🇭 ภาษาไทย (ทางการ สละสลวย เป็นมืออาชีพ)",
            ],
            index=0,
        )
        rewrite_length = st.selectbox(
            "📄 ความยาวที่ต้องการ",
            [
                "1 หน้ากระดาษ (กระชับ เจาะจง เหมาะสำหรับประสบการณ์ 1-7 ปี)",
                "2 หน้ากระดาษ (ละเอียด ครบถ้วน เหมาะสำหรับ Senior / Lead)",
            ],
            index=0,
        )
        target_role = st.text_input(
            "💼 ตำแหน่งงานเป้าหมาย (Target Role)",
            placeholder="เช่น Senior Python Engineer, Product Manager",
        )

    # ส่วน Job Description สำหรับนำมาปรับจูนคีย์เวิร์ด
    with st.expander(
        "🎯 ปรับจูนคีย์เวิร์ดให้ตรงกับ Job Description เป้าหมาย (แนะนำ)", expanded=False
    ):
        jd_default_source = st.session_state.get("rewrite_jd_source", "")
        rewrite_jd = st.text_area(
            "วางรายละเอียดประกาศงาน (Job Description) ที่ต้องการสมัคร",
            value=jd_default_source,
            height=130,
            placeholder="AI จะดึงคำศัพท์ Hard Skills และ Requirement สำคัญจาก JD นี้มาแทรกในเรซูเม่ให้โดยอัตโนมัติ...",
            key="rewrite_input_jd_text",
        )

    rewrite_btn = st.button(
        "🚀 สั่งให้ AI รีไรท์เรซูเม่ทั้งฉบับทันที (Generate Full Resume)",
        type="primary",
        use_container_width=True,
    )

    if rewrite_btn:
        if not resume_source_text.strip():
            st.error("กรุณาระบุเนื้อหาเรซูเม่ต้นฉบับก่อนกดเริ่มรีไรท์")
        else:
            with st.spinner(
                "🤖 AI กำลังยกระดับผลงาน สอดแทรกสูตร XYZ และจัดโครงสร้างเรซูเม่ฉบับใหม่..."
            ):
                try:
                    rewritten_content = rewrite_resume_with_ai(
                        resume_text=resume_source_text,
                        job_description=rewrite_jd,
                        target_language=rewrite_lang,
                        page_length=rewrite_length,
                        target_role=target_role,
                    )
                    st.session_state["latest_rewritten_resume"] = {
                        "content": rewritten_content,
                        "lang": rewrite_lang,
                        "role": target_role,
                    }
                    st.session_state["shared_resume_text"] = rewritten_content
                    if target_role.strip():
                        st.session_state["shared_role"] = target_role.strip()
                    st.success("🎉 รีไรท์เรซูเม่ฉบับสมบูรณ์เรียบร้อยแล้ว!")
                except AIServiceError as e:
                    st.error(f"เกิดข้อผิดพลาดจาก AI: {e}")
                except Exception as e:
                    logger.exception("เกิดข้อผิดพลาดในการรีไรท์เรซูเม่")
                    st.error(f"เกิดข้อผิดพลาด: {e}")

    # แสดงผลลัพธ์เรซูเม่ที่รีไรท์แล้ว
    rewritten_obj = st.session_state.get("latest_rewritten_resume")
    if rewritten_obj:
        st.divider()
        st.subheader("📑 เรซูเม่ฉบับปรับปรุงใหม่ (Polished ATS Resume)")

        tab_preview, tab_raw = st.tabs(
            [
                "👁️ มุมมองจัดหน้า (Markdown Preview)",
                "✏️ มุมมองข้อความดิบ (แก้ไขได้)",
            ]
        )

        with tab_preview:
            st.markdown(rewritten_obj["content"])

        with tab_raw:
            st.text_area(
                "ข้อความเรซูเม่ (สามารถคัดลอกหรือแก้ไขเพิ่มเติมได้)",
                value=rewritten_obj["content"],
                height=350,
                key="rewritten_editable_text_area",
            )

        current_content = st.session_state.get(
            "rewritten_editable_text_area", rewritten_obj["content"]
        )

        st.markdown("#### 📥 นำไปใช้งาน")
        dcol1, dcol2, dcol3 = st.columns(3)
        with dcol1:
            st.download_button(
                label="📄 ดาวน์โหลดเป็น Markdown (.md)",
                data=current_content,
                file_name="polished_resume.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dcol2:
            st.download_button(
                label="📝 ดาวน์โหลดเป็น Text (.txt)",
                data=current_content,
                file_name="polished_resume.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with dcol3:
            if st.button("💾 บันทึกลงในระบบเรซูเม่", use_container_width=True):
                save_title = f"เรซูเม่รีไรท์ ({rewritten_obj['role'] or 'ฉบับปรับปรุง'})"
                save_resume_analysis(
                    title=save_title,
                    raw_text=resume_source_text,
                    file_name="AI_Rewritten_Resume",
                    analysis_summary="เรซูเม่ฉบับรีไรท์ปรับปรุงใหม่",
                    rewritten_text=current_content,
                )
                st.success(f"บันทึก '{save_title}' เข้าสู่ประวัติระบบเรียบร้อยแล้ว!")


def render_history_view():
    """หน้าจอแสดงประวัติเรซูเม่ที่เคยวิเคราะห์แล้ว"""
    st.subheader("📚 ประวัติผลการวิเคราะห์และเรซูเม่ที่บันทึกไว้")
    resumes = get_all_resumes()

    if not resumes:
        st.info(
            "ยังไม่มีประวัติการวิเคราะห์เรซูเม่ สามารถเริ่มวิเคราะห์ได้ที่แท็บ 'ตรวจคะแนน ATS & วิเคราะห์'"
        )
        return

    st.write(f"พบประวัติทั้งหมด **{len(resumes)}** ฉบับ")

    for item in resumes:
        created_display = (
            format_date(item["created_at"][:10]) if item["created_at"] else "ไม่ระบุวันที่"
        )
        has_rewrite = bool(item.get("rewritten_text"))
        badge = "✨ มีฉบับรีไรท์" if has_rewrite else ""
        with st.expander(
            f"📄 **{item['title']}** {badge} (บันทึกเมื่อ: {created_display})"
        ):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(
                    f"แหล่งที่มา: {item['file_name']} • เวลาที่บันทึก: {item['created_at']}"
                )
            with col2:
                if st.button("🗑️ ลบรายงานนี้", key=f"del_resume_{item['id']}"):
                    delete_resume_analysis(item["id"])
                    st.toast("🗑️ ลบรายงานเรียบร้อยแล้ว")
                    st.rerun()

            st.divider()

            if item.get("rewritten_text"):
                st.markdown("### ✨ เรซูเม่ฉบับรีไรท์ที่บันทึกไว้:")
                st.markdown(item["rewritten_text"])
                st.download_button(
                    label="📥 ดาวน์โหลดเรซูเม่ฉบับรีไรท์นี้ (.md)",
                    data=item["rewritten_text"],
                    file_name=f"resume_{item['title']}.md",
                    key=f"dl_rewrite_{item['id']}",
                )
                st.divider()

            st.markdown("### 📊 รายงานผลการประเมิน ATS:")
            st.markdown(item["analysis_summary"])


def render():
    """
    จุดเริ่มต้นการแสดงผลของโมดูล Resume Analyzer & Full Rewriter
    """
    st.header("📄 วิเคราะห์และรีไรท์เรซูเม่ (Resume Analyzer & Full Rewriter)")
    st.caption("ระบบตรวจประเมินคะแนน ATS สกัดทักษะ และเขียนแก้ไขเรซูเม่ฉบับใหม่ทั้งฉบับด้วย AI")

    tab_titles = [
        "🔍 ตรวจคะแนน ATS & วิเคราะห์",
        "✨ รีไรท์เรซูเม่ใหม่ทั้งฉบับ",
        "📚 ประวัติเรซูเม่",
    ]

    current_tab = st.session_state.get("resume_active_tab", tab_titles[0])
    if current_tab not in tab_titles:
        current_tab = tab_titles[0]

    selected_tab = st.radio(
        "เลือกโหมดการทำงาน",
        tab_titles,
        index=tab_titles.index(current_tab),
        horizontal=True,
        label_visibility="collapsed",
        key="resume_tab_radio_nav",
    )
    # อัปเดต state ให้ตรงกัน
    st.session_state["resume_active_tab"] = selected_tab

    if selected_tab == tab_titles[0]:
        render_new_analysis_view()
    elif selected_tab == tab_titles[1]:
        render_full_rewrite_view()
    elif selected_tab == tab_titles[2]:
        render_history_view()
