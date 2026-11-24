# CodeGate (Career Agent)

Python + Streamlit AI career assistant app.

## Environment & Commands

- Virtualenv: `.venv` (Python 3.13)
- Run app: `.\.venv\Scripts\streamlit.exe run app.py`
- Lint: `.\.venv\Scripts\ruff.exe check .`
- Format: `.\.venv\Scripts\ruff.exe format .`

## Project Structure

- `app.py`: Main Streamlit dashboard entry point
- `config/settings.py`: Environment loader and app settings
- `database/db.py`, `database/schema.sql`: SQLite connection manager and schema
- `services/ai_service.py`, `services/notion_service.py`: OpenAI and Notion API integrations
- `modules/`: Feature modules (`resume_analyzer.py`, `job_hunter.py`, `job_matching.py`, `interview_coach.py`, `career_planner.py`, `application_tracker.py`, `email_writer.py`)
- `utils/`: `logger.py`, `helpers.py`
- `assets/`: Custom CSS (`style.css`, `light_theme.css`)

## Rules & Guardrails

1. **Secrets & Data:** Never read, print, or modify `.env`, and never delete or overwrite `career_agent.db`.
2. **Schema & Dependencies:** Ask before modifying `database/schema.sql` or adding packages to `requirements.txt`.
3. **Code Changes:** Keep edits minimal, modular, and localized; reuse existing helpers in `utils/` and services in `services/`.
4. **Verification:** Run `.\.venv\Scripts\ruff.exe check .` after editing Python files to ensure no lint or syntax issues.
