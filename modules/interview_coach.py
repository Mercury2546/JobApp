"""
โมดูลที่ 4: ฝึกซ้อมสัมภาษณ์ (Interview Coach)
จำลองคำถามสัมภาษณ์งานเชิงลึก และประเมินคำตอบพร้อมข้อเสนอแนะตามหลัก STAR Method
"""
import streamlit as st
from utils.logger import setup_logger

logger = setup_logger("interview_coach")


def generate_interview_questions(role: str, experience_level: str, num_questions: int = 5) -> list:
    """ตรรกะหลัก: สร้างคำถามสัมภาษณ์ (กำหนดพัฒนาใน Phase 6)"""
    logger.info(f"สร้างคำถามสัมภาษณ์สำหรับ {role} ({experience_level})")
    raise NotImplementedError("โมดูล Interview Coach มีกำหนดพัฒนาใน Phase 6")


def render():
    """แสดงผลหน้าจอโมดูล Interview Coach"""
    st.header("🎙️ ฝึกซ้อมสัมภาษณ์ (Interview Coach)")
    st.caption("ฝึกตอบคำถามเชิงเทคนิคและเชิงพฤติกรรม (Behavioral) พร้อมรับคำติชมจาก AI")

    st.info(
        "**สถานะโมดูล: วางแผนไว้ใน Phase 6**\n\n"
        "เมื่อโมดูลนี้พัฒนาเสร็จ คุณจะสามารถ:\n"
        "- รับชุดคำถามสัมภาษณ์ที่ปรับแต่งตามตำแหน่งงานและระดับประสบการณ์ของคุณ\n"
        "- ตอบคำถามและรับคำติชมทันทีตามหลัก STAR Method (Situation, Task, Action, Result)\n"
        "- ติดตามพัฒนาการและความมั่นใจในแต่ละรอบการฝึกซ้อม"
    )

    with st.expander("ตัวอย่างหน้าจอการใช้งาน (Preview)", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("ตำแหน่งงานที่ต้องการซ้อม", placeholder="เช่น Data Scientist, Project Manager", disabled=True)
        with col2:
            st.selectbox("ระดับประสบการณ์", ["เด็กจบใหม่ (Entry)", "ระดับกลาง (Mid-Level)", "ระดับอาวุโส (Senior)", "ระดับหัวหน้างาน (Lead/Manager)"], disabled=True)
        st.button("เริ่มรอบซ้อมสัมภาษณ์", disabled=True, help="จะเปิดใช้งานใน Phase 6")
