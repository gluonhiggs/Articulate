# run.ps1 — Start Articulate backend on Windows (PC profile)
# Usage: .\run.ps1 [laptop|pc]
param(
    [string]$Profile = "pc"
)

$EnvFile = ".env.$Profile"
if (-not (Test-Path $EnvFile)) {
    Write-Error "Error: $EnvFile not found"
    exit 1
}

# Load env file into environment
Get-Content $EnvFile | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' } | ForEach-Object {
    $key, $value = $_ -split '=', 2
    [System.Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim(), 'Process')
}

# On PC profile: ensure CUDA torch is installed (CPU wheel is the pyproject.toml default)
if ($Profile -eq "pc") {
    Write-Host "Checking for CUDA torch..." -ForegroundColor Cyan
    $torchCheck = uv run python -c "import torch; print(torch.cuda.is_available())" 2>$null
    if ($torchCheck -ne "True") {
        Write-Host "Installing CUDA torch (cu121)..." -ForegroundColor Yellow
        uv pip install torch --index-url https://download.pytorch.org/whl/cu121
    } else {
        Write-Host "CUDA torch already installed." -ForegroundColor Green
    }
}

Write-Host "Starting Articulate ($Profile profile)..." -ForegroundColor Green
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --reload
