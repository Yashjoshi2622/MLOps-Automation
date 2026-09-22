from pathlib import Path
import shutil
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = BASE_DIR / "templates"


def detect_project(project_path):
    print("\nChecking project structure...")

    src_exists = (project_path / "src").exists()
    models_exists = (project_path / "models").exists()
    requirements_exists = (project_path / "requirements.txt").exists()
    main_exists = (project_path / "src" / "main.py").exists()

    print(f"src/              : {'FOUND' if src_exists else 'NOT FOUND'}")
    print(f"models/           : {'FOUND' if models_exists else 'NOT FOUND'}")
    print(f"requirements.txt  : {'FOUND' if requirements_exists else 'NOT FOUND'}")
    print(f"src/main.py       : {'FOUND' if main_exists else 'NOT FOUND'}")

    print("\nProject detection completed.")


def generate_project(project_path):
    project_path = Path(project_path).resolve()

    print(f"\nCreating MLOps setup for: {project_path}")

    if not TEMPLATES_DIR.exists():
        print(f"\nERROR: Templates folder not found: {TEMPLATES_DIR}")
        sys.exit(1)

    detect_project(project_path)

    # Create required folders
    (project_path / ".github" / "workflows").mkdir(
        parents=True,
        exist_ok=True
    )

    (project_path / "scripts").mkdir(
        parents=True,
        exist_ok=True
    )

    # Copy Dockerfile
    shutil.copy(
        TEMPLATES_DIR / "Dockerfile",
        project_path / "Dockerfile"
    )

    # Copy requirements.txt only if it does not already exist
    if not (project_path / "requirements.txt").exists():
        shutil.copy(
            TEMPLATES_DIR / "requirements.txt",
            project_path / "requirements.txt"
        )
        print("Created requirements.txt")
    else:
        print("Existing requirements.txt preserved.")

    # Copy pytest.ini
    shutil.copy(
        TEMPLATES_DIR / "pytest.ini",
        project_path / "pytest.ini"
    )

    # Copy CI workflow
    shutil.copy(
        TEMPLATES_DIR / "ci.yml",
        project_path / ".github" / "workflows" / "ci.yml"
    )

    # Copy CD workflow
    shutil.copy(
        TEMPLATES_DIR / "cd.yml",
        project_path / ".github" / "workflows" / "cd.yml"
    )

    # Copy deployment script
    shutil.copy(
        TEMPLATES_DIR / "deploy.ps1",
        project_path / "scripts" / "deploy.ps1"
    )

    print("\nMLOps setup generated successfully!")

    print("\nGenerated files:")
    print("  Dockerfile")
    print("  requirements.txt")
    print("  pytest.ini")
    print("  .github/workflows/ci.yml")
    print("  .github/workflows/cd.yml")
    print("  scripts/deploy.ps1")


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("\nUsage:")
        print("python generate_project.py <project_path>")
        sys.exit(1)

    generate_project(sys.argv[1])