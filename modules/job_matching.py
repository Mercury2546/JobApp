"""
Module 3: Job Matching
Calculates compatibility scores between candidate profiles and job requirements.
"""
import streamlit as st
from utils.logger import setup_logger

logger = setup_logger("job_matching")


def calculate_match_score(resume_text: str, job_description: str) -> dict:
    """
    Core logic: compares candidate skills against job requirements.
    (Scheduled for implementation in Phase 5)
    """
    logger.info("Match scoring requested.")
    raise NotImplementedError("Job Matching module will be implemented in Phase 5.")


def render():
    """
    Renders the Job Matching interface.
    """
    st.header("🎯 Job Matching")
    st.caption("AI-driven compatibility scoring, missing skill detection, and match breakdown.")

    st.info(
        "**Module Status: Scheduled for Phase 5**\n\n"
        "This module will allow you to:\n"
        "- Assess your match percentage against any job posting.\n"
        "- Identify must-have vs. nice-to-have skill gaps.\n"
        "- Generate tailored talking points to bridge gaps in interviews."
    )

    with st.expander("Preview Interface", expanded=True):
        st.text_area("Job Description", placeholder="Paste the job description here...", disabled=True)
        st.button("Calculate Match", disabled=True, help="Will be enabled in Phase 5")
