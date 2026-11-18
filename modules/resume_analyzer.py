"""
โมดูลที่ 1: วิเคราะห์เรซูเม่ (Resume Analyzer)
วิเคราะห์เรซูเม่เทียบกับมาตรฐานระบบคัดกรอง ATS และคำอธิบายตำแหน่งงาน (Job Description) ด้วย OpenAI
รองรับการอ่านไฟล์ .pdf โดยตรงผ่าน pypdf พร้อมแสดงผลวิเคราะห์เป็นภาษาไทยอย่างละเอียด
"""
from typing import Dict, List, Optional
import streamlit as st
from config.settings import is_openai_configured
from database.db import get_db_connection
from services.ai_service import AIServiceError, ai_service
from utils.helpers import format_date, truncate_text
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
) -> int:
    """บันทึกผลการวิเคราะห์เรซูเม่ลงใน SQLite"""
    query = """
    INSERT INTO resumes (title, raw_text, file_name, analysis_summary)
    VALUES (?, ?, ?, ?);
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
                ),
            )
            new_id = cursor.lastrowid
            logger.info(f"บันทึกผลวิเคราะห์เรซูเม่ ID {new_id} ('{title}') เรียบร้อย")
            return new_id
    except Exception as e:
        logger.error(f"ไม่สามารถบันทึกผลการวิเคราะห์เรซูเม่ได้: {e}", exc_info=True)
        raise


def get_all_resumes() -> List[Dict]:
    """ดึงข้อมูลประวัติการวิเคราะห์เรซูเม่ทั้งหมดจาก SQLite"""
    query = "SELECT * FROM resumes ORDER BY created_at DESC;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลเรซูเม่: {e}", exc_info=True)
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
    except Exception as e:
        logger.error(f"ไม่สามารถลบผลวิเคราะห์เรซูเม่ ID {resume_id} ได้: {e}", exc_info=True)
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
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ PDF: {e}")
            raise AIServiceError(f"ไม่สามารถอ่านไฟล์ PDF ได้: {e}")

    raise AIServiceError("ไม่รองรับนามสกุลไฟล์นี้ (รองรับเฉพาะ .pdf, .txt, .md)")


# ==========================================
# ตรรกะการวิเคราะห์ด้วย AI (AI Analysis Logic)
# ==========================================

def analyze_resume_with_ai(resume_text: str, job_description: str = "") -> str:
    """
    ส่งข้อความเรซูเม่ให้ OpenAI วิเคราะห์แบบเจาะลึก
    ตอบกลับเป็นภาษาไทยที่กระชับ ตรงจุด และจัดหมวดหมู่อย่างมืออาชีพ
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

    logger.info("กำลังส่งคำขอวิเคราะห์เรซูเม่ไปยัง OpenAI...")
    return ai_service.generate_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.3,
    )


# ==========================================
# หน้าจอแสดงผล (Streamlit UI Views)
# ==========================================

