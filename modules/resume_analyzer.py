"""
Module 1: Resume Analyzer.
Analyzes resumes against industry standards and specific job descriptions using OpenAI.
Provides ATS score estimates, strength analysis, keyword gap analysis, and bullet point rewrites.
Saves analysis history to the SQLite database.
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
# Database Operations
# ==========================================

def save_resume_analysis(
    title: str,
    raw_text: str,
    file_name: str,
    analysis_summary: str,
) -> int:
    """
    Saves an analyzed resume and its AI feedback to SQLite.
    """
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
                    file_name.strip() if file_name else "Pasted Text",
                    analysis_summary.strip(),
                ),
            )
            new_id = cursor.lastrowid
            logger.info(f"Saved resume analysis ID {new_id} ('{title}')")
            return new_id
    except Exception as e:
        logger.error(f"Failed to save resume analysis: {e}", exc_info=True)
        raise


def get_all_resumes() -> List[Dict]:
    """
    Retrieves all saved resume analysis records from SQLite.
    """
    query = "SELECT * FROM resumes ORDER BY created_at DESC;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch resumes: {e}", exc_info=True)
        return []


def delete_resume_analysis(resume_id: int) -> bool:
    """
    Deletes a saved resume analysis by ID.
    """
    query = "DELETE FROM resumes WHERE id = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (resume_id,))
            logger.info(f"Deleted resume analysis ID {resume_id}")
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to delete resume analysis ID {resume_id}: {e}", exc_info=True)
        raise


# ==========================================
# Text Extraction Helpers
# ==========================================

def extract_text_from_file(uploaded_file) -> str:
    """
    Extracts text from uploaded file (.txt, .md, or .pdf).
    """
    if uploaded_file is None:
        return ""

    file_name = uploaded_file.name.lower()

    # Plain text / Markdown
    if file_name.endswith((".txt", ".md")):
        try:
            return uploaded_file.read().decode("utf-8")
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            return uploaded_file.read().decode("latin-1", errors="ignore")

    # PDF extraction
    if file_name.endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(uploaded_file)
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages).strip()
        except ImportError:
            raise AIServiceError(
                "PDF parsing library ('pypdf') is not installed. "
                "Please paste your resume text directly into the text box, or install pypdf."
            )
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise AIServiceError(f"Failed to read PDF file: {e}")

    raise AIServiceError("Unsupported file format. Please upload a .txt, .md, or .pdf file.")


# ==========================================
# Core AI Analysis Logic
# ==========================================

def analyze_resume_with_ai(resume_text: str, job_description: str = "") -> str:
    """
    Prompts OpenAI to perform an in-depth ATS critique and role-fit analysis.
    Does not use mock responses.
    """
    if not resume_text.strip():
        raise ValueError("Resume content cannot be empty.")

    system_prompt = (
        "You are an expert Executive Career Coach and Senior ATS (Applicant Tracking System) Recruiter.\n"
        "Your task is to analyze resumes rigorously and provide actionable, honest, and high-impact feedback.\n\n"
        "Format your output clearly in clean GitHub Flavored Markdown using these exact sections:\n"
        "### 1. Overall ATS & Readiness Score\n"
        "- Provide an estimated ATS Compatibility Score from 0 to 100 with a 2-sentence rationale.\n\n"
        "### 2. Key Strengths\n"
        "- 3 to 4 standout qualities, achievements, or structural strengths.\n\n"
        "### 3. Critical Weaknesses & Red Flags\n"
        "- Vague bullet points, missing metrics, formatting hazards, or weak action verbs.\n\n"
        "### 4. Keyword & Skill Gap Analysis\n"
        "- Must-have skills identified (and missing skills if a Job Description was provided).\n\n"
        "### 5. Actionable Rewrites (Before vs. After)\n"
        "- Pick 2 to 3 actual bullet points from the resume and rewrite them using the XYZ formula: "
        "'Accomplished [X] as measured by [Y], by doing [Z]'."
    )

    jd_context = (
        f"\n\n--- TARGET JOB DESCRIPTION ---\n{job_description.strip()}"
        if job_description.strip()
        else "\n\n(No specific job description provided. Evaluate against general industry excellence.)"
    )

    user_prompt = f"--- CANDIDATE RESUME ---\n{resume_text.strip()}{jd_context}"

    logger.info("Sending resume to OpenAI for ATS evaluation.")
    return ai_service.generate_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.3,
    )


# ==========================================
# Streamlit UI Views
# ==========================================

def render_new_analysis_view():
    """Renders the resume upload and AI analysis interface."""
    st.subheader("🔍 New Resume Evaluation")
    st.write("Upload or paste your resume to receive an AI ATS score, skill gap review, and bullet-point rewrites.")

    if not is_openai_configured():
        st.warning(
            "⚠️ **OpenAI API Key is not set in `.env`**\n\n"
            "To generate real AI critiques, please add your `OPENAI_API_KEY` to the `.env` file in the project folder."
        )

    col_title, col_file = st.columns([1, 1])
    with col_title:
        title = st.text_input("Resume Profile Name *", placeholder="e.g. Senior Backend Resume 2026", value="My Resume")
    with col_file:
        uploaded_file = st.file_uploader("Upload Resume File (.txt, .md, .pdf)", type=["txt", "md", "pdf"])

    # If file was uploaded, attempt to read text into session
    extracted_text = ""
    file_name = ""
    if uploaded_file is not None:
        file_name = uploaded_file.name
        try:
            extracted_text = extract_text_from_file(uploaded_file)
            st.success(f"Loaded '{file_name}' ({len(extracted_text)} characters)")
        except Exception as e:
            st.error(str(e))

    # Text areas for resume & target JD
    resume_input = st.text_area(
        "Resume Text *",
        value=extracted_text,
        height=220,
        placeholder="Paste your full resume text here if not uploading a file...",
    )

    with st.expander("🎯 Target Job Description (Optional but Recommended)", expanded=False):
        job_description = st.text_area(
            "Target Job Description",
            height=150,
            placeholder="Paste the job description here to check ATS match and keyword compatibility...",
        )

    # Analyze Button
    if st.button("🚀 Analyze Resume with AI", type="primary", use_container_width=True):
        final_text = resume_input.strip() or extracted_text.strip()
        if not final_text:
            st.error("Please provide your resume text either by uploading a file or pasting it.")
        elif not title.strip():
            st.error("Please provide a name/title for this resume.")
        else:
            with st.spinner("Analyzing resume against ATS criteria via OpenAI..."):
                try:
                    analysis_result = analyze_resume_with_ai(final_text, job_description)
                    st.session_state["latest_analysis"] = {
                        "title": title,
                        "raw_text": final_text,
                        "file_name": file_name,
                        "result": analysis_result,
                    }
                    # Automatically save to SQLite
                    save_resume_analysis(
                        title=title,
                        raw_text=final_text,
                        file_name=file_name,
                        analysis_summary=analysis_result,
                    )
                    st.success("Analysis complete and saved to database!")
                except AIServiceError as e:
                    st.error(f"AI Service Error: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error analyzing resume: {e}", exc_info=True)
                    st.error(f"An unexpected error occurred: {e}")

    # Display Latest Result if present in session state
    if "latest_analysis" in st.session_state:
        latest = st.session_state["latest_analysis"]
        st.divider()
        st.subheader(f"📊 Evaluation Report: {latest['title']}")
        st.markdown(latest["result"])


def render_history_view():
    """Renders the saved analysis records from SQLite."""
    st.subheader("📚 Saved Resume Analyses")
    resumes = get_all_resumes()

    if not resumes:
        st.info("No saved resume analyses yet. Run an analysis in the 'New Evaluation' tab to view it here.")
        return

    st.write(f"Total Saved Analyses: **{len(resumes)}**")

    for item in resumes:
        with st.expander(f"📄 **{item['title']}** (Saved on {format_date(item['created_at'][:10])})"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"Source: {item['file_name']} • Created: {item['created_at']}")
            with col2:
                if st.button("🗑️ Delete", key=f"del_resume_{item['id']}"):
                    delete_resume_analysis(item["id"])
                    st.success("Deleted analysis report.")
                    st.rerun()

            st.divider()
            st.markdown(item["analysis_summary"])


def render():
    """
    Main render entry point for Resume Analyzer module.
    """
    st.header("📄 Resume Analyzer")
    st.caption("AI-powered resume evaluation, ATS readiness scoring, and bullet-point rewrites.")

    tab_analyze, tab_history = st.tabs([
        "🔍 New Evaluation",
        "📚 Analysis History",
    ])

    with tab_analyze:
        render_new_analysis_view()

    with tab_history:
        render_history_view()
