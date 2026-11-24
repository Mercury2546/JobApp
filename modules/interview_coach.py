"""
โมดูลที่ 4: ฝึกซ้อมสัมภาษณ์จำลอง (Interview Coach)
จำลองคำถามสัมภาษณ์งานเชิงลึก (คำถามเชิงพฤติกรรม Behavioral และคำถามเชิงเทคนิค Technical)
มีพื้นที่ให้ผู้ใช้ฝึกตอบ และประเมินผลลัพธ์ด้วย AI ตามหลัก STAR Method พร้อมบันทึกประวัติลงใน SQLite
"""

import json

import streamlit as st

from config.settings import is_openai_configured
from database.db import get_db_connection
from services.ai_service import AIServiceError, ai_service
from utils.helpers import format_date
from utils.logger import setup_logger

logger = setup_logger("interview_coach")

DIFFICULTY_LEVELS = [
    "ง่าย (Entry Level)",
    "ปานกลาง (Mid-Level)",
    "ท้าทาย / ขั้นสูง (Senior / Lead)",
]
QUESTION_TYPES = [
    "ผสมผสาน (พฤติกรรม + เทคนิค)",
    "คำถามเชิงพฤติกรรม (Behavioral - STAR)",
    "คำถามเชิงเทคนิคและการแก้ปัญหา (Technical & Problem Solving)",
]


# ==========================================
# จัดการฐานข้อมูล SQLite (Database Operations)
# ==========================================


