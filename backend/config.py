from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TALLY_HOST: str = "192.168.18.219"
    TALLY_PORT: int = 9000
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    SESSION_TTL_MINUTES: int = 60

    @property
    def TALLY_URL(self) -> str:
        return f"http://{self.TALLY_HOST}:{self.TALLY_PORT}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
