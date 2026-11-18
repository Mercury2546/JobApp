"""
โมดูลที่ 5: วางแผนเส้นทางสายอาชีพ (Career Planner)
สร้างแผนที่การพัฒนาทักษะ (Career Roadmap) สู่ตำแหน่งงานเป้าหมายด้วย AI
รองรับการติดตามความคืบหน้ารายหมุดหมาย (Interactive Milestone Checklist)
และบันทึกเป้าหมายลงในฐานข้อมูล SQLite
"""
import json
from datetime import date
from typing import Dict, List, Optional
import streamlit as st
from config.settings import is_openai_configured
from database.db import get_db_connection
from services.ai_service import AIServiceError, ai_service
from utils.helpers import format_date, get_current_date_str
from utils.logger import setup_logger

logger = setup_logger("career_planner")

GOAL_STATUSES = ["In Progress", "Completed", "Archived"]

GOAL_STATUS_LABELS = {
    "In Progress": "🔄 กำลังดำเนินการ (In Progress)",
    "Completed": "🏆 สำเร็จแล้ว (Completed)",
    "Archived": "📦 เก็บถาวร (Archived)",
}


# ==========================================
# จัดการฐานข้อมูล SQLite (Database Operations)
# ==========================================

def add_career_goal(
    title: str,
    target_role: str,
    target_date: str = "",
    status: str = "In Progress",
    milestones_json: str = "[]",
    notes: str = "",
) -> int:
    """เพิ่มเป้าหมายเส้นทางสายอาชีพใหม่ลงใน SQLite"""
    if status not in GOAL_STATUSES:
        status = "In Progress"

    query = """
    INSERT INTO career_goals (title, target_role, target_date, status, milestones_json, notes)
    VALUES (?, ?, ?, ?, ?, ?);
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    title.strip(),
                    target_role.strip(),
                    target_date,
                    status,
                    milestones_json,
                    notes.strip(),
                ),
            )
            new_id = cursor.lastrowid
            logger.info(f"เพิ่มเป้าหมายอาชีพ ID {new_id}: {title} ({target_role})")
            return new_id
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเพิ่มเป้าหมายอาชีพ: {e}", exc_info=True)
        raise


def get_all_career_goals() -> List[Dict]:
    """ดึงข้อมูลเป้าหมายอาชีพทั้งหมดจาก SQLite"""
    query = "SELECT * FROM career_goals ORDER BY created_at DESC;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงเป้าหมายอาชีพ: {e}", exc_info=True)
        return []


def update_goal_milestones(goal_id: int, milestones_json: str) -> bool:
    """อัปเดตรายการงานย่อย/หมุดหมาย (Checklist) ของเป้าหมาย"""
    query = "UPDATE career_goals SET milestones_json = ? WHERE id = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (milestones_json, goal_id))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการอัปเดตหมุดหมาย ID {goal_id}: {e}", exc_info=True)
        raise


def update_career_goal_status(goal_id: int, new_status: str) -> bool:
    """เปลี่ยนสถานะของเป้าหมายอาชีพ"""
    if new_status not in GOAL_STATUSES:
        raise ValueError(f"สถานะไม่ถูกต้อง: {new_status}")

    query = "UPDATE career_goals SET status = ? WHERE id = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (new_status, goal_id))
            logger.info(f"เปลี่ยนสถานะเป้าหมาย ID {goal_id} เป็น {new_status}")
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเปลี่ยนสถานะ ID {goal_id}: {e}", exc_info=True)
        raise


def delete_career_goal(goal_id: int) -> bool:
    """ลบเป้าหมายอาชีพตาม ID"""
    query = "DELETE FROM career_goals WHERE id = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (goal_id,))
            logger.info(f"ลบเป้าหมายอาชีพ ID {goal_id} เรียบร้อย")
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"ไม่สามารถลบเป้าหมาย ID {goal_id} ได้: {e}", exc_info=True)
        raise


# ==========================================
# ตรรกะการสร้างแผนที่เส้นทางอาชีพด้วย AI
# ==========================================

def generate_career_roadmap_with_ai(
    current_role: str,
    target_role: str,
    timeframe_months: int,
    current_skills: str,
) -> str:
    """
    ให้ OpenAI วางแผนกลยุทธ์การเปลี่ยนผ่านสายอาชีพอย่างเป็นระบบ
    """
    if not current_role.strip() or not target_role.strip():
        raise ValueError("กรุณาระบุตำแหน่งปัจจุบันและตำแหน่งเป้าหมาย")

    system_prompt = (
        "คุณคือที่ปรึกษาวางแผนกลยุทธ์สายอาชีพระดับสูง (Principal Career Strategist)\n"
        "หน้าที่ของคุณคือวางแผนที่เส้นทางอาชีพ (Career Roadmap) ทีละขั้นตอนอย่างชัดเจน มีความเป็นไปได้จริง "
        "และตอบโจทย์ตลาดแรงงานระดับสากล\n\n"
        "จงตอบกลับเป็นภาษาไทยที่สร้างแรงบันดาลใจ มีโครงสร้าง Markdown ดังนี้:\n"
        "### 1. 🎯 ภาพรวมและหัวใจสำคัญของการเปลี่ยนผ่าน (Transition Strategy)\n"
        "- สรุปช่องว่างหลักระหว่างตำแหน่งปัจจุบันกับตำแหน่งเป้าหมาย และ mindset ที่ต้องปรับ\n\n"
        "### 2. 🗺️ แผนปฏิบัติการรายช่วงเวลา (Phased Milestone Roadmap)\n"
        f"- แบ่งเวลา {timeframe_months} เดือนออกเป็น 3-4 ช่วง แต่ละช่วงระบุ:\n"
        "  - **เป้าหมายหลักประจำช่วง**\n"
        "  - **ทักษะที่ต้องศึกษา (Hard & Soft Skills)**\n"
        "  - **ผลงานชิ้นโบว์แดงที่ต้องสร้าง (Capstone Deliverables)**\n\n"
        "### 3. 📚 ทรัพยากรและใบรับรองแนะนำ (Recommended Certifications & Resources)\n"
        "- ใบรับรอง คอร์สเรียน หรือหนังสือระดับมาตรฐานสากลที่ควรศึกษา\n\n"
        "### 4. ✅ รายการหมุดหมายเช็คลิสต์ 5 ข้อ (Suggested Milestones Checklist)\n"
        "- สรุปเป็น 5 ข้อความสั้นๆ สำหรับนำไปสร้างเป็น Checklist ติดตามผล\n"
    )

    user_prompt = (
        f"ตำแหน่งงานปัจจุบัน: {current_role}\n"
        f"ตำแหน่งงานเป้าหมาย: {target_role}\n"
        f"ระยะเวลาเป้าหมาย: {timeframe_months} เดือน\n"
        f"ทักษะและความเชี่ยวชาญปัจจุบัน: {current_skills or 'พื้นฐานทั่วไป'}\n"
    )

    logger.info(f"กำลังขอ Roadmap จาก AI สำหรับ {current_role} -> {target_role}")
    return ai_service.generate_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.4,
    )


# ==========================================
# หน้าจอแสดงผล (Streamlit UI Views)
# ==========================================

def render_roadmap_generator():
    """หน้าจอให้ AI สร้างแผนที่เส้นทางสายอาชีพ"""
    st.subheader("📈 สร้างแผนที่เส้นทางสายอาชีพด้วย AI (AI Roadmap Generator)")
    st.write("วางแผนการเปลี่ยนผ่านสายอาชีพ หรือการขยับขั้นสู่ตำแหน่งที่สูงขึ้นอย่างมีแบบแผนและวัดผลได้จริง")

    if not is_openai_configured():
        st.warning("⚠️ **ยังไม่ได้ตั้งค่า OpenAI API Key** โปรดระบุคีย์ใน `.env` เพื่อให้ AI สามารถสร้างแผนงานได้")

    col1, col2 = st.columns(2)
    with col1:
        current_role = st.text_input("ตำแหน่งงานปัจจุบันของคุณ *", placeholder="เช่น Junior Backend Developer", value="Junior Developer")
        target_role = st.text_input("ตำแหน่งงานเป้าหมายในอนาคต *", placeholder="เช่น Tech Lead / Senior Cloud Architect", value="Senior Software Engineer")
    with col2:
        timeframe = st.selectbox(
            "กรอบระยะเวลาเป้าหมาย",
            [6, 12, 18, 24, 36],
            index=1,
            format_func=lambda m: f"{m} เดือน ({m // 12} ปี {m % 12} เดือน)" if m >= 12 else f"{m} เดือน",
        )
        current_skills = st.text_input("ทักษะและความเชี่ยวชาญปัจจุบัน", placeholder="เช่น Python, Git, SQL, Flask")

    if st.button("🚀 สร้างแผนที่เส้นทางอาชีพ (Generate Roadmap)", type="primary", use_container_width=True):
        if not current_role.strip() or not target_role.strip():
            st.error("กรุณาระบุทั้งตำแหน่งงานปัจจุบันและตำแหน่งเป้าหมาย")
        else:
            with st.spinner("AI กำลังวิเคราะห์และออกแบบ Roadmap รายช่วงเวลา..."):
                try:
                    roadmap_text = generate_career_roadmap_with_ai(
                        current_role=current_role,
                        target_role=target_role,
                        timeframe_months=timeframe,
                        current_skills=current_skills,
                    )
                    st.session_state["generated_roadmap"] = {
                        "current_role": current_role,
                        "target_role": target_role,
                        "timeframe": timeframe,
                        "content": roadmap_text,
                    }
                    st.success("🎉 ออกแบบแผนที่เส้นทางอาชีพสำเร็จแล้ว!")
                except AIServiceError as e:
                    st.error(f"เกิดข้อผิดพลาดจาก AI Service: {e}")
                except Exception as e:
                    logger.error(f"เกิดข้อผิดพลาด: {e}", exc_info=True)
                    st.error(f"เกิดข้อผิดพลาด: {e}")

    # แสดงผล Roadmap ล่าสุด
    if "generated_roadmap" in st.session_state:
        road = st.session_state["generated_roadmap"]
        st.divider()
        st.subheader(f"🗺️ แผนที่เส้นทาง: จาก {road['current_role']} สู่ {road['target_role']} ({road['timeframe']} เดือน)")
        st.markdown(road["content"])

        # ปุ่มบันทึกเป็นเป้าหมายใน SQLite
        st.write("---")
        if st.button("💾 บันทึกแผนนี้เข้าสู่ 'เป้าหมายของฉัน' เพื่อติดตามผล", use_container_width=True):
            # สร้าง Default Checklist เบื้องต้น 4 ข้อ
            default_milestones = [
                {"title": f"ศึกษาทักษะหลักของตำแหน่ง {road['target_role']}", "done": False},
                {"title": "สร้างผลงานหรือโปรเจกต์ต้นแบบชิ้นที่ 1", "done": False},
                {"title": "รับผิดชอบงานหรือโปรเจกต์ที่ซับซ้อนขึ้นในที่ทำงานเดิม", "done": False},
                {"title": f"ปรับปรุงเรซูเม่และเริ่มสมัครตำแหน่ง {road['target_role']}", "done": False},
            ]
            goal_id = add_career_goal(
                title=f"ขยับสู่ {road['target_role']}",
                target_role=road["target_role"],
                target_date=get_current_date_str(),
                status="In Progress",
                milestones_json=json.dumps(default_milestones, ensure_ascii=False),
                notes=road["content"],
            )
            st.success(f"บันทึกเป้าหมายเรียบร้อยแล้ว (รหัสเป้าหมาย #{goal_id})! สามารถตรวจสอบและติ๊ก Checklist ได้ที่แท็บ 'เป้าหมายและความคืบหน้า'")


def render_my_goals_view():
    """หน้าจอติดตามเป้าหมายและ Checklist รายหมุดหมาย"""
    st.subheader("🎯 เป้าหมายสายอาชีพและความคืบหน้าของฉัน (My Goals & Checklist)")
    goals = get_all_career_goals()

    if not goals:
        st.info("ยังไม่มีเป้าหมายที่บันทึกไว้ สามารถสร้างเป้าหมายใหม่ได้ที่แท็บ 'สร้างแผนที่ด้วย AI' หรือ 'เพิ่มเป้าหมายด้วยตนเอง'")
        return

    st.write(f"พบเป้าหมายทั้งหมด **{len(goals)}** รายการ")

    for goal in goals:
        # ถอดรหัส JSON milestones
        try:
            milestones = json.loads(goal["milestones_json"])
            if not isinstance(milestones, list):
                milestones = []
        except Exception:
            milestones = []

        total_m = len(milestones)
        done_m = sum(1 for m in milestones if m.get("done", False))
        progress_pct = int((done_m / total_m) * 100) if total_m > 0 else 0

        status_label = GOAL_STATUS_LABELS.get(goal["status"], goal["status"])

        with st.expander(f"🏆 **{goal['title']}** — {goal['target_role']} [{status_label}] (ความคืบหน้า {progress_pct}%)", expanded=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**เป้าหมาย:** {goal['target_role']} • **บันทึกเมื่อ:** {format_date(goal['created_at'][:10])}")
                st.progress(progress_pct / 100.0, text=f"ความสำเร็จ {done_m}/{total_m} หมุดหมาย ({progress_pct}%)")
            with col2:
                # ตัวเลือกเปลี่ยนสถานะ
                current_st_idx = GOAL_STATUSES.index(goal["status"]) if goal["status"] in GOAL_STATUSES else 0
                new_st = st.selectbox(
                    "สถานะเป้าหมาย",
                    GOAL_STATUSES,
                    format_func=lambda s: GOAL_STATUS_LABELS.get(s, s),
                    index=current_st_idx,
                    key=f"goal_st_{goal['id']}",
                )
                if new_st != goal["status"]:
                    update_career_goal_status(goal["id"], new_st)
                    st.rerun()

                if st.button("🗑️ ลบเป้าหมายนี้", key=f"del_goal_{goal['id']}"):
                    delete_career_goal(goal["id"])
                    st.success("ลบเป้าหมายเรียบร้อยแล้ว")
                    st.rerun()

            st.divider()
            st.markdown("##### ✅ หมุดหมายและเช็คลิสต์ความคืบหน้า:")

            if not milestones:
                st.caption("ยังไม่มีรายการหมุดหมายย่อยในเป้าหมายนี้")
            else:
                updated = False
                for m_idx, m_item in enumerate(milestones):
                    checked = st.checkbox(
                        m_item["title"],
                        value=m_item.get("done", False),
                        key=f"chk_{goal['id']}_{m_idx}",
                    )
                    if checked != m_item.get("done", False):
                        milestones[m_idx]["done"] = checked
                        updated = True

                if updated:
                    update_goal_milestones(goal["id"], json.dumps(milestones, ensure_ascii=False))
                    st.rerun()

            if goal["notes"]:
                with st.expander("📖 ดูรายละเอียดเนื้อหาแผนงาน (Roadmap Notes)", expanded=False):
                    st.markdown(goal["notes"])


def render_manual_goal_form():
    """ฟอร์มสร้างเป้าหมายสายอาชีพด้วยตนเอง"""
    st.subheader("➕ เพิ่มเป้าหมายสายอาชีพด้วยตนเอง")
    st.write("ตั้งเป้าหมายและกำหนดภารกิจย่อย (Milestones) ด้วยตัวคุณเอง")

    with st.form("manual_goal_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("ชื่อเป้าหมาย *", placeholder="เช่น เลื่อนขั้นเป็น Senior Software Engineer")
            target_role = st.text_input("ตำแหน่งงานที่มุ่งหวัง *", placeholder="เช่น Senior Software Engineer")
        with col2:
            target_date = st.date_input("วันที่ตั้งเป้าหมายจะทำให้สำเร็จ", value=date.today())
            status = st.selectbox("สถานะเริ่มต้น", GOAL_STATUSES, format_func=lambda s: GOAL_STATUS_LABELS.get(s, s), index=0)

        milestone_inputs = st.text_area(
            "หมุดหมายย่อย (พิมพ์ทีละบรรทัด)",
            placeholder="เรียนคอร์ส System Design ให้จบ\nสร้างโปรเจกต์ Microservices บน AWS\nขอรับฟีดแบ็กจากหัวหน้าทีม\nยื่นประเมินผลงานปลายปี",
            height=140,
        )
        notes = st.text_area("บันทึกเพิ่มเติมหรือแผนปฏิบัติการ", placeholder="คำสัญญาต่อตนเอง ทรัพยากรที่จะใช้...")

        submitted = st.form_submit_button("💾 บันทึกเป้าหมายใหม่", use_container_width=True)

        if submitted:
            if not title.strip() or not target_role.strip():
                st.error("กรุณาระบุทั้งชื่อเป้าหมายและตำแหน่งงานที่มุ่งหวัง")
            else:
                # แปลงข้อความหมุดหมายทีละบรรทัดเป็น JSON List
                lines = [line.strip() for line in milestone_inputs.split("\n") if line.strip()]
                milestones_list = [{"title": line, "done": False} for line in lines]

                try:
                    new_id = add_career_goal(
                        title=title,
                        target_role=target_role,
                        target_date=str(target_date),
                        status=status,
                        milestones_json=json.dumps(milestones_list, ensure_ascii=False),
                        notes=notes,
                    )
                    st.success(f"🎉 บันทึกเป้าหมาย #{new_id} เรียบร้อยแล้ว!")
                    st.rerun()
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดในการบันทึกเป้าหมาย: {e}")


def render():
    """
    จุดเริ่มต้นการแสดงผลของโมดูล Career Planner
    """
    st.header("📈 วางแผนเส้นทางสายอาชีพ (Career Planner)")
    st.caption("กำหนดเป้าหมาย วางแผนที่เส้นทางอาชีพด้วย AI และติดตามหมุดหมายความสำเร็จ")

    tab_ai, tab_my_goals, tab_manual = st.tabs([
        "📈 สร้างแผนที่ด้วย AI (AI Roadmap)",
        "🎯 เป้าหมายและความคืบหน้า (My Goals)",
        "➕ เพิ่มเป้าหมายด้วยตนเอง (Manual Entry)",
    ])

    with tab_ai:
        render_roadmap_generator()

    with tab_my_goals:
        render_my_goals_view()

    with tab_manual:
        render_manual_goal_form()
