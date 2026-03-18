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
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"

    @property
    def TALLY_URL(self) -> str:
        return f"http://{self.TALLY_HOST}:{self.TALLY_PORT}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
