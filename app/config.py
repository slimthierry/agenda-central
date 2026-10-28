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


settings = Settings()
