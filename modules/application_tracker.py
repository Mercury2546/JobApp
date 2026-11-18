"""
Module 6: Application Tracker.
Provides full CRUD capabilities for tracking job applications across the hiring pipeline.
Stores and updates records directly in the SQLite database.
"""
from datetime import date
from typing import Dict, List, Optional
import streamlit as st
from database.db import get_db_connection
from utils.helpers import format_date, get_current_date_str
from utils.logger import setup_logger

logger = setup_logger("application_tracker")

# Pipeline status choices
VALID_STATUSES = ["Wishlist", "Applied", "Interviewing", "Offered", "Rejected"]

STATUS_BADGES = {
    "Wishlist": "📌 Wishlist",
    "Applied": "📨 Applied",
    "Interviewing": "🎙️ Interviewing",
    "Offered": "🎉 Offered",
    "Rejected": "❌ Rejected",
}


# ==========================================
# Database Operations (CRUD)
# ==========================================

def add_application(
    company: str,
    role: str,
    location: str = "",
    salary: str = "",
    job_url: str = "",
    status: str = "Wishlist",
    applied_date: str = "",
    notes: str = "",
) -> int:
    """
    Inserts a new job application into the database.
    """
    if status not in VALID_STATUSES:
        status = "Wishlist"

    query = """
    INSERT INTO applications (company, role, location, salary, job_url, status, applied_date, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    company.strip(),
                    role.strip(),
                    location.strip(),
                    salary.strip(),
                    job_url.strip(),
                    status,
                    applied_date,
                    notes.strip(),
                ),
            )
            new_id = cursor.lastrowid
            logger.info(f"Added new application (ID: {new_id}) for {company} - {role}")
            return new_id
    except Exception as e:
        logger.error(f"Failed to add application: {e}", exc_info=True)
        raise


def get_all_applications(status_filter: Optional[str] = None, search_term: Optional[str] = None) -> List[Dict]:
    """
    Retrieves applications from the database with optional status filtering and keyword search.
    """
    query = "SELECT * FROM applications WHERE 1=1"
    params: list = []

    if status_filter and status_filter in VALID_STATUSES:
        query += " AND status = ?"
        params.append(status_filter)

    if search_term and search_term.strip():
        term = f"%{search_term.strip()}%"
        query += " AND (company LIKE ? OR role LIKE ? OR location LIKE ? OR notes LIKE ?)"
        params.extend([term, term, term, term])

    query += " ORDER BY updated_at DESC, id DESC;"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch applications: {e}", exc_info=True)
        return []


def update_application(
    app_id: int,
    company: str,
    role: str,
    location: str,
    salary: str,
    job_url: str,
    status: str,
    applied_date: str,
    notes: str,
) -> bool:
    """
    Updates all fields of an existing application.
    """
    if status not in VALID_STATUSES:
        status = "Wishlist"

    query = """
    UPDATE applications
    SET company = ?, role = ?, location = ?, salary = ?, job_url = ?, status = ?, applied_date = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?;
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    company.strip(),
                    role.strip(),
                    location.strip(),
                    salary.strip(),
                    job_url.strip(),
                    status,
                    applied_date,
                    notes.strip(),
                    app_id,
                ),
            )
            logger.info(f"Updated application ID {app_id}")
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update application ID {app_id}: {e}", exc_info=True)
        raise


def update_application_status(app_id: int, new_status: str) -> bool:
    """
    Quick status transition for pipeline boards.
    """
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")

    query = "UPDATE applications SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (new_status, app_id))
            logger.info(f"Updated status for application ID {app_id} to {new_status}")
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update status for application ID {app_id}: {e}", exc_info=True)
        raise


def delete_application(app_id: int) -> bool:
    """
    Deletes an application by ID.
    """
    query = "DELETE FROM applications WHERE id = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (app_id,))
            logger.info(f"Deleted application ID {app_id}")
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to delete application ID {app_id}: {e}", exc_info=True)
        raise


