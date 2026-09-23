# MLOps Automation Webhook Service

A FastAPI service that listens for GitHub App push webhooks and automatically bootstraps new ML project repositories with CI/CD workflows, Docker configuration, and deployment scripts.

---

## How it Works

```
New ML repo ──► git push ──► GitHub App webhook ──► This service
                                                         │
                                        Inject bootstrap.yml + smoke test
                                                         │
                                          Bootstrap workflow runs in target repo
                                                         │
                              Generates: Dockerfile, CI, CD, deploy.ps1, pytest.ini
                                                         │
                                              CI runs ──► CD runs (main only)
                                                         │
                                          Self-hosted runner ──► Docker container
                                                         │
                                               localhost:8000
```

---

## Prerequisites

| Software | Minimum version |
|----------|----------------|
| Python | 3.10 |
| Docker Desktop | any recent |
| GitHub App | created (see below) |
| ngrok or Smee | for local tunnel |

---

## 1 — GitHub App Configuration

Your GitHub App (**MLOps Automation Bot**) must have:

| Setting | Value |
|---------|-------|
| Homepage URL | `http://localhost:8080` (or your server URL) |
| Webhook URL | `https://<your-tunnel>.ngrok.io/webhook` |
| Webhook Secret | A strong random string — set in `.env` |
| **Repository permissions** | |
| → Contents | Read & write |
| → Workflows | Read & write |
| → Metadata | Read-only (automatic) |
| **Subscribe to events** | |
| → Push | ✔ |

After creating / saving the App:
1. Go to **App settings → Private keys → Generate a private key**.
2. Download the `.pem` file and save it somewhere **outside** any git repo (e.g. `D:\secrets\mlops-app.pem`).
3. Note the **App ID** shown on the App settings page.
4. Install the App on your GitHub account / organisation.

---

## 2 — Environment Setup

```powershell
# From D:\MLOps-Automation
cd webhook

# Copy template
Copy-Item .env.example .env

# Edit .env — fill in GITHUB_APP_ID, GITHUB_PRIVATE_KEY_PATH,
#              GITHUB_WEBHOOK_SECRET, MLOPS_AUTOMATION_REPO
notepad .env
```

`.env` values:

| Variable | Where to find it |
|----------|-----------------|
| `GITHUB_APP_ID` | GitHub App settings page |
| `GITHUB_PRIVATE_KEY_PATH` | Absolute path to the downloaded `.pem` file |
| `GITHUB_WEBHOOK_SECRET` | The secret you typed when creating the webhook |
| `MLOPS_AUTOMATION_REPO` | `YourOrg/MLOps-Automation` |

---

## 3 — Install Dependencies

```powershell
# From D:\MLOps-Automation (project root, NOT inside webhook/)
pip install -r webhook/requirements.txt
```

---

## 4 — Start the Webhook Service

```powershell
# Always run from the project root so the package import works correctly
cd D:\MLOps-Automation
uvicorn webhook.app:app --host 0.0.0.0 --port 8080 --reload
```

Verify it is running:

```powershell
curl http://localhost:8080/
# Expected: {"status":"healthy","service":"MLOps Automation Webhook",...}
```

---

## 5 — Expose the Service with ngrok

GitHub cannot reach `localhost:8080` directly. Use ngrok to create a public tunnel:

```powershell
# Install ngrok from https://ngrok.com/download
# Then:
ngrok http 8080
```

Copy the `https://xxxx.ngrok.io` URL from the ngrok output.

Update your GitHub App's **Webhook URL** to:
```
https://xxxx.ngrok.io/webhook
```

> **Note:** The ngrok URL changes every time you restart ngrok (on the free plan).
> Update the GitHub App webhook URL each session, or use a paid ngrok plan / a fixed server.

---

## 6 — Self-Hosted Runner Setup (Windows PC)

The CD workflow deploys to your Windows PC using a self-hosted runner.

### Required software on your Windows PC
- Docker Desktop (must be running when the runner executes)
- Git
- PowerShell 5.1+ (pre-installed on Windows 10/11)

### Register the runner

1. Go to your **target ML project repository** on GitHub.
2. Navigate to **Settings → Actions → Runners → New self-hosted runner**.
3. Select **Windows** and follow the instructions displayed.

Typical commands (run in PowerShell **as Administrator** on your PC):

```powershell
# Create a directory for the runner — keep it on D:\
mkdir D:\actions-runner
cd D:\actions-runner

# Download the runner package (version shown in GitHub UI)
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.xxx.x/actions-runner-win-x64-2.xxx.x.zip -OutFile actions-runner.zip
Expand-Archive actions-runner.zip -DestinationPath .

# Configure (replace the URL and token with values from the GitHub UI)
.\config.cmd --url https://github.com/YourOrg/YourMLRepo --token YOUR_RUNNER_TOKEN

# Install and start as a Windows service (recommended)
.\svc.cmd install
.\svc.cmd start
```

### Verify the runner is online
- Go to **Settings → Actions → Runners** in the target repo.
- The runner should show a green **Idle** status.

---

## 7 — End-to-End Test Procedure

1. Create a new **empty** GitHub repository (e.g. `MLOps-Test-Project`).
2. Install the **MLOps Automation Bot** GitHub App on that repository.
3. Make sure the webhook service is running locally and ngrok is active.
4. Make sure the runner is online.

```powershell
# On your local machine — initialise a simple ML project
mkdir D:\my-test-project
cd D:\my-test-project
git init
echo "fastapi" > requirements.txt
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YourOrg/MLOps-Test-Project.git
git push -u origin main
```

5. Watch the webhook service logs — you should see:
   ```
   Received event: push
   Bootstrapping YourOrg/MLOps-Test-Project ...
   Injected bootstrap.yml into YourOrg/MLOps-Test-Project
   Bootstrap result: {"bootstrap_workflow": "created", "smoke_test": "created"}
   ```

6. In the GitHub repository, go to **Actions**. You should see the
   **MLOps Bootstrap** workflow triggered automatically.

7. After the bootstrap workflow completes, **CI Pipeline** and
   **CD Pipeline** workflows appear and run.

8. After CI passes, CD runs on your self-hosted runner and deploys the
   Docker container. Visit `http://localhost:8000`.

---

## Security Notes

- `.env` is listed in `.gitignore` — **never commit it**.
- The private key (`.pem`) should be stored **outside** the git repository.
- Webhook signatures are verified using HMAC-SHA256 before any payload is processed.
- The access token obtained from GitHub is used only in `Authorization` headers and is **never logged**.
- The webhook service **never executes code from the target repository**.
- CD only runs after a successful CI on the `main` branch — PRs are never deployed.
