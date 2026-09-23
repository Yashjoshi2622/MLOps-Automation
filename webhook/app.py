"""
app.py
------
FastAPI webhook service for the MLOps Automation Framework.

Endpoints:
  GET  /          — health check
  POST /webhook   — GitHub App webhook receiver

Security:
  - Every incoming webhook request is verified against the HMAC-SHA256
    signature produced by GitHub using the GITHUB_WEBHOOK_SECRET.
  - The raw token obtained from GitHub is used only in an Authorization
    header; it is never logged or returned to callers.
  - Only push events to the default branch are acted upon.
  - Commits made by the bootstrap process itself (marked [skip ci] or
    pushed by github-actions[bot]) are ignored to prevent infinite loops.
"""

import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .config import settings
from .github_app import create_jwt, get_installation_token
from .bootstrap import bootstrap_repository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== MLOps Automation Webhook Service starting ===")
    logger.info("GitHub App ID : %s", settings.GITHUB_APP_ID)
    logger.info("Automation repo: %s", settings.MLOPS_AUTOMATION_REPO)
    logger.info("Listening on  : %s:%d", settings.HOST, settings.PORT)
    yield
    logger.info("=== MLOps Automation Webhook Service stopped ===")


app = FastAPI(
    title="MLOps Automation Webhook",
    description=(
        "Receives GitHub push webhooks and bootstraps new ML project "
        "repositories with CI/CD workflows and Docker configuration."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify_signature(payload: bytes, signature_header: str | None) -> bool:
    """
    Validate the HMAC-SHA256 signature GitHub attaches to every webhook.
    Returns False (never raises) so callers can return 401 explicitly.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["health"])
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "MLOps Automation Webhook",
        "automation_repo": settings.MLOPS_AUTOMATION_REPO,
    }


@app.post("/webhook", tags=["webhook"])
async def webhook(request: Request):
    """
    Receive and process GitHub App webhook events.

    Expected headers:
      X-Hub-Signature-256  — HMAC-SHA256 of the raw body
      X-GitHub-Event       — event type (we handle 'push' and 'ping')
    """
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    # --- 1. Verify signature before touching payload ---
    if not _verify_signature(payload_bytes, signature):
        logger.warning("Rejected webhook: invalid or missing signature.")
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    event_type = request.headers.get("X-GitHub-Event", "")
    logger.info("Received event: %s", event_type)

    # --- 2. Respond to ping (sent when a new webhook is configured) ---
    if event_type == "ping":
        return {"status": "pong", "message": "Webhook configured successfully."}

    # --- 3. Ignore anything that is not a push event ---
    if event_type != "push":
        return {"status": "ignored", "event": event_type}

    payload: dict = json.loads(payload_bytes)

    # --- 4. Only act on pushes to the repository's default branch ---
    ref: str = payload.get("ref", "")
    default_branch: str = (
        payload.get("repository", {}).get("default_branch", "main")
    )
    if ref != f"refs/heads/{default_branch}":
        logger.info("Ignoring push to non-default branch: %s", ref)
        return {"status": "ignored", "reason": "non-default-branch", "ref": ref}

    # --- 5. Skip commits produced by the bootstrap itself ---
    pusher_name: str = payload.get("pusher", {}).get("name", "")
    head_commit: dict = payload.get("head_commit") or {}
    commit_msg: str = head_commit.get("message", "")

    if pusher_name == "github-actions[bot]" or "[skip ci]" in commit_msg:
        logger.info(
            "Skipping bootstrap-sourced push (pusher=%s, msg=%r).",
            pusher_name,
            commit_msg[:80],
        )
        return {"status": "ignored", "reason": "skip-ci"}

    # --- 6. Extract repository and installation details ---
    repo_full: str = payload.get("repository", {}).get("full_name", "")
    installation_id: int | None = (
        payload.get("installation", {}).get("id")
    )

    if not repo_full or installation_id is None:
        logger.error(
            "Payload missing repository.full_name or installation.id."
        )
        raise HTTPException(
            status_code=400,
            detail="Payload missing required fields (full_name / installation.id).",
        )

    owner, repo = repo_full.split("/", 1)
    logger.info(
        "Bootstrapping %s (installation_id=%s)", repo_full, installation_id
    )

    # --- 7. Authenticate as the GitHub App for this installation ---
    try:
        jwt_token = create_jwt(settings.GITHUB_APP_ID, settings.GITHUB_PRIVATE_KEY_PATH)
        access_token = get_installation_token(installation_id, jwt_token)
    except Exception as exc:
        logger.exception("GitHub App authentication failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="GitHub App authentication failed."
        )

    # --- 8. Bootstrap the target repository ---
    try:
        result = bootstrap_repository(
            owner, repo, access_token, settings.MLOPS_AUTOMATION_REPO
        )
        logger.info("Bootstrap result for %s: %s", repo_full, result)
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "repository": repo_full, "result": result},
        )
    except Exception as exc:
        logger.exception("Bootstrap failed for %s: %s", repo_full, exc)
        raise HTTPException(
            status_code=500, detail=f"Bootstrap failed: {exc}"
        )