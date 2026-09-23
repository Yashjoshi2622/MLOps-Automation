"""
bootstrap.py
------------
Injects the MLOps bootstrap workflow into a target GitHub repository
using the GitHub Contents API (no local git clone required).

Design decisions:
  - Uses the GitHub REST API exclusively, so the service never executes
    code from the target repository (security requirement).
  - The bootstrap.yml template is read from THIS automation repository's
    own .github/workflows/bootstrap.yml.
  - The automation repo reference (${{ vars.MLOPS_AUTOMATION_REPO }}) is
    substituted with the real value before injection so the target repo
    does not need a separate variable configured.
  - If bootstrap.yml already exists in the target repo it is left alone
    (idempotent).
  - A minimal smoke-test file is also injected so that CI never fails
    solely because the user has not written tests yet.
"""

import base64
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# Paths that will be injected into the target repository
_BOOTSTRAP_WORKFLOW = ".github/workflows/bootstrap.yml"
_SMOKE_TEST_PATH = "tests/test_smoke.py"

# Smoke test content — always passes, documents the intention
_SMOKE_TEST_CONTENT = '''\
"""
test_smoke.py
-------------
Auto-generated minimal smoke test by the MLOps Automation Framework.
Replace or extend this file with your own tests.
"""


def test_smoke():
    """Smoke test: always passes — confirms the test runner is working."""
    assert True
'''


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_file(owner: str, repo: str, path: str, token: str) -> dict | None:
    """
    Return the file metadata dict from the Contents API, or None if not found.
    Raises for unexpected HTTP errors.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    resp = httpx.get(url, headers=_headers(token))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _put_file(
    owner: str,
    repo: str,
    path: str,
    content: bytes,
    message: str,
    token: str,
    sha: str | None = None,
) -> None:
    """Create or update a file in the target repository via the Contents API."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    payload: dict = {
        "message": message,
        "content": base64.b64encode(content).decode(),
    }
    if sha:
        payload["sha"] = sha
    resp = httpx.put(url, headers=_headers(token), json=payload)
    resp.raise_for_status()


def _load_bootstrap_template(automation_repo: str) -> bytes:
    """
    Read the bootstrap.yml from this automation repo and substitute the
    automation repo placeholder with the real value so the target repo's
    workflow can find templates without needing an Actions variable.
    """
    template_path = (
        Path(__file__).resolve().parent.parent
        / ".github"
        / "workflows"
        / "bootstrap.yml"
    )
    if not template_path.exists():
        raise FileNotFoundError(
            f"Bootstrap template not found at: {template_path}"
        )
    content = template_path.read_text(encoding="utf-8")
    # Substitute the variable placeholder with the real automation repo
    content = content.replace(
        "${{ vars.MLOPS_AUTOMATION_REPO }}", automation_repo
    )
    return content.encode("utf-8")


def bootstrap_repository(
    owner: str, repo: str, token: str, automation_repo: str
) -> dict:
    """
    Ensure the target repository has the MLOps bootstrap workflow and a
    minimal smoke test so that CI can run immediately.

    Returns a status dict describing what was created / skipped.
    """
    results: dict[str, str] = {}

    # ----------------------------------------------------------------
    # 1. Inject bootstrap.yml
    # ----------------------------------------------------------------
    existing = _get_file(owner, repo, _BOOTSTRAP_WORKFLOW, token)
    if existing is None:
        bootstrap_content = _load_bootstrap_template(automation_repo)
        _put_file(
            owner,
            repo,
            _BOOTSTRAP_WORKFLOW,
            bootstrap_content,
            "chore: add MLOps bootstrap workflow [skip ci]",
            token,
        )
        logger.info("Injected bootstrap.yml into %s/%s", owner, repo)
        results["bootstrap_workflow"] = "created"
    else:
        logger.info(
            "bootstrap.yml already exists in %s/%s — skipping", owner, repo
        )
        results["bootstrap_workflow"] = "already_exists"

    # ----------------------------------------------------------------
    # 2. Inject smoke test (only if tests/ directory has no test files)
    # ----------------------------------------------------------------
    smoke_existing = _get_file(owner, repo, _SMOKE_TEST_PATH, token)
    if smoke_existing is None:
        _put_file(
            owner,
            repo,
            _SMOKE_TEST_PATH,
            _SMOKE_TEST_CONTENT.encode("utf-8"),
            "chore: add minimal smoke test [skip ci]",
            token,
        )
        logger.info("Injected smoke test into %s/%s", owner, repo)
        results["smoke_test"] = "created"
    else:
        results["smoke_test"] = "already_exists"

    return results
