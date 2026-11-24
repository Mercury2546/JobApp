"""
โมดูลที่ 3: จับคู่งานและทักษะ (Job Matching)
วิเคราะห์ความเข้ากันได้ระหว่างเรซูเม่ของผู้สมัครกับคำอธิบายตำแหน่งงาน (Job Description)
ประเมินคะแนน % Match Score จำแนกทักษะที่มีและทักษะที่ขาด (Must-have vs. Nice-to-have)
พร้อมให้คำแนะนำเชิงกลยุทธ์เพื่อปิดช่องว่างทักษะและเตรียมตัวสัมภาษณ์
"""

import streamlit as st

from config.settings import is_openai_configured
from modules.application_tracker import get_all_applications
from modules.resume_analyzer import get_all_resumes
from services.ai_service import AIServiceError, ai_service
from utils.helpers import extract_job_details_from_image, fetch_job_description_from_url
from utils.logger import setup_logger

logger = setup_logger("job_matching")


# ==========================================
# ตรรกะการวิเคราะห์ความเข้ากันได้ด้วย AI
# ==========================================


def calculate_job_match_with_ai(resume_text: str, job_description: str) -> str:
    """
    ส่งข้อมูลเรซูเม่และ Job Description ให้ OpenAI วิเคราะห์ความเข้ากันได้แบบเจาะลึก
    """
    if not resume_text.strip():
        raise ValueError("ข้อมูลเรซูเม่ต้องไม่ว่างเปล่า")
    if not job_description.strip():
        raise ValueError("ข้อมูลคำอธิบายตำแหน่งงาน (Job Description) ต้องไม่ว่างเปล่า")

    system_prompt = (
        "คุณคือผู้เชี่ยวชาญด้านการคัดเลือกบุคลากร (Senior Talent Acquisition Specialist) "
        "และที่ปรึกษาด้านการสัมภาษณ์งานระดับสากล\n"
        "หน้าที่ของคุณคือเปรียบเทียบเรซูเม่ของผู้สมัครกับประกาศรับสมัครงานอย่างละเอียด ตรงไปตรงมา และมีหลักการ\n\n"
        "จงตอบกลับเป็นภาษาไทยที่สุภาพ กระชับ เป็นมืออาชีพ โดยใช้โครงสร้าง Markdown ดังนี้:\n"
        "### 1. 🎯 คะแนนความเข้ากันได้โดยรวม (Match Compatibility Score)\n"
        "- ระบุตัวเลขชัดเจนในรูปแบบ: **[XX]%** (เช่น 85%)\n"
        "- คำวินิจฉัยสรุปภาพรวม 2-3 บรรทัด ว่าโปรไฟล์นี้เหมาะกับตำแหน่งงานมากน้อยเพียงใด\n\n"
        "### 2. ✅ ทักษะและประสบการณ์ที่มีตรงกัน (Matched Core Competencies)\n"
        "- ระบุทักษะด้านเทคนิค (Hard Skills), เครื่องมือ, หรือประสบการณ์ที่ผู้สมัครมีและตรงกับความต้องการของงานชัดเจน\n\n"
        "### 3. 🚨 ทักษะจำเป็นที่ยังขาดหาย (Missing Must-Have Requirements)\n"
        "- ทักษะสำคัญที่เป็นข้อกำหนดหลักของตำแหน่งงาน (Deal-breakers) แต่ไม่พบในเรซูเม่\n\n"
        "### 4. 💡 ทักษะเสริมที่ควรมีเพิ่มเติม (Missing Nice-To-Have Skills)\n"
        "- คุณสมบัติเสริมที่จะช่วยเพิ่มความโดดเด่นแต่ไม่ใช่ข้อบังคับ\n\n"
        "### 5. 🛡️ กลยุทธ์การนำเสนอและกลบจุดอ่อนในการสัมภาษณ์ (Interview Positioning Strategy)\n"
        "- คำแนะนำ 3 ข้อในการตอบคำถามสัมภาษณ์ เพื่ออธิบายหรือเชื่อมโยงประสบการณ์เดิมมาทดแทนทักษะที่ยังขาดอยู่\n"
    )

    user_prompt = (
        f"--- เนื้อหาเรซูเม่ของผู้สมัคร ---\n{resume_text.strip()}\n\n"
        f"--- ประกาศรับสมัครงานเป้าหมาย (Job Description) ---\n{job_description.strip()}"
    )

    logger.info("กำลังส่งคำขอวิเคราะห์ Job Matching ไปยัง OpenAI...")
    return ai_service.generate_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.3,
    )


