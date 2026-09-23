"""
config.py
---------
All configuration is loaded from environment variables (or a .env file).
No secrets or repository-specific values are hard-coded here.
"""

from pathlib import Path
import sys
from pydantic_settings import BaseSettings

_CONFIG_DIR = Path(__file__).resolve().parent

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
        "env_file": str(_CONFIG_DIR / ".env"),
        "case_sensitive": False,
        "extra": "ignore",
    }

try:
    settings = Settings()
    print("\n--- MLOps Webhook Configuration ---")
    print(f"GITHUB_APP_ID:           SET")
    print(f"GITHUB_PRIVATE_KEY_PATH: SET")
    print(f"GITHUB_WEBHOOK_SECRET:   SET")
    print(f"MLOPS_AUTOMATION_REPO:   SET")
    print("-----------------------------------\n")
except Exception as e:
    print("\n[ERROR] Failed to load configuration.")
    print("Make sure you have created D:\\MLOps-Automation\\webhook\\.env and filled in all required fields.")
    print(f"Details: {e}\n")
    sys.exit(1)
