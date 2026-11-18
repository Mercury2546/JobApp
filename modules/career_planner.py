"""
Module 5: Career Planner
Helps users map out long-term career roadmaps, skill upgrades, and career milestones.
"""
import streamlit as st
from utils.logger import setup_logger

logger = setup_logger("career_planner")


def generate_career_roadmap(current_role: str, target_role: str, timeline_months: int = 12) -> dict:
    """
    Core logic: creates strategic career progression plans with concrete milestones.
    (Scheduled for implementation in Phase 7)
    """
    logger.info(f"Career roadmap planned from {current_role} to {target_role}")
    raise NotImplementedError("Career Planner module will be implemented in Phase 7.")


def render():
    """
    Renders the Career Planner interface.
    """
    st.header("📈 Career Planner")
    st.caption("Strategic roadmap planning, skill acquisition paths, and career milestones.")

    st.info(
        "**Module Status: Scheduled for Phase 7**\n\n"
        "This module will allow you to:\n"
        "- Define your target career milestones and transition goals.\n"
        "- Receive sequenced monthly roadmaps to transition into higher-level roles.\n"
        "- Save and review goals inside the SQLite database."
    )

    with st.expander("Preview Interface", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Current Role", placeholder="e.g. Junior Developer", disabled=True)
        with col2:
            st.text_input("Target Role", placeholder="e.g. Staff Engineer / Tech Lead", disabled=True)
        st.button("Generate Roadmap", disabled=True, help="Will be enabled in Phase 7")
