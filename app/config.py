from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ticket_tamer"

    # RouterAI API
    routerai_api_key: str = ""
    routerai_base_url: str = "https://routerai.ru/api/v1"
    llm_model: str = "deepseek/deepseek-v3.2"
    llm_fallback_model: str = "qwen/qwen3.5-flash-02-23"
    embedding_model: str = "baai/bge-m3"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048

    # IMAP
    imap_host: str = "imap.example.com"
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""

    # SMTP
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    # Classification
    classification_confidence_threshold: float = 0.7

    # KB Cleanup
    kb_retention_days: int = 180
    kb_cleanup_interval_h: int = 24

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Google Sheets
    google_sheets_credentials_file: str = ""
    google_sheets_spreadsheet_id: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
