"""Core smoke tests for helpers, database, and application tracker CRUD."""

from database import db
from modules import application_tracker as tracker
from utils.helpers import format_date, truncate_text


def _use_temp_db(monkeypatch, tmp_path):
    temp_db = tmp_path / "test_career_agent.db"
    monkeypatch.setattr(db, "DB_PATH", temp_db)
    db.init_db()
    return temp_db


def test_format_date():
    assert format_date("2026-11-25") == "25/11/2026"
    assert format_date(None) == "ไม่ระบุ"
    assert format_date("invalid") == "invalid"


def test_truncate_text():
    assert truncate_text(None) == ""
    assert truncate_text("short", max_len=10) == "short"
    assert truncate_text("hello world", max_len=8) == "hello..."


def test_db_init_and_health(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    assert db.check_db_health() is True


def test_application_crud_preserves_image_url(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)

    app_id = tracker.add_application(
        company="Acme",
        role="Python Dev",
        location="Bangkok",
        salary="60k",
        job_url="https://example.com/job",
        status="Applied",
        applied_date="2026-11-25",
        notes="test",
        image_url="https://example.com/poster.png",
    )
    apps = tracker.get_all_applications()
    assert len(apps) == 1
    assert apps[0]["id"] == app_id
    assert apps[0]["image_url"] == "https://example.com/poster.png"

    tracker.update_application(
        app_id=app_id,
        company="Acme Updated",
        role="Senior Python Dev",
        location="Remote",
        salary="80k",
        job_url="https://example.com/job",
        status="Interviewing",
        applied_date="2026-11-25",
        notes="updated",
        image_url=apps[0]["image_url"],
    )
    updated = tracker.get_all_applications()[0]
    assert updated["company"] == "Acme Updated"
    assert updated["image_url"] == "https://example.com/poster.png"

    assert tracker.delete_application(app_id) is True
    assert tracker.get_all_applications() == []
