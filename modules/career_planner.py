"""
โมดูลที่ 5: วางแผนเส้นทางอาชีพ (Career Planner)
สร้างแผนที่การพัฒนาทักษะ (Skill Roadmap) และหมุดหมายความสำเร็จในสายอาชีพระยะยาว
"""
import streamlit as st
from utils.logger import setup_logger

logger = setup_logger("career_planner")


def generate_career_roadmap(current_role: str, target_role: str, timeline_months: int = 12) -> dict:
    """ตรรกะหลัก: สร้างแผนที่เส้นทางอาชีพ (กำหนดพัฒนาใน Phase 7)"""
    logger.info(f"วางแผนเส้นทางอาชีพจาก {current_role} สู่ {target_role}")
    raise NotImplementedError("โมดูล Career Planner มีกำหนดพัฒนาใน Phase 7")


def render():
    """แสดงผลหน้าจอโมดูล Career Planner"""
    st.header("📈 วางแผนเส้นทางอาชีพ (Career Planner)")
    st.caption("กำหนดเป้าหมาย วางแผนการเรียนรู้ทักษะใหม่ และสร้าง Roadmaps สู่ตำแหน่งงานในฝัน")

    st.info(
        "**สถานะโมดูล: วางแผนไว้ใน Phase 7**\n\n"
        "เมื่อโมดูลนี้พัฒนาเสร็จ คุณจะสามารถ:\n"
        "- กำหนดตำแหน่งงานปัจจุบันและเป้าหมายที่ต้องการขยับขึ้นไปในอนาคต\n"
        "- รับแผนปฏิบัติการรายเดือนในการเรียนรู้ทักษะ และสร้างผลงานพอร์ตโฟลิโอ\n"
        "- บันทึกและติดตามความคืบหน้าของเป้าหมายบนฐานข้อมูล SQLite"
    )

    with st.expander("ตัวอย่างหน้าจอการใช้งาน (Preview)", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("ตำแหน่งงานปัจจุบัน", placeholder="เช่น Junior Developer", disabled=True)
        with col2:
            st.text_input("ตำแหน่งเป้าหมายในอนาคต", placeholder="เช่น Tech Lead / Solutions Architect", disabled=True)
        st.button("สร้างแผนที่เส้นทางอาชีพ", disabled=True, help="จะเปิดใช้งานใน Phase 7")
