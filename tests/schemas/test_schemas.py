"""Tests for Pydantic schemas — validation and serialization."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.ticket import TicketBase, TicketCreate, TicketRead, TicketUpdate
from app.schemas.knowledge_base import KBArticleBase, KBArticleCreate, KBArticleRead, KBArticleUpdate
from app.schemas.user import UserLogin, UserCreate, UserRead, Token, TokenData
from app.schemas.analytics import AnalyticsSummary, DeviceCount, TimelinePoint


# ---------------------------------------------------------------------------
# Ticket schemas
# ---------------------------------------------------------------------------


class TestTicketSchemas:
    def test_ticket_create_minimal(self):
        tc = TicketCreate(
            email_from="test@test.com",
            subject="Subject",
            body="Body",
        )
        assert tc.email_from == "test@test.com"
        assert tc.email_to is None

    def test_ticket_create_full(self):
        tc = TicketCreate(
            email_from="test@test.com",
            email_to="support@eriskip.com",
            subject="Subject",
            body="Body",
        )
        assert tc.email_to == "support@eriskip.com"

    def test_ticket_update_partial(self):
        tu = TicketUpdate(status="closed")
        dumped = tu.model_dump(exclude_unset=True)
        assert dumped == {"status": "closed"}

    def test_ticket_update_empty(self):
        tu = TicketUpdate()
        dumped = tu.model_dump(exclude_unset=True)
        assert dumped == {}

    def test_ticket_update_multiple_fields(self):
        tu = TicketUpdate(
            status="responded",
            response="Ответ",
            category="неисправность",
            priority="high",
        )
        dumped = tu.model_dump(exclude_unset=True)
        assert len(dumped) == 4

    def test_ticket_read_from_attributes(self):
        """TicketRead can be populated from ORM-like objects."""
        data = {
            "id": 1,
            "email_from": "test@test.com",
            "email_to": None,
            "subject": "Sub",
            "body": "Body",
            "fio": None,
            "organization": None,
            "phone": None,
            "serial_numbers": None,
            "device_type": None,
            "description": None,
            "category": "прочее",
            "priority": "low",
            "sentiment": "нейтраль",
            "confidence": 0.5,
            "entities": {},
            "response": None,
            "kb_article_id": None,
            "status": "new",
            "is_auto": True,
            "created_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
            "responded_at": None,
        }
        tr = TicketRead.model_validate(data)
        assert tr.id == 1
        assert tr.status == "new"

    def test_ticket_create_missing_required_fields(self):
        with pytest.raises(Exception):
            TicketCreate(email_from="test@test.com")  # missing subject, body


# ---------------------------------------------------------------------------
# Knowledge Base schemas
# ---------------------------------------------------------------------------


class TestKBSchemas:
    def test_kb_article_create_defaults(self):
        ka = KBArticleCreate(category="test", question="Q", answer="A")
        assert ka.source_type == "official_docs"
        assert ka.priority == 10

    def test_kb_article_create_custom(self):
        ka = KBArticleCreate(
            category="test", question="Q", answer="A",
            source_type="support_history", priority=1,
        )
        assert ka.source_type == "support_history"
        assert ka.priority == 1

    def test_kb_article_update_partial(self):
        update = KBArticleUpdate(is_active=False)
        dumped = update.model_dump(exclude_unset=True)
        assert dumped == {"is_active": False}


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------


class TestUserSchemas:
    def test_user_login_validation(self):
        ul = UserLogin(username="admin", password="pass1234")
        assert ul.username == "admin"

    def test_user_login_password_too_short(self):
        with pytest.raises(Exception):
            UserLogin(username="admin", password="ab")

    def test_user_create_with_full_name(self):
        uc = UserCreate(username="admin", password="pass1234", full_name="Admin User")
        assert uc.full_name == "Admin User"

    def test_user_create_default_full_name(self):
        uc = UserCreate(username="admin", password="pass1234")
        assert uc.full_name == ""

    def test_token_schema(self):
        t = Token(access_token="abc123")
        assert t.token_type == "bearer"

    def test_token_data(self):
        td = TokenData(username="user")
        assert td.username == "user"


# ---------------------------------------------------------------------------
# Analytics schemas
# ---------------------------------------------------------------------------


class TestAnalyticsSchemas:
    def test_analytics_summary(self):
        s = AnalyticsSummary(
            total_tickets=10,
            by_category={"прочее": 10},
            by_sentiment={"нейтраль": 10},
            by_status={"new": 10},
            avg_response_time_minutes=5.0,
            auto_response_rate=0.5,
            top_devices=[DeviceCount(device="ДГС", count=5)],
        )
        assert s.total_tickets == 10

    def test_timeline_point(self):
        tp = TimelinePoint(date="2026-03-01", count=10, auto=7, manual=3)
        assert tp.auto + tp.manual == tp.count

    def test_device_count(self):
        dc = DeviceCount(device="СЕНСОН", count=3)
        assert dc.device == "СЕНСОН"
