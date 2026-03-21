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
    # Use 'uv pip show' to inspect the installed wheel version — much faster than importing torch.
    # CUDA wheels carry a "+cu121" suffix in their version string (e.g. "2.3.0+cu121").
    $torchVersion = uv pip show torch 2>$null | Select-String "^Version:"
    $isCuda = $torchVersion -and ($torchVersion -match "cu121")
    if (-not $isCuda) {
        Write-Host "Installing CUDA torch (cu121)..." -ForegroundColor Yellow
        uv pip install torch --index-url https://download.pytorch.org/whl/cu121
    } else {
        Write-Host "CUDA torch already installed." -ForegroundColor Green
    }
}



# Conditional SSL
$sslArgs = @()
if (Test-Path "certs/cert.pem") {
    $sslArgs = @("--ssl-certfile", "certs/cert.pem", "--ssl-keyfile", "certs/key.pem")
    Write-Host "HTTPS enabled (certs/cert.pem found)" -ForegroundColor Green
} else {
    Write-Warning "certs/ not found, running HTTP only (for phone mic: enable chrome://flags/#unsafely-treat-insecure-origin-as-secure)"
}

Write-Host "Starting Articulate ($Profile profile)..." -ForegroundColor Green
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --reload @sslArgs