def save_interview_session(
    role: str,
    company: str,
    difficulty: str,
    questions_json: str,
    answers_json: str,
    feedback: str,
    score: float,
) -> int:
    """บันทึกรอบการซ้อมสัมภาษณ์และผลประเมินลงใน SQLite"""
    query = """
    INSERT INTO interview_sessions (role, company, difficulty, questions_json, answers_json, feedback, score)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    role.strip(),
                    company.strip() if company else "ไม่ระบุบริษัท",
                    difficulty,
                    questions_json,
                    answers_json,
                    feedback.strip(),
                    score,
                ),
            )
            new_id = cursor.lastrowid
            logger.info(f"บันทึกประวัติการซ้อมสัมภาษณ์ ID {new_id} ({role}) เรียบร้อย")
            return new_id
    except Exception:
        logger.exception("เกิดข้อผิดพลาดในการบันทึกรอบสัมภาษณ์")
        raise


def get_all_interview_sessions() -> list[dict]:
    """ดึงประวัติการซ้อมสัมภาษณ์ทั้งหมดจาก SQLite"""
    query = "SELECT * FROM interview_sessions ORDER BY created_at DESC;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("เกิดข้อผิดพลาดในการดึงประวัติสัมภาษณ์")
        return []


def delete_interview_session(session_id: int) -> bool:
    """ลบประวัติการซ้อมสัมภาษณ์ตาม ID"""
    query = "DELETE FROM interview_sessions WHERE id = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (session_id,))
            logger.info(f"ลบประวัติการซ้อมสัมภาษณ์ ID {session_id} เรียบร้อย")
            return cursor.rowcount > 0
    except Exception:
        logger.exception(f"ไม่สามารถลบประวัติการซ้อมสัมภาษณ์ ID {session_id} ได้")
        raise


# ==========================================
# ตรรกะการสร้างคำถามและประเมินผลด้วย AI
# ==========================================


def generate_questions_with_ai(
    role: str, company: str, difficulty: str, q_type: str, num_q: int = 3
) -> list[str]:
    """
    ขอชุดคำถามสัมภาษณ์จาก OpenAI
    """
    if not role.strip():
        raise ValueError("กรุณาระบุตำแหน่งงาน")

    system_prompt = (
        "คุณคือหัวหน้าผู้สัมภาษณ์งานมืออาชีพ (Lead Interviewer) "
        "หน้าที่ของคุณคือออกคำถามสัมภาษณ์งานที่สมจริง คมคาย และตรงกับตำแหน่งงาน\n\n"
        f"จงออกคำถามจำนวน {num_q} ข้อ โดยตอบกลับเป็นรูปแบบ JSON List ของสตริงเท่านั้น เช่น:\n"
        '["คำถามข้อที่ 1...", "คำถามข้อที่ 2...", "คำถามข้อที่ 3..."]\n'
        "ไม่ต้องมีข้อความอื่นใดนอกเหนือจาก JSON เพื่อให้ระบบสามารถแปลงได้ทันที"
    )

    user_prompt = (
        f"ตำแหน่งงาน: {role}\n"
        f"บริษัทเป้าหมาย: {company or 'บริษัทชั้นนำทั่วไป'}\n"
        f"ระดับความยาก: {difficulty}\n"
        f"ประเภทคำถามที่ต้องการ: {q_type}\n"
    )

    logger.info(f"สร้างคำถามสัมภาษณ์ด้วย AI สำหรับ {role}")
    response = ai_service.generate_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.5,
    )

    try:
        # ทำความสะอาดข้อความ Markdown code block ถ้ามี
        clean_resp = response.strip()
        if clean_resp.startswith("```"):
            clean_resp = clean_resp.split("\n", 1)[1]
            if clean_resp.endswith("```"):
                clean_resp = clean_resp.rsplit("\n", 1)[0]
            clean_resp = clean_resp.strip()
            if clean_resp.lower().startswith("json"):
                clean_resp = clean_resp[4:].strip()

        questions = json.loads(clean_resp)
        if isinstance(questions, list):
            return [str(q).strip() for q in questions if str(q).strip()]
        return [response]
    except (json.JSONDecodeError, ValueError, IndexError) as e:
        logger.warning(f"ไม่สามารถแปลง JSON คำถามสัมภาษณ์ได้ แปลงเป็นลิสต์บรรทัดแทน: {e}")
        lines = [
            line.strip("- 1234567890.").strip()
            for line in response.split("\n")
            if line.strip()
        ]
        return lines[:num_q] if lines else [response]


def evaluate_answers_with_ai(
    role: str, questions: list[str], answers: list[str]
) -> str:
    """
    ส่งคำตอบของผู้สมัครให้ OpenAI ประเมินตามเกณฑ์ STAR Method
    """
    qa_pairs = []
    for i, (q, a) in enumerate(zip(questions, answers), 1):
        qa_pairs.append(f"คำถามที่ {i}: {q}\nคำตอบของผู้สมัคร: {a.strip() or 'ไม่ได้ตอบ'}")

    qa_text = "\n\n".join(qa_pairs)

    system_prompt = (
        "คุณคือโค้ชสอนสัมภาษณ์งานระดับสากล (Executive Interview Coach)\n"
        "หน้าที่ของคุณคือวิเคราะห์คำตอบของผู้สมัครอย่างสร้างสรรค์ ชี้จุดแข็ง และแนะนำจุดแก้ไขตามหลัก STAR Method "
        "(Situation, Task, Action, Result)\n\n"
        "จงตอบกลับเป็นภาษาไทยที่สุภาพ ตรงจุด และสร้างแรงบันดาลใจ โดยใช้โครงสร้าง Markdown ดังนี้:\n"
        "### 1. 🏆 คะแนนประเมินภาพรวม (Overall Interview Score)\n"
        "- ให้คะแนนภาพรวมในรูปแบบ: **[XX]/100** พร้อมบทวิเคราะห์ภาพรวมสั้นๆ\n\n"
        "### 2. ⭐ จุดเด่นของคำตอบ (Key Strengths)\n"
        "- สิ่งที่ตอบได้ดี ความชัดเจน ทัศนคติ และทักษะการสื่อสาร\n\n"
        "### 3. 🔍 การวิเคราะห์รายข้อตามหลัก STAR (Per-Question STAR Critique)\n"
        "- ประเมินคำตอบแต่ละข้อว่ามี Situation, Task, Action, Result ชัดเจนหรือไม่ และยังขาดจุดใด\n\n"
        "### 4. ✍️ แนวทางการปรับปรุงและคำตอบเวอร์ชันอัปเกรด (Refined Answer Suggestions)\n"
        "- ยกตัวอย่างการตอบที่ดีขึ้น 1-2 ข้อ เพื่อเพิ่มความน่าประทับใจให้แก่ผู้สัมภาษณ์\n"
    )

    user_prompt = f"ตำแหน่งงานที่สัมภาษณ์: {role}\n\n--- บันทึกการถาม-ตอบ ---\n{qa_text}"

    logger.info("กำลังประเมินคำตอบสัมภาษณ์ด้วย AI...")
    return ai_service.generate_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.3,
    )


# ==========================================
# หน้าจอแสดงผล (Streamlit UI Views)
# ==========================================


def render_practice_session():
    """หน้าจอจำลองรอบการซ้อมสัมภาษณ์งาน"""
    st.subheader("🎙️ เริ่มรอบซ้อมสัมภาษณ์จำลอง")
    st.write(
        "ตั้งค่าตำแหน่งงานที่ต้องการ จากนั้นให้ AI ออกคำถามสัมภาษณ์ และส่งคำตอบเพื่อรับการประเมินตามหลัก STAR"
    )

    if not is_openai_configured():
        st.warning(
            "⚠️ **ยังไม่ได้ตั้งค่า OpenAI API Key** โปรดระบุคีย์ในไฟล์ `.env` เพื่อให้ AI สามารถสร้างคำถามและประเมินผลได้"
        )

    col1, col2 = st.columns(2)
    with col1:
        role_presets = [
            "🎨 Graphic Designer",
            "✨ UX/UI Designer",
            "🖌️ Graphic & Content Creator",
            "📱 Product Designer (UI/UX)",
            "💻 Web & Graphic Designer",
            "✏️ พิมพ์ระบุตำแหน่งอื่นเอง...",
        ]
        shared_role = st.session_state.get("shared_role", "").strip()
        default_role_idx = len(role_presets) - 1 if shared_role else 1
        selected_role_preset = st.radio(
            "ตำแหน่งงานที่ต้องการซ้อมสัมภาษณ์ * (กดเลือกได้ทันที)",
            role_presets,
            index=default_role_idx,
        )
        if selected_role_preset == "✏️ พิมพ์ระบุตำแหน่งอื่นเอง...":
            role = st.text_input(
                "พิมพ์ชื่อตำแหน่งงาน *",
                value=shared_role,
                placeholder="เช่น Senior UX/UI Specialist, Motion Artist",
            )
        else:
            role = (
                selected_role_preset.replace("🎨 ", "")
                .replace("✨ ", "")
                .replace("🖌️ ", "")
                .replace("📱 ", "")
                .replace("💻 ", "")
                .replace("🎯 ", "")
                .strip()
            )

        company = st.text_input(
            "บริษัทเป้าหมาย (ระบุหรือไม่ก็ได้)",
            value=st.session_state.get("shared_company", ""),
            placeholder="เช่น Agoda, SCB, Line MAN Wongnai",
        )
    with col2:
        difficulty = st.selectbox("ระดับความยากของคำถาม", DIFFICULTY_LEVELS, index=1)
        q_type = st.selectbox("ประเภทของคำถาม", QUESTION_TYPES, index=0)

    num_questions = st.slider("จำนวนคำถามที่ต้องการซ้อม", min_value=1, max_value=5, value=3)

    # ปุ่มสร้างคำถาม
    if st.button("🎲 สร้างชุดคำถามสัมภาษณ์", type="primary", use_container_width=True):
        if not role.strip():
            st.error("กรุณาระบุตำแหน่งงานที่ต้องการซ้อม")
        else:
            with st.spinner("AI กำลังเตรียมคำถามสัมภาษณ์ที่ท้าทายและตรงกับตำแหน่งงาน..."):
                try:
                    questions = generate_questions_with_ai(
                        role=role,
                        company=company,
                        difficulty=difficulty,
                        q_type=q_type,
                        num_q=num_questions,
                    )
                    st.session_state["interview_session"] = {
                        "role": role,
                        "company": company,
                        "difficulty": difficulty,
                        "questions": questions,
                        "answers": [""] * len(questions),
                    }
                    st.session_state.pop("latest_interview_eval", None)
                    st.success(
                        f"สร้างคำถามสัมภาษณ์สำเร็จจำนวน {len(questions)} ข้อ! กรุณาพิมพ์คำตอบด้านล่าง"
                    )
                except AIServiceError as e:
                    st.error(f"เกิดข้อผิดพลาดจาก AI Service: {e}")
                except Exception as e:
                    logger.exception("เกิดข้อผิดพลาดในการสร้างคำถาม")
                    st.error(f"เกิดข้อผิดพลาด: {e}")

    # แสดงฟอร์มตอบคำถามเมื่อมีเซสชัน
    if "interview_session" in st.session_state:
        sess = st.session_state["interview_session"]
        st.divider()
        st.subheader(f"📝 ชุดคำถามสัมภาษณ์: {sess['role']} ({sess['difficulty']})")
        if sess["company"]:
            st.caption(f"บริษัทเป้าหมาย: **{sess['company']}**")

        answers_input = []
        for i, q_text in enumerate(sess["questions"], 1):
            st.markdown(f"**คำถามที่ {i}:** {q_text}")
            ans = st.text_area(
                f"คำตอบของคุณสำหรับข้อที่ {i}",
                value=sess["answers"][i - 1] if i - 1 < len(sess["answers"]) else "",
                placeholder="พิมพ์คำตอบของคุณที่นี่ (แนะนำให้เล่าตามหลัก: สถานการณ์ -> ปัญหา/งาน -> สิ่งที่คุณลงมือทำ -> ผลลัพธ์เชิงตัวเลข)...",
                height=130,
                key=f"ans_input_{i}",
            )
            answers_input.append(ans)

        st.session_state["interview_session"]["answers"] = answers_input

        # ปุ่มส่งคำตอบให้ประเมิน
        if st.button(
            "🚀 ส่งคำตอบและขอรับการประเมินจาก AI",
            type="secondary",
            use_container_width=True,
        ):
            if not any(a.strip() for a in answers_input):
                st.error("กรุณาพิมพ์คำตอบอย่างน้อย 1 ข้อเพื่อรับการประเมิน")
            else:
                with st.spinner("โค้ช AI กำลังอ่านคำตอบและประเมินตามหลัก STAR Method..."):
                    try:
                        eval_result = evaluate_answers_with_ai(
                            role=sess["role"],
                            questions=sess["questions"],
                            answers=answers_input,
                        )
                        st.session_state["latest_interview_eval"] = eval_result

                        # บันทึกลง SQLite
                        save_interview_session(
                            role=sess["role"],
                            company=sess["company"],
                            difficulty=sess["difficulty"],
                            questions_json=json.dumps(
                                sess["questions"], ensure_ascii=False
                            ),
                            answers_json=json.dumps(answers_input, ensure_ascii=False),
                            feedback=eval_result,
                            score=80.0,  # Default score marker
                        )
                        st.success("🎉 ประเมินผลเสร็จสิ้นและบันทึกประวัติเรียบร้อยแล้ว!")
                    except AIServiceError as e:
                        st.error(f"เกิดข้อผิดพลาดจาก AI: {e}")
                    except Exception as e:
                        logger.exception("เกิดข้อผิดพลาดในการประเมิน")
                        st.error(f"เกิดข้อผิดพลาด: {e}")

    # แสดงผลการประเมินล่าสุด
    if "latest_interview_eval" in st.session_state:
        st.divider()
        st.subheader("📑 ผลการประเมินและคำแนะนำจากโค้ชสัมภาษณ์")
        st.markdown(st.session_state["latest_interview_eval"])


def render_history_view():
    """แสดงประวัติรอบการซ้อมสัมภาษณ์ที่บันทึกไว้"""
    st.subheader("📚 ประวัติรอบการซ้อมสัมภาษณ์ที่ผ่านมา")
    sessions = get_all_interview_sessions()

    if not sessions:
        st.info("ยังไม่มีประวัติการซ้อมสัมภาษณ์ สามารถเริ่มฝึกซ้อมรอบแรกได้ที่แท็บ 'เริ่มรอบซ้อมสัมภาษณ์'")
        return

    st.write(f"พบประวัติการฝึกซ้อมทั้งหมด **{len(sessions)}** รอบ")

    for item in sessions:
        created_display = (
            format_date(item["created_at"][:10]) if item["created_at"] else "ไม่ระบุ"
        )
        company_tag = (
            f" @ {item['company']}"
            if item["company"] and item["company"] != "ไม่ระบุบริษัท"
            else ""
        )
        title_display = f"🎙️ **{item['role']}{company_tag}** ({item['difficulty']}) — เมื่อ {created_display}"

        with st.expander(title_display):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"บันทึกเมื่อ: {item['created_at']}")
            with col2:
                if st.button("🗑️ ลบประวัติรอบนี้", key=f"del_session_{item['id']}"):
                    delete_interview_session(item["id"])
                    st.toast("🗑️ ลบประวัติการซ้อมเรียบร้อยแล้ว")
                    st.rerun()

            # แสดงคำถามและคำตอบย้อนหลัง
            try:
                qs = json.loads(item["questions_json"])
                ans = json.loads(item["answers_json"])
                st.markdown("**ชุดคำถามและคำตอบที่บันทึกไว้:**")
                for i, (q, a) in enumerate(zip(qs, ans), 1):
                    st.write(f"**ข้อ {i}:** {q}")
                    st.caption(f"คำตอบ: {a or '(ไม่ได้ตอบ)'}")
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.debug(
                    f"ไม่สามารถแสดงประวัติคำถาม-ตอบของ session {item.get('id')}: {e}"
                )

            st.divider()
            st.markdown(item["feedback"])


def render_star_method_guide():
    """คู่มือเทคนิคการตอบสัมภาษณ์ตามหลัก STAR Method"""
    st.subheader("⭐ คู่มือเทคนิคการตอบสัมภาษณ์ตามหลัก STAR Method")
    st.markdown(
        """
        **STAR Method** คือเทคนิคการตอบคำถามสัมภาษณ์เชิงพฤติกรรม (Behavioral Questions) ที่ได้รับการยอมรับในระดับสากล 
        โดยเฉพาะบริษัทเทคโนโลยีชั้นนำ เช่น Google, Amazon, Microsoft และ Meta:

        ---

        #### 1. S - Situation (บริบทและสถานการณ์)
        - เกริ่นสั้นๆ ว่าคุณทำงานที่ไหน โปรเจกต์อะไร และปัญหาหรือความท้าทายที่เกิดขึ้นคืออะไร
        - *ข้อแนะนำ:* กระชับ ไม่ควรใช้เวลาเกิน 15-20% ของคำตอบทั้งหมด

        #### 2. T - Task (ภารกิจและความรับผิดชอบของคุณ)
        - อธิบายบทบาทหน้าที่เฉพาะตัวของคุณ ว่าคุณต้องรับผิดชอบแก้ไขอะไรในสถานการณ์นั้น
        - *ข้อแนะนำ:* เน้นย้ำเป้าหมายที่คุณต้องทำให้สำเร็จ

        #### 3. A - Action (การลงมือทำและการตัดสินใจ)
        - **ส่วนที่สำคัญที่สุด (ใช้เวลา 50-60%)**: คุณตัดสินใจอย่างไร ใช้เครื่องมือ/ทักษะอะไร และมีขั้นตอนแก้ปัญหาอย่างไร
        - *ข้อแนะนำ:* ใช้คำว่า *"ฉัน/ผม..." (I did)* แทนคำว่า *"พวกเรา..." (We did)* เพื่อแสดงให้เห็นบทบาทที่แท้จริงของคุณ

        #### 4. R - Result (ผลลัพธ์และความสำเร็จเชิงปริมาณ)
        - ผลลัพธ์สุดท้ายเป็นอย่างไร มีตัวเลขวัดผลได้หรือไม่ (เช่น ลดเวลาลง 40%, เพิ่มยอดขาย 25%, ระบบไม่ล่ม 99.9%)
        - *ข้อแนะนำ:* หากมีข้อคิดหรือสิ่งที่ได้เรียนรู้จากการแก้ปัญหานั้น ให้นำมาสรุปปิดท้ายด้วยเสมอ
        """
    )


def render():
    """
    จุดเริ่มต้นการแสดงผลของโมดูล Interview Coach
    """
    st.header("🎙️ ฝึกซ้อมสัมภาษณ์จำลอง (Interview Coach)")
    st.caption(
        "ฝึกซ้อมตอบคำถามสัมภาษณ์งานจริง พร้อมรับการประเมินและข้อเสนอแนะตามหลัก STAR Method"
    )

    tab_practice, tab_history, tab_star = st.tabs(
        [
            "🎙️ เริ่มรอบซ้อมสัมภาษณ์ (Practice)",
            "📚 ประวัติและการพัฒนา (Session History)",
            "⭐ คู่มือเทคนิค STAR Method (STAR Guide)",
        ]
    )

    with tab_practice:
        render_practice_session()

    with tab_history:
        render_history_view()

    with tab_star:
        render_star_method_guide()
