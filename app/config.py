import logging
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://agenda:agenda@localhost:5435/agenda"

    service_name: str = "agenda-central"
    api_port: int = 4400

    reminder_lead_min: int = 60
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # Security
    cors_origins: list[str] = ["*"]
    rate_limit_requests: int = 100
    rate_limit_period: int = 60

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def setup_logging(settings: Settings) -> None:
    """Configure logging based on settings."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format=settings.log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Set uvicorn loggers to same level
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)


settings = Settings()
