"""
Career Agent - Main Streamlit Application Entry Point.
Modular dashboard coordinating all career intelligence services.
"""
import streamlit as st
from config.settings import OPENAI_MODEL, is_openai_configured
from database.db import init_db, check_db_health, get_db_connection
from services.ai_service import ai_service
from utils.logger import setup_logger

# Import core modules
from modules import (
    resume_analyzer,
    job_hunter,
    job_matching,
    interview_coach,
    career_planner,
    application_tracker,
)

logger = setup_logger("app")

# 1. Page Configuration
st.set_page_config(
    page_title="Career Agent | All-in-One Career Assistant",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Database Initialization
@st.cache_resource
def initialize_database():
    """Ensure database tables exist on application startup."""
    try:
        init_db()
        return True
    except Exception as e:
        logger.error(f"Database initialization failure: {e}")
        return False

db_ready = initialize_database()


def get_quick_stats():
    """Fetch summary metrics from the database."""
    stats = {
        "applications": 0,
        "resumes": 0,
        "interviews": 0,
        "goals": 0,
    }
    if not db_ready:
        return stats

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM applications;")
            stats["applications"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM resumes;")
            stats["resumes"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM interview_sessions;")
            stats["interviews"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM career_goals;")
            stats["goals"] = cursor.fetchone()[0]
    except Exception as e:
        logger.warning(f"Could not load overview stats: {e}")

    return stats


def render_dashboard_overview():
    """Renders the main overview and status dashboard."""
    st.title("💼 Career Agent Dashboard")
    st.markdown(
        "Welcome to your intelligent career command center. "
        "Track job applications, optimize resumes, practice interviews, and plan your career path in one place."
    )
    st.divider()

    # Metric Cards
    stats = get_quick_stats()
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="Active Applications", value=stats["applications"])
    with col2:
        st.metric(label="Resumes Uploaded", value=stats["resumes"])
    with col3:
        st.metric(label="Interviews Practiced", value=stats["interviews"])
    with col4:
        st.metric(label="Career Goals", value=stats["goals"])

    st.divider()

    # System Status and Roadmap Section
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("🚀 Implementation Roadmap")
        st.markdown(
            """
            | Phase | Module | Status |
            | :--- | :--- | :--- |
            | **Phase 1** | **Project Architecture & Setup** | 🟢 **Complete** |
            | **Phase 2** | **Application Tracker (CRUD & SQLite)** | 🟢 **Complete** |
            | **Phase 3** | **Resume Analyzer (AI Critique & ATS)** | 🟢 **Complete** |
            | **Phase 4** | **Job Hunter (Search & Import)** | 🟡 **Up Next** |
            | **Phase 5** | **Job Matching (Compatibility Fit)** | ⚪ Planned |
            | **Phase 6** | **Interview Coach (STAR Feedback)** | ⚪ Planned |
            | **Phase 7** | **Career Planner (Roadmaps & Goals)** | ⚪ Planned |
            """
        )

    with col_right:
        st.subheader("⚙️ System Status")
        if db_ready and check_db_health():
            st.success("🟢 SQLite Database: Connected & Healthy")
        else:
            st.error("🔴 SQLite Database: Connection Issue")

        if is_openai_configured():
            st.success(f"🟢 OpenAI API: Key Configured ({OPENAI_MODEL})")
        else:
            st.warning("🟡 OpenAI API: Key Not Configured (Add to .env)")

        with st.expander("AI Connection Test"):
            if st.button("Run Connection Ping", use_container_width=True):
                with st.spinner("Pinging OpenAI..."):
                    result = ai_service.test_connection()
                    if result["success"]:
                        st.success(result["message"])
                    else:
                        st.error(result["message"])


def main():
    # Sidebar Navigation
    st.sidebar.title("💼 Career Agent")
    st.sidebar.caption("v0.1.0 • Phase 1 Foundation")

    menu_options = [
        "Dashboard Overview",
        "1. Resume Analyzer",
        "2. Job Hunter",
        "3. Job Matching",
        "4. Interview Coach",
        "5. Career Planner",
        "6. Application Tracker",
    ]

    selected_page = st.sidebar.radio("Navigate", menu_options, index=0)

    st.sidebar.divider()
    st.sidebar.subheader("Environment")
    st.sidebar.write(f"**Model:** `{OPENAI_MODEL}`")
    st.sidebar.write(f"**DB Status:** `{'Ready' if db_ready else 'Error'}`")
    st.sidebar.write(f"**AI Key:** `{'Set' if is_openai_configured() else 'Missing'}`")

    # Routing
    try:
        if selected_page == "Dashboard Overview":
            render_dashboard_overview()
        elif selected_page == "1. Resume Analyzer":
            resume_analyzer.render()
        elif selected_page == "2. Job Hunter":
            job_hunter.render()
        elif selected_page == "3. Job Matching":
            job_matching.render()
        elif selected_page == "4. Interview Coach":
            interview_coach.render()
        elif selected_page == "5. Career Planner":
            career_planner.render()
        elif selected_page == "6. Application Tracker":
            application_tracker.render()
    except Exception as e:
        logger.error(f"Error rendering page '{selected_page}': {e}", exc_info=True)
        st.error(f"An error occurred while loading this module: {e}")


if __name__ == "__main__":
    main()