# ==========================================
# หน้าจอแสดงผล (Streamlit UI Views)
# ==========================================


def render_matching_tool():
    """หน้าจอหลักสำหรับเปรียบเทียบเรซูเม่กับตำแหน่งงาน"""
    st.subheader("🎯 ประเมินความเข้ากันได้ระหว่างเรซูเม่และตำแหน่งงาน")
    st.write(
        "เลือกเรซูเม่ของคุณและนำมาเปรียบเทียบกับคำอธิบายตำแหน่งงาน เพื่อดูเปอร์เซ็นต์ความเข้ากันได้และทักษะที่ต้องเตรียมตัว"
    )

    if not is_openai_configured():
        st.warning(
            "⚠️ **ยังไม่ได้ตั้งค่า OpenAI API Key ในไฟล์ `.env`**\n\n"
            "ระบบจำเป็นต้องใช้ OpenAI API Key ในการวิเคราะห์ โปรดใส่คีย์ของคุณก่อนกดคำนวณ"
        )

    # ดึงเรซูเม่และงานที่บันทึกไว้ในฐานข้อมูลเพื่อความสะดวก
    saved_resumes = get_all_resumes()
    saved_apps = get_all_applications()

    col_res, col_job = st.columns(2)

    # --- ส่วนที่ 1: เลือกหรือกรอกเรซูเม่ ---
    with col_res:
        st.markdown("#### 1. ข้อมูลเรซูเม่ของผู้สมัคร")
        has_shared_resume = bool(st.session_state.get("shared_resume_text", "").strip())
        resume_sources = (
            ["✨ ใช้เรซูเม่ล่าสุดในเซสชัน", "เลือกจากประวัติเรซูเม่ที่บันทึกไว้", "พิมพ์หรือวางข้อความใหม่"]
            if has_shared_resume
            else ["เลือกจากประวัติเรซูเม่ที่บันทึกไว้", "พิมพ์หรือวางข้อความใหม่"]
        )
        resume_source = st.radio(
            "แหล่งที่มาของเรซูเม่",
            resume_sources,
            horizontal=True,
            key="match_resume_src",
        )

        resume_text_to_use = ""
        if resume_source == "✨ ใช้เรซูเม่ล่าสุดในเซสชัน":
            resume_text_to_use = st.session_state.get("shared_resume_text", "")
            st.caption(f"โหลดจากเซสชันล่าสุด: ความยาว {len(resume_text_to_use):,} ตัวอักษร")
        elif resume_source == "เลือกจากประวัติเรซูเม่ที่บันทึกไว้":
            if saved_resumes:
                resume_choices = {
                    f"{r['title']} (บันทึกเมื่อ {r['created_at'][:10] if r.get('created_at') else 'ไม่ระบุ'})": r[
                        "raw_text"
                    ]
                    for r in saved_resumes
                }
                selected_label = st.selectbox(
                    "เลือกเรซูเม่ที่ต้องการใช้", list(resume_choices.keys())
                )
                resume_text_to_use = resume_choices[selected_label]
                st.caption(f"โหลดข้อมูลแล้ว: ความยาว {len(resume_text_to_use):,} ตัวอักษร")
            else:
                st.info("ยังไม่มีเรซูเม่ที่บันทึกไว้ คุณสามารถเลือกตัวเลือก 'พิมพ์หรือวางข้อความใหม่' ได้")
                resume_source = "พิมพ์หรือวางข้อความใหม่"

        if resume_source == "พิมพ์หรือวางข้อความใหม่":
            resume_text_to_use = st.text_area(
                "วางเนื้อหาเรซูเม่ที่นี่ *",
                value=resume_text_to_use,
                height=220,
                placeholder="วางข้อความเรซูเม่ของคุณที่นี่...",
            )

    # --- ส่วนที่ 2: เลือกหรือกรอก Job Description ---
    with col_job:
        st.markdown("#### 2. คำอธิบายตำแหน่งงานเป้าหมาย (Job Description)")
        job_source = st.radio(
            "แหล่งที่มาของรายละเอียดงาน",
            [
                "🔗 ดึงจากลิงก์เว็บ (URL)",
                "🖼️ สแกนจากภาพโปสเตอร์ (Facebook)",
                "พิมพ์หรือวางข้อความประกาศงาน",
                "ดึงจากงานที่ติดตามอยู่ในระบบ",
            ],
            horizontal=True,
            key="match_job_src",
        )

        jd_text_to_use = ""

        if job_source == "🔗 ดึงจากลิงก์เว็บ (URL)":
            col_url, col_fetch = st.columns([4, 1])
            with col_url:
                job_url_input = st.text_input(
                    "วางลิงก์ประกาศรับสมัครงาน (Job URL)",
                    value=st.session_state.get("matching_job_url")
                    or st.session_state.get("shared_job_url", ""),
                    placeholder="เช่น https://th.jobsdb.com/job/... หรือ https://careers.company.com/...",
                    key="match_job_url_input",
                )
            with col_fetch:
                fetch_btn = st.button(
                    "🌐 ดึงข้อมูล JD", use_container_width=True, key="match_fetch_btn"
                )

            if fetch_btn:
                if not job_url_input.strip():
                    st.warning("กรุณาระบุ URL ก่อน")
                else:
                    with st.spinner("🌐 กำลังเชื่อมต่อไปยังเว็บไซต์เพื่ออ่านเนื้อหาประกาศงาน..."):
                        fetch_res = fetch_job_description_from_url(job_url_input)
                        if fetch_res["success"]:
                            st.session_state["matching_job_url"] = fetch_res["url"]
                            st.session_state["matching_jd_text"] = fetch_res["text"]
                            st.session_state["shared_job_url"] = fetch_res["url"]
                            st.session_state["shared_jd_text"] = fetch_res["text"]
                            st.toast(
                                f"✅ ดึงเนื้อหาประกาศงานสำเร็จ! ({len(fetch_res['text'])} ตัวอักษร)"
                            )
                            st.rerun()
                        else:
                            st.error(f"❌ {fetch_res['error']}")

            jd_text_to_use = st.text_area(
                "เนื้อหาประกาศรับสมัครงานที่ดึงมา (ตรวจสอบหรือแก้ไขได้) *",
                value=st.session_state.get("matching_jd_text")
                or st.session_state.get("shared_jd_text", ""),
                height=200,
                placeholder="วางลิงก์ด้านบนแล้วกด 'ดึงข้อมูล JD' หรือพิมพ์รายละเอียดที่นี่...",
                key="match_url_jd_area",
            )

        elif job_source == "🖼️ สแกนจากภาพโปสเตอร์ (Facebook)":
            uploaded_match_img = st.file_uploader(
                "อัปโหลดภาพโปสเตอร์หรือภาพแคปหน้าจอ (PNG, JPG, JPEG, WEBP)",
                type=["png", "jpg", "jpeg", "webp"],
                key="match_uploader_img",
            )
            if uploaded_match_img:
                m_col1, m_col2 = st.columns([1, 2])
                with m_col1:
                    st.image(
                        uploaded_match_img,
                        caption="ภาพประกาศงาน",
                        use_container_width=True,
                    )
                with m_col2:
                    if st.button(
                        "🔍 ให้ AI Vision สแกนภาพนี้ทันที",
                        type="primary",
                        use_container_width=True,
                        key="match_scan_btn",
                    ):
                        with st.spinner(
                            "🤖 AI กำลังอ่านตัวหนังสือและสกัดข้อมูล JD จากรูปภาพ..."
                        ):
                            scan_res = extract_job_details_from_image(
                                uploaded_match_img.getvalue(),
                                mime_type=uploaded_match_img.type or "image/jpeg",
                            )
                            if scan_res["success"]:
                                st.session_state["matching_jd_text"] = scan_res[
                                    "job_description"
                                ]
                                st.session_state["shared_jd_text"] = scan_res[
                                    "job_description"
                                ]
                                if scan_res.get("company"):
                                    st.session_state["shared_company"] = scan_res[
                                        "company"
                                    ]
                                if scan_res.get("role"):
                                    st.session_state["shared_role"] = scan_res["role"]
                                st.toast("✅ สแกนภาพสำเร็จ!")
                                st.rerun()
                            else:
                                st.error(f"❌ {scan_res['error']}")

            jd_text_to_use = st.text_area(
                "เนื้อหาประกาศงานที่สแกนได้จากภาพ (ตรวจสอบหรือแก้ไขได้) *",
                value=st.session_state.get("matching_jd_text", ""),
                height=200,
                placeholder="อัปโหลดรูปภาพด้านบนแล้วกด 'ให้ AI Vision สแกนภาพนี้ทันที'...",
            )

        elif job_source == "ดึงจากงานที่ติดตามอยู่ในระบบ":
            if saved_apps:
                app_choices = {
                    f"{a['company']} - {a['role']} ({a['status']})": a
                    for a in saved_apps
                }
                selected_app_label = st.selectbox(
                    "เลือกงานที่ติดตามอยู่", list(app_choices.keys())
                )
                chosen_app = app_choices[selected_app_label]
                jd_text_to_use = (
                    chosen_app.get("notes")
                    or f"ตำแหน่ง: {chosen_app['role']}\nบริษัท: {chosen_app['company']}\nสถานที่: {chosen_app['location']}"
                )
                st.caption(f"ดึงข้อมูลงาน: {chosen_app['role']} ที่ {chosen_app['company']}")
            else:
                st.info(
                    "ยังไม่มีรายการงานในระบบติดตาม คุณสามารถพิมพ์หรือวางข้อความประกาศงานได้โดยตรง"
                )
                job_source = "พิมพ์หรือวางข้อความประกาศงาน"

        elif job_source == "พิมพ์หรือวางข้อความประกาศงาน":
            jd_text_to_use = st.text_area(
                "วางรายละเอียดประกาศรับสมัครงาน *",
                value=jd_text_to_use or st.session_state.get("shared_jd_text", ""),
                height=220,
                placeholder="วางข้อความคุณสมบัติ หน้าที่ความรับผิดชอบ และความต้องการของตำแหน่งงานที่นี่...",
                key="match_manual_jd_area",
            )

    # ปุ่มเริ่มการคำนวณ
    st.divider()
    if st.button(
        "🚀 คำนวณความเข้ากันได้และวิเคราะห์ทักษะ (Calculate Match)",
        type="primary",
        use_container_width=True,
    ):
        if not resume_text_to_use.strip():
            st.error("กรุณาระบุข้อมูลเรซูเม่ของผู้สมัคร")
        elif not jd_text_to_use.strip():
            st.error("กรุณาระบุคำอธิบายตำแหน่งงาน (Job Description)")
        else:
            st.session_state["shared_resume_text"] = resume_text_to_use.strip()
            st.session_state["shared_jd_text"] = jd_text_to_use.strip()
            with st.spinner("AI กำลังเปรียบเทียบทักษะและคำนวณคะแนนความเข้ากันได้..."):
                try:
                    match_result = calculate_job_match_with_ai(
                        resume_text_to_use, jd_text_to_use
                    )
                    st.session_state["latest_job_match_result"] = match_result
                    st.success("🎉 วิเคราะห์ความเข้ากันได้สำเร็จแล้ว!")
                except AIServiceError as e:
                    st.error(f"เกิดข้อผิดพลาดจาก AI Service: {e}")
                except Exception as e:
                    logger.exception("เกิดข้อผิดพลาดในการคำนวณ Job Matching")
                    st.error(f"เกิดข้อผิดพลาด: {e}")

    # แสดงผลลัพธ์การวิเคราะห์
    if "latest_job_match_result" in st.session_state:
        st.divider()
        st.subheader("📊 ผลการวิเคราะห์ความเข้ากันได้และช่องว่างทักษะ")
        st.markdown(st.session_state["latest_job_match_result"])

        b_col1, b_col2 = st.columns(2)
        with b_col1:
            if st.button(
                "✉️ นำข้อมูลนี้ไปร่างอีเมลสมัครงาน",
                use_container_width=True,
                key="match_to_email_btn",
            ):
                st.session_state["fetched_jd_text"] = st.session_state.get(
                    "shared_jd_text", ""
                )
                st.session_state["nav_selection"] = "✉️ ร่างอีเมลสมัครงาน"
                st.rerun()
        with b_col2:
            if st.button(
                "🎙️ นำตำแหน่งนี้ไปซ้อมสัมภาษณ์",
                use_container_width=True,
                key="match_to_interview_btn",
            ):
                st.session_state["nav_selection"] = "🎙️ ฝึกซ้อมสัมภาษณ์"
                st.rerun()


