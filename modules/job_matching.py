"""
โมดูลที่ 3: จับคู่งานและทักษะ (Job Matching)
คำนวณคะแนนความเข้ากันได้ระหว่างผู้สมัครกับข้อกำหนดของตำแหน่งงาน พร้อมวิเคราะห์ช่องว่างทักษะ
"""
import streamlit as st
from utils.logger import setup_logger

logger = setup_logger("job_matching")


def calculate_match_score(resume_text: str, job_description: str) -> dict:
    """ตรรกะหลัก: คำนวณคะแนนความเข้ากันได้ (กำหนดพัฒนาใน Phase 5)"""
    logger.info("คำนวณคะแนนความเข้ากันได้")
    raise NotImplementedError("โมดูล Job Matching มีกำหนดพัฒนาใน Phase 5")


def render():
    """แสดงผลหน้าจอโมดูล Job Matching"""
    st.header("🎯 จับคู่งานและทักษะ (Job Matching)")
    st.caption("ประเมินความเข้ากันได้ด้วย AI วิเคราะห์ทักษะที่ขาด และเตรียมจุดแข็งสำหรับการสมัคร")

    st.info(
        "**สถานะโมดูล: วางแผนไว้ใน Phase 5**\n\n"
        "เมื่อโมดูลนี้พัฒนาเสร็จ คุณจะสามารถ:\n"
        "- ตรวจสอบเปอร์เซ็นต์ความเข้ากันได้ (% Match Score) ระหว่างเรซูเม่กับตำแหน่งงาน\n"
        "- จำแนกทักษะที่จำเป็น (Must-have) กับทักษะเสริม (Nice-to-have) ที่ยังขาดอยู่\n"
        "- รับข้อแนะนำประเด็นที่ควรเน้นตอบในรอบสัมภาษณ์เพื่อกลบจุดอ่อน"
    )

    with st.expander("ตัวอย่างหน้าจอการใช้งาน (Preview)", expanded=True):
        st.text_area("คำอธิบายตำแหน่งงาน (Job Description)", placeholder="วางรายละเอียดงานที่นี่...", disabled=True)
        st.button("คำนวณความเข้ากันได้", disabled=True, help="จะเปิดใช้งานใน Phase 5")
