from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    anthropic_admin_key: str | None = Field(default=None, alias="ANTHROPIC_ADMIN_KEY")
    openai_admin_key: str | None = Field(default=None, alias="OPENAI_ADMIN_KEY")
    log_dir: str = Field(default="/app/logs", alias="LOG_DIR")
    claude_code_dir: str = Field(default="~/.claude", alias="CLAUDE_CODE_DIR")
    poll_interval_seconds: int = Field(default=60, alias="POLL_INTERVAL_SECONDS")

    model_config = {"env_file": ".env", "populate_by_name": True}


settings = Settings()
