"""Tests for app/services/email_service.py — email parsing, IMAP, SMTP."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.email_service import IncomingEmail, parse_email_message, send_reply, fetch_new_emails


# ---------------------------------------------------------------------------
# parse_email_message — plain text email
# ---------------------------------------------------------------------------


class TestParseEmailMessage:
    def _build_raw_email(
        self,
        subject: str = "Test Subject",
        sender: str = "Иванов Иван <ivanov@example.com>",
        to: str = "support@eriskip.com",
        body: str = "Прибор не работает.",
        message_id: str = "<msg001@example.com>",
    ) -> bytes:
        raw = (
            f"Message-ID: {message_id}\r\n"
            f"From: {sender}\r\n"
            f"To: {to}\r\n"
            f"Subject: {subject}\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n"
            f"Date: Mon, 01 Mar 2026 10:00:00 +0000\r\n"
            f"\r\n"
            f"{body}\r\n"
        )
        return raw.encode("utf-8")

    def test_parses_basic_fields(self):
        raw = self._build_raw_email()
        result = parse_email_message(raw)
        assert isinstance(result, IncomingEmail)
        assert result.subject == "Test Subject"
        assert "Прибор не работает" in result.body
        assert result.message_id == "<msg001@example.com>"

    def test_parses_sender_name(self):
        raw = self._build_raw_email(sender="Иванов Иван <ivanov@example.com>")
        result = parse_email_message(raw)
        assert result.sender_name == "Иванов Иван"

    def test_parses_sender_without_name(self):
        raw = self._build_raw_email(sender="ivanov@example.com")
        result = parse_email_message(raw)
        assert result.sender_name == ""

    def test_parses_recipient(self):
        raw = self._build_raw_email(to="support@eriskip.com")
        result = parse_email_message(raw)
        assert result.recipient == "support@eriskip.com"

    def test_empty_body(self):
        raw = self._build_raw_email(body="")
        result = parse_email_message(raw)
        assert result.body is not None  # empty but not None

    def test_no_attachments_for_plain_text(self):
        raw = self._build_raw_email()
        result = parse_email_message(raw)
        assert result.attachments == []


class TestParseMultipartEmail:
    def test_multipart_with_attachment(self):
        boundary = "----=_Part_12345"
        raw = (
            f"Message-ID: <multi@test.com>\r\n"
            f"From: test@test.com\r\n"
            f"To: support@eriskip.com\r\n"
            f"Subject: With attachment\r\n"
            f"MIME-Version: 1.0\r\n"
            f"Content-Type: multipart/mixed; boundary=\"{boundary}\"\r\n"
            f"\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n"
            f"\r\n"
            f"Текст письма.\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: application/pdf\r\n"
            f"Content-Disposition: attachment; filename=\"doc.pdf\"\r\n"
            f"Content-Transfer-Encoding: base64\r\n"
            f"\r\n"
            f"JVBERi0xLjQK\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        result = parse_email_message(raw)
        assert "Текст письма" in result.body
        assert len(result.attachments) == 1
        assert result.attachments[0].filename == "doc.pdf"
        assert result.attachments[0].content_type == "application/pdf"


# ---------------------------------------------------------------------------
# send_reply — SMTP
# ---------------------------------------------------------------------------


class TestSendReply:
    @pytest.mark.asyncio
    async def test_not_configured(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.smtp_user = ""
            mock_settings.smtp_password = ""
            result = await send_reply("to@test.com", "Sub", "Body")
        assert result is False

    @pytest.mark.asyncio
    async def test_success(self):
        with (
            patch("app.services.email_service.settings") as mock_settings,
            patch("app.services.email_service.aiosmtplib.send", new_callable=AsyncMock) as mock_send,
        ):
            mock_settings.smtp_user = "bot@eriskip.com"
            mock_settings.smtp_password = "pass"
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 465
            result = await send_reply("to@test.com", "Sub", "Body")
        assert result is True
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failure_after_retries(self):
        with (
            patch("app.services.email_service.settings") as mock_settings,
            patch("app.services.email_service.aiosmtplib.send", new_callable=AsyncMock, side_effect=Exception("SMTP error")),
        ):
            mock_settings.smtp_user = "bot@eriskip.com"
            mock_settings.smtp_password = "pass"
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 465
            result = await send_reply("to@test.com", "Sub", "Body")
        assert result is False

    @pytest.mark.asyncio
    async def test_adds_re_prefix(self):
        with (
            patch("app.services.email_service.settings") as mock_settings,
            patch("app.services.email_service.aiosmtplib.send", new_callable=AsyncMock) as mock_send,
        ):
            mock_settings.smtp_user = "bot@eriskip.com"
            mock_settings.smtp_password = "pass"
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 465
            await send_reply("to@test.com", "Subject", "Body")
        # The EmailMessage passed to send should have Re: prefix
        sent_msg = mock_send.call_args[0][0]
        assert sent_msg["Subject"].startswith("Re:")


# ---------------------------------------------------------------------------
# fetch_new_emails — IMAP
# ---------------------------------------------------------------------------


class TestFetchNewEmails:
    @pytest.mark.asyncio
    async def test_not_configured(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.imap_user = ""
            mock_settings.imap_password = ""
            result = await fetch_new_emails()
        assert result == []

    @pytest.mark.asyncio
    async def test_imap_connection_error(self):
        with (
            patch("app.services.email_service.settings") as mock_settings,
            patch("app.services.email_service.aioimaplib.IMAP4_SSL", side_effect=Exception("Connection refused")),
        ):
            mock_settings.imap_user = "bot@eriskip.com"
            mock_settings.imap_password = "pass"
            mock_settings.imap_host = "imap.test.com"
            mock_settings.imap_port = 993
            result = await fetch_new_emails()
        assert result == []
