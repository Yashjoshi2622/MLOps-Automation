"""
config.py
---------
All configuration is loaded from environment variables (or a .env file).
No secrets or repository-specific values are hard-coded here.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ----------------------------------------------------------------
    # GitHub App credentials
    # ----------------------------------------------------------------
    GITHUB_APP_ID: str
    GITHUB_PRIVATE_KEY_PATH: Path        # absolute path to the .pem file
    GITHUB_WEBHOOK_SECRET: str           # GitHub App webhook secret

    # ----------------------------------------------------------------
    # Automation repository  (format: "owner/repo")
    # This is the MLOps-Automation repo that contains templates/ and scripts/
    # ----------------------------------------------------------------
    MLOPS_AUTOMATION_REPO: str

    # ----------------------------------------------------------------
    # Server settings (optional overrides)
    # ----------------------------------------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()
