from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TALLY_HOST: str = "localhost"
    TALLY_PORT: int = 9000
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_CLASSIFIER_MODEL: str = "claude-haiku-4-5-20251001"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    SESSION_TTL_MINUTES: int = 60
    TALLY_MODE: str = "live"  # "live" or "mock"
    CODE_EXECUTION_ENABLED: bool = True  # kill switch: False reverts to analysis tools
    ANALYSIS_CONTEXT_MESSAGES: int = 8  # Number of prior session messages passed to AnalysisAgent
    CHARTS_ENABLED: bool = True  # kill switch for chart rendering
    CORS_ORIGINS: str = ""  # Comma-separated allowed origins; empty/"*" = allow all (legacy default)
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"

    # Database & Auth (Set A1)
    DATABASE_URL: str | None = None
    JWT_SECRET: str | None = None
    JWT_ACCESS_TOKEN_EXPIRY_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRY_DAYS: int = 7

    # File upload (Set B1)
    FILE_STORAGE_PATH: str = "./uploads"
    FILE_MAX_SIZE_MB: int = 10

    # Tally write (Set B1)
    TALLY_WRITE_ENABLED: bool = False
    TALLY_DRY_RUN: bool = False

    @property
    def db_mode(self) -> bool:
        """True when DATABASE_URL is set — enables auth + persistence."""
        return self.DATABASE_URL is not None

    @property
    def TALLY_URL(self) -> str:
        return f"http://{self.TALLY_HOST}:{self.TALLY_PORT}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
