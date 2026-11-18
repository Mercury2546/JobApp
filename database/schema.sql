-- Schema definition for Career Agent database

-- Job Applications Table
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    location TEXT,
    salary TEXT,
    job_url TEXT,
    status TEXT NOT NULL DEFAULT 'Wishlist' CHECK(status IN ('Wishlist', 'Applied', 'Interviewing', 'Offered', 'Rejected')),
    applied_date TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resumes Table
CREATE TABLE IF NOT EXISTS resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    raw_text TEXT,
    file_name TEXT,
    analysis_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Mock Interview Sessions Table
CREATE TABLE IF NOT EXISTS interview_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    company TEXT,
    difficulty TEXT DEFAULT 'Medium',
    questions_json TEXT,
    answers_json TEXT,
    feedback TEXT,
    score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Career Goals & Milestones Table
CREATE TABLE IF NOT EXISTS career_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    target_role TEXT,
    target_date TEXT,
    status TEXT DEFAULT 'In Progress' CHECK(status IN ('In Progress', 'Completed', 'Archived')),
    milestones_json TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
