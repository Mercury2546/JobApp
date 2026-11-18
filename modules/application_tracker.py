"""
Module 6: Application Tracker
Tracks job applications across their lifecycle (Wishlist -> Applied -> Interviewing -> Offered/Rejected).
(Next Phase: Phase 2)
"""
import streamlit as st
from database.db import get_db_connection
from utils.logger import setup_logger

logger = setup_logger("application_tracker")


def get_all_applications():
    """
    Fetch all tracked job applications from the SQLite database.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM applications ORDER BY created_at DESC;")
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to fetch applications: {e}")
        return []


def render():
    """
    Renders the Application Tracker interface.
    """
    st.header("📋 Application Tracker")
    st.caption("Manage your job search pipeline, deadlines, and application statuses.")

    st.info(
        "**Module Status: Up Next in Phase 2**\n\n"
        "This module will allow you to:\n"
        "- Add, edit, and delete job applications.\n"
        "- Track statuses across a Kanban-style pipeline (Wishlist, Applied, Interviewing, Offered, Rejected).\n"
        "- Filter and search your active applications."
    )

    # Display current application records if any exist in the database
    apps = get_all_applications()
    st.subheader(f"Saved Applications ({len(apps)})")

    if not apps:
        st.write("No job applications tracked yet. You can add them once Phase 2 is activated.")
    else:
        for app in apps:
            with st.container():
                st.write(f"**{app['company']}** — {app['role']} ({app['status']})")