def get_status_counts() -> Dict[str, int]:
    """
    Returns counts for each status to populate pipeline metrics.
    """
    counts = {s: 0 for s in VALID_STATUSES}
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) as cnt FROM applications GROUP BY status;")
            for row in cursor.fetchall():
                if row["status"] in counts:
                    counts[row["status"]] = row["cnt"]
    except Exception as e:
        logger.error(f"Failed to get status counts: {e}")
    return counts


# ==========================================
# Streamlit UI Views
# ==========================================

def render_add_application_form():
    """Form view to add a new job application."""
    st.subheader("➕ Track a New Job Application")
    st.write("Record a new opportunity in your pipeline.")

    with st.form("add_application_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input("Company Name *", placeholder="e.g. Acme Corp")
            role = st.text_input("Job Title / Role *", placeholder="e.g. Senior Software Engineer")
            location = st.text_input("Location", placeholder="e.g. Remote, New York, NY")
        with col2:
            status = st.selectbox("Current Status", VALID_STATUSES, index=0)
            salary = st.text_input("Salary / Compensation", placeholder="e.g. $130,000 - $150,000")
            applied_date = st.date_input("Date Applied", value=date.today())

        job_url = st.text_input("Job Posting URL", placeholder="https://linkedin.com/jobs/view/...")
        notes = st.text_area("Notes & Interview Contacts", placeholder="Recruiter name, referral info, notes...")

        submitted = st.form_submit_button("Save Application", use_container_width=True)

        if submitted:
            if not company.strip() or not role.strip():
                st.error("Please fill in both Company Name and Job Title.")
            else:
                try:
                    add_application(
                        company=company,
                        role=role,
                        location=location,
                        salary=salary,
                        job_url=job_url,
                        status=status,
                        applied_date=str(applied_date),
                        notes=notes,
                    )
                    st.success(f"Application for **{role}** at **{company}** saved successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save application: {e}")


def render_pipeline_view():
    """Kanban-style column view of applications by status."""
    st.subheader("📊 Hiring Pipeline (Kanban Board)")
    counts = get_status_counts()

    # Metric summary row
    cols = st.columns(len(VALID_STATUSES))
    for i, st_name in enumerate(VALID_STATUSES):
        with cols[i]:
            st.metric(label=st_name, value=counts[st_name])

    st.divider()

    # Column board
    kanban_cols = st.columns(len(VALID_STATUSES))
    for idx, st_name in enumerate(VALID_STATUSES):
        with kanban_cols[idx]:
            st.markdown(f"#### {STATUS_BADGES[st_name]}")
            apps_in_stage = get_all_applications(status_filter=st_name)

            if not apps_in_stage:
                st.caption("No applications in this stage.")
            else:
                for app in apps_in_stage:
                    with st.container(border=True):
                        st.markdown(f"**{app['company']}**")
                        st.write(f"💼 {app['role']}")
                        if app["location"]:
                            st.caption(f"📍 {app['location']}")
                        if app["salary"]:
                            st.caption(f"💰 {app['salary']}")
                        if app["applied_date"]:
                            st.caption(f"📅 {format_date(app['applied_date'])}")

                        # Quick Move Dropdown
                        current_idx = VALID_STATUSES.index(app["status"])
                        new_status = st.selectbox(
                            "Move to",
                            VALID_STATUSES,
                            index=current_idx,
                            key=f"move_{app['id']}",
                            label_visibility="collapsed",
                        )
                        if new_status != app["status"]:
                            update_application_status(app["id"], new_status)
                            st.rerun()


def render_list_view():
    """Searchable, filterable list of all job applications with edit/delete actions."""
    st.subheader("📋 Application Directory")

    col_search, col_filter = st.columns([3, 1])
    with col_search:
        search_query = st.text_input("🔍 Search by company, role, or keywords", placeholder="Type to filter...")
    with col_filter:
        filter_status = st.selectbox("Filter Status", ["All"] + VALID_STATUSES)

    selected_status = None if filter_status == "All" else filter_status
    applications = get_all_applications(status_filter=selected_status, search_term=search_query)

    st.write(f"Showing **{len(applications)}** applications")

    if not applications:
        st.info("No matching applications found. Use the 'Add Application' tab to record one.")
        return

    for app in applications:
        with st.expander(f"{STATUS_BADGES.get(app['status'], app['status'])} — **{app['company']}** : {app['role']}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Company:** {app['company']}")
                st.write(f"**Role:** {app['role']}")
                st.write(f"**Location:** {app['location'] or 'Not specified'}")
                st.write(f"**Salary:** {app['salary'] or 'Not specified'}")
            with col2:
                st.write(f"**Status:** {app['status']}")
                st.write(f"**Date Applied:** {format_date(app['applied_date'])}")
                if app["job_url"]:
                    st.markdown(f"**Posting URL:** [View Posting]({app['job_url']})")
                st.write(f"**Created:** {app['created_at']}")

            if app["notes"]:
                st.info(f"**Notes:**\n\n{app['notes']}")

            # Edit and Delete buttons
            bcol1, bcol2, _ = st.columns([1, 1, 4])
            with bcol1:
                if st.button("✏️ Edit", key=f"edit_btn_{app['id']}"):
                    st.session_state["edit_app_id"] = app["id"]
                    st.rerun()
            with bcol2:
                if st.button("🗑️ Delete", key=f"del_btn_{app['id']}", type="secondary"):
                    delete_application(app["id"])
                    st.success(f"Deleted application for {app['company']}.")
                    st.rerun()


def render_edit_view(app_id: int):
    """View to edit an existing application record."""
    st.subheader(f"✏️ Edit Application #{app_id}")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM applications WHERE id = ?;", (app_id,))
            row = cursor.fetchone()
            if not row:
                st.error("Application not found.")
                if st.button("Back to List"):
                    st.session_state.pop("edit_app_id", None)
                    st.rerun()
                return
            app = dict(row)
    except Exception as e:
        st.error(f"Error loading application: {e}")
        return

    with st.form(f"edit_form_{app_id}"):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input("Company Name *", value=app["company"])
            role = st.text_input("Job Title / Role *", value=app["role"])
            location = st.text_input("Location", value=app["location"] or "")
        with col2:
            status_index = VALID_STATUSES.index(app["status"]) if app["status"] in VALID_STATUSES else 0
            status = st.selectbox("Current Status", VALID_STATUSES, index=status_index)
            salary = st.text_input("Salary / Compensation", value=app["salary"] or "")
            applied_date = st.text_input("Date Applied (YYYY-MM-DD)", value=app["applied_date"] or get_current_date_str())

        job_url = st.text_input("Job Posting URL", value=app["job_url"] or "")
        notes = st.text_area("Notes", value=app["notes"] or "")

        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            save_clicked = st.form_submit_button("Update Application", use_container_width=True)
        with sub_col2:
            cancel_clicked = st.form_submit_button("Cancel", use_container_width=True)

        if save_clicked:
            if not company.strip() or not role.strip():
                st.error("Company Name and Role cannot be empty.")
            else:
                update_application(
                    app_id=app_id,
                    company=company,
                    role=role,
                    location=location,
                    salary=salary,
                    job_url=job_url,
                    status=status,
                    applied_date=applied_date,
                    notes=notes,
                )
                st.session_state.pop("edit_app_id", None)
                st.success("Application updated successfully!")
                st.rerun()

        if cancel_clicked:
            st.session_state.pop("edit_app_id", None)
            st.rerun()


def render():
    """
    Main render entry point for the Application Tracker module.
    """
    st.header("📋 Application Tracker")
    st.caption("Organize and manage your full recruitment pipeline in SQLite.")

    # Check if user is currently editing a specific application
    edit_id = st.session_state.get("edit_app_id")
    if edit_id:
        render_edit_view(edit_id)
        return

    # Tabs for main views
    tab_pipeline, tab_list, tab_add = st.tabs([
        "📊 Pipeline (Kanban)",
        "📋 Directory & Search",
        "➕ Add New Application",
    ])

    with tab_pipeline:
        render_pipeline_view()

    with tab_list:
        render_list_view()

    with tab_add:
        render_add_application_form()
