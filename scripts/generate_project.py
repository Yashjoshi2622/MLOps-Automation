"""
generate_project.py
--------------------
MLOps project generator.

Usage:
    python generate_project.py <path-to-target-ml-project>

Generates / injects:
  - Dockerfile          (generated dynamically based on detected structure)
  - requirements.txt    (only if not already present)
  - pytest.ini
  - tests/test_smoke.py (only if no test files detected)
  - .github/workflows/ci.yml
  - .github/workflows/cd.yml
  - scripts/deploy.ps1

Safety rules:
  - Never overwrites requirements.txt if it already exists.
  - Never overwrites ci.yml / cd.yml if they already exist.
  - Never deletes user source files.
  - Never reads or executes user ML source code.
  - Template path is resolved relative to THIS script, not to any
    hardcoded absolute path.
"""

from pathlib import Path
import sys

# Template directory is always relative to this script regardless of where
# the automation repo is cloned.
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = BASE_DIR / "templates"


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------

def detect_project(project_path: Path) -> dict:
    """
    Inspect the target project directory and return a dict of detected flags.
    Never modifies the project or executes any user code.
    """
    src_exists = (project_path / "src").exists()
    models_exists = (project_path / "models").exists()
    requirements_exists = (project_path / "requirements.txt").exists()
    main_exists = (project_path / "src" / "main.py").exists()

    # Detect whether any test files already exist
    test_files = list(project_path.rglob("test_*.py")) + list(
        project_path.rglob("*_test.py")
    )
    # Exclude anything inside .mlops-automation (temp automation folder)
    test_files = [
        f
        for f in test_files
        if ".mlops-automation" not in f.parts
    ]
    tests_exist = bool(test_files)

    info = {
        "src_exists": src_exists,
        "models_exists": models_exists,
        "requirements_exists": requirements_exists,
        "main_exists": main_exists,
        "tests_exist": tests_exist,
    }

    print("\nChecking project structure...")
    print(f"  src/              : {'FOUND' if src_exists else 'NOT FOUND'}")
    print(f"  models/           : {'FOUND' if models_exists else 'NOT FOUND'}")
    print(f"  requirements.txt  : {'FOUND' if requirements_exists else 'NOT FOUND'}")
    print(f"  src/main.py       : {'FOUND' if main_exists else 'NOT FOUND'}")
    print(f"  test files        : {'FOUND' if tests_exist else 'NOT FOUND'}")
    print("Project detection completed.\n")

    return info


# ---------------------------------------------------------------------------
# Dynamic Dockerfile generation
# ---------------------------------------------------------------------------

def _generate_dockerfile_content(info: dict) -> str:
    """
    Build a Dockerfile tailored to the detected project structure.
    Only COPY statements for directories that actually exist are emitted,
    avoiding broken Docker builds when models/ is absent.
    """
    lines = [
        "FROM python:3.10-slim",
        "",
        "WORKDIR /app",
        "",
        "# Install dependencies first for better layer caching",
        "COPY requirements.txt .",
        "RUN pip install --no-cache-dir -r requirements.txt",
        "",
    ]

    if info["src_exists"]:
        lines.append("COPY src ./src")
    else:
        # Fallback: copy the entire project (excluding common dev artifacts)
        lines.append("# src/ not found — copying entire project")
        lines.append("COPY . .")

    if info["models_exists"]:
        lines.append("COPY models ./models")

    lines += [
        "",
        "EXPOSE 8000",
        "",
        'CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]',
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Smoke test injection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_project(project_path_arg: str) -> None:
    project_path = Path(project_path_arg).resolve()

    print(f"\nCreating MLOps setup for: {project_path}")

    if not TEMPLATES_DIR.exists():
        print(f"\nERROR: Templates folder not found: {TEMPLATES_DIR}")
        sys.exit(1)

    info = detect_project(project_path)

    # ---- Create required directories ----
    (project_path / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (project_path / "scripts").mkdir(parents=True, exist_ok=True)
    (project_path / "tests").mkdir(parents=True, exist_ok=True)

    generated = []
    preserved = []

    # ---- Dockerfile (always generated dynamically) ----
    dockerfile_content = _generate_dockerfile_content(info)
    (project_path / "Dockerfile").write_text(dockerfile_content, encoding="utf-8")
    generated.append("Dockerfile")

    # ---- requirements.txt (preserve existing) ----
    req_path = project_path / "requirements.txt"
    if not req_path.exists():
        import shutil
        shutil.copy(TEMPLATES_DIR / "requirements.txt", req_path)
        generated.append("requirements.txt")
    else:
        preserved.append("requirements.txt")

    # ---- pytest.ini ----
    import shutil
    shutil.copy(TEMPLATES_DIR / "pytest.ini", project_path / "pytest.ini")
    generated.append("pytest.ini")

    # ---- Smoke test (only if no test files detected) ----
    smoke_path = project_path / "tests" / "test_smoke.py"
    init_path = project_path / "tests" / "__init__.py"
    if not info["tests_exist"] and not smoke_path.exists():
        smoke_path.write_text(_SMOKE_TEST_CONTENT, encoding="utf-8")
        init_path.touch(exist_ok=True)
        generated.append("tests/test_smoke.py")
        generated.append("tests/__init__.py")
    else:
        preserved.append("tests/ (existing tests found)")

    # ---- CI workflow (preserve existing) ----
    ci_path = project_path / ".github" / "workflows" / "ci.yml"
    if not ci_path.exists():
        shutil.copy(TEMPLATES_DIR / "ci.yml", ci_path)
        generated.append(".github/workflows/ci.yml")
    else:
        preserved.append(".github/workflows/ci.yml")

    # ---- CD workflow (preserve existing) ----
    cd_path = project_path / ".github" / "workflows" / "cd.yml"
    if not cd_path.exists():
        shutil.copy(TEMPLATES_DIR / "cd.yml", cd_path)
        generated.append(".github/workflows/cd.yml")
    else:
        preserved.append(".github/workflows/cd.yml")

    # ---- Deployment script ----
    shutil.copy(
        TEMPLATES_DIR / "deploy.ps1",
        project_path / "scripts" / "deploy.ps1",
    )
    generated.append("scripts/deploy.ps1")

    # ---- Summary ----
    print("MLOps setup generated successfully!\n")
    if generated:
        print("Generated files:")
        for f in generated:
            print(f"  + {f}")
    if preserved:
        print("\nPreserved (not overwritten):")
        for f in preserved:
            print(f"  ~ {f}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("\nUsage:")
        print("  python generate_project.py <path-to-ml-project>")
        sys.exit(1)

    generate_project(sys.argv[1])