def render_new_analysis_view():
    """หน้าจอวิเคราะห์เรซูเม่ใหม่"""
    st.subheader("🔍 วิเคราะห์และประเมินเรซูเม่ใหม่")
    st.write("อัปโหลดไฟล์เรซูเม่ของคุณ (รองรับไฟล์ PDF โดยตรง) หรือคัดลอกข้อความมาวาง เพื่อรับการตรวจคะแนน ATS และคำแนะนำปรับปรุงเรซูเม่")

    if not is_openai_configured():
        st.warning(
            "⚠️ **ยังไม่ได้ตั้งค่า OpenAI API Key ในไฟล์ `.env`**\n\n"
            "ระบบจำเป็นต้องใช้ OpenAI API Key ในการวิเคราะห์ โปรดใส่ `OPENAI_API_KEY` ของคุณในไฟล์ `.env` ก่อนกดวิเคราะห์"
        )

    col_title, col_file = st.columns([1, 1])
    with col_title:
        title = st.text_input("ชื่อชุดเรซูเม่ (สำหรับบันทึก) *", placeholder="เช่น เรซูเม่ตำแหน่ง Senior Developer 2026", value="เรซูเม่ของฉัน")
    with col_file:
        uploaded_file = st.file_uploader("📂 อัปโหลดไฟล์เรซูเม่ (.pdf, .txt, .md)", type=["pdf", "txt", "md"])

    # จัดการสกัดข้อความจากไฟล์
    extracted_text = ""
    file_name = ""
    if uploaded_file is not None:
        file_name = uploaded_file.name
        try:
            extracted_text = extract_text_from_file(uploaded_file)
            st.success(f"✅ โหลดไฟล์ '{file_name}' สำเร็จ (อ่านได้ {len(extracted_text):,} ตัวอักษร)")
        except Exception as e:
            st.error(f"❌ {e}")

    # ช่องกรอกหรือแก้ไขเนื้อหาเรซูเม่
    resume_input = st.text_area(
        "เนื้อหาเรซูเม่ (ตรวจสอบหรือวางข้อความที่นี่) *",
        value=extracted_text,
        height=240,
        placeholder="ข้อความจากเรซูเม่ของคุณจะปรากฏที่นี่หลังอัปโหลด หรือสามารถวางข้อความได้โดยตรง...",
    )

    with st.expander("🎯 คำอธิบายตำแหน่งงานเป้าหมาย (Job Description) — แนะนำให้ใส่", expanded=False):
        job_description = st.text_area(
            "คัดลอกประกาศรับสมัครงานมาวางที่นี่",
            height=140,
            placeholder="วางคุณสมบัติและหน้าที่ความรับผิดชอบของงานเป้าหมาย เพื่อให้ AI ตรวจสอบคีย์เวิร์ดที่ตรงกัน...",
        )

    # ปุ่มสั่งการวิเคราะห์
    if st.button("🚀 เริ่มวิเคราะห์เรซูเม่ด้วย AI", type="primary", use_container_width=True):
        final_text = resume_input.strip() or extracted_text.strip()
        if not final_text:
            st.error("กรุณาระบุเนื้อหาเรซูเม่ โดยการอัปโหลดไฟล์หรือวางข้อความ")
        elif not title.strip():
            st.error("กรุณาระบุชื่อเรซูเม่สำหรับบันทึก")
        else:
            with st.spinner("AI กำลังอ่านและประเมินเรซูเม่ตามเกณฑ์ ATS..."):
                try:
                    analysis_result = analyze_resume_with_ai(final_text, job_description)
                    st.session_state["latest_analysis"] = {
                        "title": title,
                        "raw_text": final_text,
                        "file_name": file_name,
                        "result": analysis_result,
                    }
                    # บันทึกลงฐานข้อมูล SQLite
                    save_resume_analysis(
                        title=title,
                        raw_text=final_text,
                        file_name=file_name,
                        analysis_summary=analysis_result,
                    )
                    st.success("🎉 วิเคราะห์เสร็จสิ้นและบันทึกลงฐานข้อมูลเรียบร้อยแล้ว!")
                except AIServiceError as e:
                    st.error(f"เกิดข้อผิดพลาดจาก AI Service: {e}")
                except Exception as e:
                    logger.error(f"เกิดข้อผิดพลาดในการวิเคราะห์เรซูเม่: {e}", exc_info=True)
                    st.error(f"เกิดข้อผิดพลาดไม่คาดคิด: {e}")

    # แสดงผลการวิเคราะห์ล่าสุด
    if "latest_analysis" in st.session_state:
        latest = st.session_state["latest_analysis"]
        st.divider()
        st.subheader(f"📑 รายงานผลการประเมิน: {latest['title']}")
        st.markdown(latest["result"])


def render_history_view():
    """หน้าจอแสดงประวัติเรซูเม่ที่เคยวิเคราะห์แล้ว"""
    st.subheader("📚 ประวัติผลการวิเคราะห์เรซูเม่")
    resumes = get_all_resumes()

    if not resumes:
        st.info("ยังไม่มีประวัติการวิเคราะห์เรซูเม่ สามารถเริ่มวิเคราะห์ได้ที่แท็บ 'วิเคราะห์เรซูเม่ใหม่'")
        return

    st.write(f"พบประวัติทั้งหมด **{len(resumes)}** ฉบับ")

    for item in resumes:
        created_display = format_date(item["created_at"][:10]) if item["created_at"] else "ไม่ระบุวันที่"
        with st.expander(f"📄 **{item['title']}** (บันทึกเมื่อ: {created_display})"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"แหล่งที่มา: {item['file_name']} • เวลาที่บันทึก: {item['created_at']}")
            with col2:
                if st.button("🗑️ ลบรายงานนี้", key=f"del_resume_{item['id']}"):
                    delete_resume_analysis(item["id"])
                    st.success("ลบรายงานเรียบร้อยแล้ว")
                    st.rerun()

            st.divider()
            st.markdown(item["analysis_summary"])


def render():
    """
    จุดเริ่มต้นการแสดงผลของโมดูล Resume Analyzer
    """
    st.header("📄 วิเคราะห์เรซูเม่ (Resume Analyzer)")
    st.caption("ระบบตรวจประเมินคะแนน ATS สกัดทักษะ และปรับปรุงเรซูเม่ด้วย AI")

    tab_analyze, tab_history = st.tabs([
        "🔍 วิเคราะห์เรซูเม่ใหม่",
        "📚 ประวัติการวิเคราะห์",
    ])

    with tab_analyze:
        render_new_analysis_view()

    with tab_history:
        render_history_view()
