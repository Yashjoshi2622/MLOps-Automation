<#
.SYNOPSIS
    MLOps Docker deployment script.
    Runs on the self-hosted Windows GitHub Actions runner.

.DESCRIPTION
    1. Stops and removes any existing container with the same name.
    2. Builds the Docker image from the repository root.
    3. Starts a new container and maps port 8000.

    Image/container name is derived from the repository name via the
    GITHUB_REPOSITORY environment variable so different projects never
    collide on the same Windows host.

.NOTES
    Requires Docker Desktop (or Docker Engine) to be installed and running.
#>

$ErrorActionPreference = "Stop"

# ---- Derive image/container name from the GitHub repository env var ----
# GITHUB_REPOSITORY is set by GitHub Actions: "owner/repo"
# We sanitise it to produce a valid Docker name.
if ($env:GITHUB_REPOSITORY) {
    $RepoSlug = $env:GITHUB_REPOSITORY -replace "[^a-zA-Z0-9_.-]", "-"
    $ImageName     = $RepoSlug.ToLower()
    $ContainerName = $RepoSlug.ToLower()
} else {
    # Fallback for local testing
    $ImageName     = "mlops-app"
    $ContainerName = "mlops-app"
}

$Port = 8000

Write-Host "=== MLOps Deployment ===" -ForegroundColor Cyan
Write-Host "Image     : $ImageName"
Write-Host "Container : $ContainerName"
Write-Host "Port      : $Port"
Write-Host ""

# ---- Verify Docker is available ----
try {
    docker info | Out-Null
} catch {
    Write-Error "Docker is not available or not running. Please start Docker Desktop."
    exit 1
}

# ---- Stop existing container if running ----
$Running = docker ps -q --filter "name=^${ContainerName}$" 2>$null
if ($Running) {
    Write-Host "Stopping existing container: $ContainerName" -ForegroundColor Yellow
    docker stop $ContainerName
    Write-Host "Container stopped."
}

# ---- Remove existing container if present ----
$Exists = docker ps -aq --filter "name=^${ContainerName}$" 2>$null
if ($Exists) {
    Write-Host "Removing existing container: $ContainerName" -ForegroundColor Yellow
    docker rm $ContainerName
    Write-Host "Container removed."
}

# ---- Build Docker image ----
Write-Host "Building Docker image: $ImageName" -ForegroundColor Cyan
docker build -t $ImageName .
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker build failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}
Write-Host "Build succeeded."

# ---- Run new container ----
Write-Host "Starting container: $ContainerName" -ForegroundColor Cyan
docker run -d `
    --name $ContainerName `
    -p "${Port}:${Port}" `
    --restart unless-stopped `
    $ImageName

if ($LASTEXITCODE -ne 0) {
    Write-Error "docker run failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "=== Deployment complete ===" -ForegroundColor Green
Write-Host "Application is running at http://localhost:$Port"
