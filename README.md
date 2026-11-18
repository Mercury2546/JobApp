# 💼 Career Agent

An intelligent, modular, AI-powered personal career assistant built in Python and Streamlit. Career Agent guides job seekers through their entire job hunt and career progression lifecycle.

---

## 🌟 Core Features & Modules

1. **📄 Resume Analyzer**: AI-driven critique, bullet-point refinement, and ATS readability check against target job descriptions.
2. **🔍 Job Hunter**: Automated job search query creation and opportunity tracking.
3. **🎯 Job Matching**: Quantitative compatibility scoring and skill gap identification.
4. **🎙️ Interview Coach**: Dynamic mock interview question generation with STAR-method answer evaluation.
5. **📈 Career Planner**: Long-term career progression milestones, skill roadmaps, and transition tracking.
6. **📋 Application Tracker**: Pipeline management across application stages (Wishlist → Applied → Interviewing → Offered / Rejected).

---

## 🏗️ Project Architecture

```
career_agent/
│
├── .env.example              # Template for environment variables (OpenAI API key, DB path)
├── .gitignore                # Git ignore rules for virtual environments, secrets, DB, logs
├── README.md                 # Setup and documentation
├── requirements.txt          # Python dependencies (Streamlit, OpenAI, python-dotenv)
├── app.py                    # Main Streamlit dashboard application
│
├── config/
│   ├── __init__.py
│   └── settings.py           # Environment loader and application configuration
│
├── database/
│   ├── __init__.py
│   ├── db.py                 # SQLite connection manager and initialization logic
│   └── schema.sql            # Table definitions (applications, resumes, interviews, goals)
│
├── services/
│   ├── __init__.py
│   └── ai_service.py         # Configurable OpenAI service with error handling & logging
│
├── modules/                  # Modular implementations for each feature
│   ├── __init__.py
│   ├── resume_analyzer.py    # Module 1: Resume evaluation
│   ├── job_hunter.py         # Module 2: Job search
│   ├── job_matching.py       # Module 3: Fit scoring
│   ├── interview_coach.py    # Module 4: Mock interviews
│   ├── career_planner.py     # Module 5: Roadmaps
│   └── application_tracker.py# Module 6: Application tracking
│
└── utils/
    ├── __init__.py
    ├── logger.py             # Dual console & file logger
    └── helpers.py            # Utility functions (date formatting, text truncation)
```

---

## 📁 File Purpose Overview

| File / Folder | Purpose |
| :--- | :--- |
| **`app.py`** | Primary application entry point. Coordinates navigation, system health checks, summary metrics, and renders module views. |
| **`config/settings.py`** | Centralizes configuration, parses `.env`, detects missing keys, and sets file paths. |
| **`database/schema.sql`** | SQL DDL script defining tables: `applications`, `resumes`, `interview_sessions`, and `career_goals`. |
| **`database/db.py`** | Manages SQLite connection pooling, executes schema migrations, and provides safe database context managers. |
| **`services/ai_service.py`** | Wrapper around the OpenAI API with custom exception handling (`AuthenticationError`, `RateLimitError`), logging, and token limits. |
| **`modules/*.py`** | Dedicated, self-contained business logic and UI render functions for each of the 6 core features. |
| **`utils/logger.py`** | Configures Python's standard `logging` module to output to both console and `logs/career_agent.log`. |
| **`utils/helpers.py`** | General-purpose helper functions for formatting dates, truncating text, etc. |
| **`.env.example`** | Safe template for API keys and configuration parameters. |
| **`requirements.txt`** | Dependency manifest specifying library versions. |

---

## 🚀 Quickstart & Setup Instructions

### 1. Prerequisites
- **Python 3.10+** installed on your system.
- An **OpenAI API Key** (optional for initial setup, but required for AI features).

### 2. Clone / Open Project
Navigate to the project root directory:
```bash
cd Career Agent
```

### 3. Create and Activate a Virtual Environment
```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to create your active `.env` file:
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```
Open `.env` and set your OpenAI API key:
```ini
OPENAI_API_KEY=sk-your-actual-openai-api-key
OPENAI_MODEL=gpt-4o-mini
DB_PATH=career_agent.db
LOG_LEVEL=INFO
```

### 6. Run the Application
Launch the Streamlit web dashboard:
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 🔒 Security Best Practices
- **No Hardcoded Keys**: API keys are exclusively read from `.env` or system environment variables.
- **Git Protection**: `.gitignore` prevents `.env`, `*.db`, and log files from being checked into version control.
- **True AI Execution**: The system cleanly reports when keys are missing or invalid rather than simulating mock AI responses as real results.

---

## 🗺️ Implementation Roadmap
- [x] **Phase 1: Project Architecture & Setup** (Foundation, SQLite DB, AI Service Layer, Dashboard Layout)
- [x] **Phase 2: Application Tracker** (SQLite CRUD operations, status management, pipeline view)
- [x] **Phase 3: Resume Analyzer** (File parser, prompt templates, ATS scoring)
- [x] **Phase 4: Job Hunter** (Search query builder, listing capture)
- [x] **Phase 5: Job Matching** (Resume vs. Job Description matching)
- [x] **Phase 6: Interview Coach** (Interactive mock interview Q&A with evaluation)
- [x] **Phase 7: Career Planner** (Career goal milestones and learning roadmaps)
