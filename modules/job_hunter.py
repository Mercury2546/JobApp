"""
Module 2: Job Hunter
Finds relevant job listings, builds custom search queries, and imports opportunities.
"""
import streamlit as st
from utils.logger import setup_logger

logger = setup_logger("job_hunter")


def search_jobs(keywords: str, location: str) -> list:
    """
    Core logic: queries job aggregators or search APIs.
    (Scheduled for implementation in Phase 4)
    """
    logger.info(f"Job search requested for: {keywords} in {location}")
    raise NotImplementedError("Job Hunter module will be implemented in Phase 4.")


def render():
    """
    Renders the Job Hunter interface.
    """
    st.header("🔍 Job Hunter")
    st.caption("Search, curate, and filter open opportunities tailored to your profile.")

    st.info(
        "**Module Status: Scheduled for Phase 4**\n\n"
        "This module will allow you to:\n"
        "- Query job roles across target industries and locations.\n"
        "- Parse and save relevant job listings directly into your Application Tracker.\n"
        "- Generate smart search strings for LinkedIn, Indeed, and Google Jobs."
    )

    with st.expander("Preview Interface", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Target Role / Keywords", placeholder="e.g. Senior Python Engineer", disabled=True)
        with col2:
            st.text_input("Location / Remote", placeholder="e.g. Remote, United States", disabled=True)
        st.button("Search Jobs", disabled=True, help="Will be enabled in Phase 4")
