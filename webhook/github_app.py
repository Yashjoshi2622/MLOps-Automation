"""
github_app.py
-------------
GitHub App authentication helpers.

Responsibilities:
  - Generate a short-lived JWT signed with the App's RSA private key.
  - Exchange the JWT for an installation access token that can act on
    a specific repository.

Security:
  - The private key is read from a file path; it is never logged or
    included in any API response.
  - Tokens are not cached globally; a fresh token is obtained per
    webhook event to avoid stale or leaked tokens.
"""

import time
import logging
from pathlib import Path

import jwt          # PyJWT
import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
_ACCEPT = "application/vnd.github+json"
_API_VERSION = "2022-11-28"


def _api_headers(token: str, token_type: str = "Bearer") -> dict:
    return {
        "Authorization": f"{token_type} {token}",
        "Accept": _ACCEPT,
        "X-GitHub-Api-Version": _API_VERSION,
    }


def create_jwt(app_id: str, private_key_path: Path) -> str:
    """
    Create a short-lived JWT (≤ 10 min) to authenticate as the GitHub App.
    The private key is read directly from disk and is never stored in memory
    beyond this function call.
    """
    private_key = private_key_path.read_text(encoding="utf-8")
    now = int(time.time())
    payload = {
        "iat": now - 60,   # issued 60 s ago to tolerate clock skew
        "exp": now + 540,  # expires in 9 min (max GitHub allows is 10 min)
        "iss": str(app_id),
    }
    token = jwt.encode(payload, private_key, algorithm="RS256")
    # PyJWT ≥ 2.0 returns str; older versions return bytes
    return token if isinstance(token, str) else token.decode()


def get_installation_token(installation_id: int, jwt_token: str) -> str:
    """
    Exchange a GitHub App JWT for an installation access token that can
    read/write the repositories the App is installed on.

    Returns the raw token string. The caller is responsible for using it
    safely (e.g. not logging it).
    """
    url = f"{GITHUB_API}/app/installations/{installation_id}/access_tokens"
    resp = httpx.post(url, headers=_api_headers(jwt_token, "Bearer"))
    resp.raise_for_status()
    return resp.json()["token"]