def render_skill_bridge_guide():
    """คำแนะนำและเทคนิคการปิดช่องว่างทักษะอย่างรวดเร็ว"""
    st.subheader("💡 กลยุทธ์และเทคนิคการปิดช่องว่างทักษะ (Skill Bridge Guide)")
    st.markdown(
        """
        เมื่อพบว่าเรซูเม่ของคุณมีทักษะไม่ตรงกับ Job Description 100% ไม่จำเป็นต้องกังวล เพราะนายจ้างส่วนใหญ่เปิดรับผู้สมัครที่มีความเข้ากันได้ตั้งแต่ **70% ขึ้นไป** นี่คือแนวทางรับมือ:

        ---

        #### 1. กลยุทธ์ "ทักษะที่ถ่ายโอนได้" (Transferable Skills)
        - หากขาดเครื่องมือเฉพาะ (เช่น ขาดประสบการณ์ในเครื่องมือ A แต่คุณเชี่ยวชาญเครื่องมือ B ที่ทำงานคล้ายกัน):
          - **ตัวอย่างการตอบ:** *"ผมมีพื้นฐานการใช้ AWS อย่างแน่นหนาตลอด 3 ปี ซึ่งคอนเซ็ปต์การจัดการ Cloud Infrastructure มีหลักการเดียวกับ Azure ที่ตำแหน่งนี้ต้องการ จึงมั่นใจว่าจะสามารถปรับตัวใช้งานได้ในเวลาอันสั้นครับ"*

        #### 2. แผนการเรียนรู้แบบเร่งรัด (Fast-track Upskilling)
        - สร้างโปรเจกต์ขนาดเล็ก (Proof of Concept) ด้วยทักษะที่ขาดไป แล้วนำลิงก์ GitHub ไปใส่ไว้ในเรซูเม่
        - ลงเรียนคอร์สออนไลน์สั้นๆ หรือสอบใบรับรองพื้นฐานเพื่อแสดงถึงความกระตือรือร้นในการเรียนรู้

        #### 3. ปรับแต่งคีย์เวิร์ดในเรซูเม่ให้ตรงกับคำประกาศงาน
        - ตรวจสอบว่าคำศัพท์ที่คุณใช้ตรงกับใน Job Description หรือไม่ เช่น ประกาศใช้คำว่า `CI/CD Automation` แต่ในเรซูเม่เขียนเพียงแค่ `Deployment Scripts` การเปลี่ยนคำให้ตรงกันจะช่วยเพิ่มคะแนน ATS ได้ทันที
        """
    )


def render():
    """
    จุดเริ่มต้นการแสดงผลของโมดูล Job Matching
    """
    st.header("🎯 จับคู่งานและทักษะ (Job Matching)")
    st.caption("ประเมินความเข้ากันได้ระหว่างเรซูเม่กับตำแหน่งงาน วิเคราะห์จุดแข็ง และแนวทางกลบจุดอ่อน")

    tab_match, tab_guide = st.tabs(
        [
            "🎯 วิเคราะห์ความเข้ากันได้ (Match Analysis)",
            "💡 คำแนะนำปิดช่องว่างทักษะ (Skill Bridge Guide)",
        ]
    )

    with tab_match:
        render_matching_tool()

    with tab_guide:
        render_skill_bridge_guide()
