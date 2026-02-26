"""Shared pytest fixtures.

Will be extended with test DB session, mock IMAP/SMTP, and mock ML models
during the hackathon.
"""

import pytest


@pytest.fixture
def sample_email():
    """A sample email dict for testing the pipeline."""
    return {
        "email_from": "user@example.com",
        "email_to": "support@example.com",
        "subject": "Не работает авторизация",
        "body": "Добрый день! При попытке входа выдаёт ошибку 500. Помогите, пожалуйста.",
    }
