# run.ps1 — Start Articulate on Windows
# Usage: .\run.ps1

# ── Load config ───────────────────────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Write-Error ".env not found. Copy .env.example to .env and fill in your API keys."
    exit 1
}

Get-Content ".env" | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' } | ForEach-Object {
    $key, $value = $_ -split '=', 2
    [System.Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim(), 'Process')
}


# ── Java check (required for LanguageTool grammar checker) ───────────────────
# Refresh PATH from registry first — picks up Java installed in a prior session
# before we decide whether to call winget at all.
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("PATH", "User")

if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    # Resolve winget — it lives in WindowsApps which is often absent from PATH
    # in non-interactive / no-profile PowerShell sessions.
    $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
    $wingetExe = if ($wingetCmd) { $wingetCmd.Source } else { $null }
    if (-not $wingetExe) {
        $wingetExe = "$env:LOCALAPPDATA\Microsoft\WindowsApps\winget.exe"
        if (-not (Test-Path $wingetExe)) { $wingetExe = $null }
    }

    if ($wingetExe) {
        Write-Host "Java not found - installing Microsoft OpenJDK 21 via winget..." -ForegroundColor Yellow
        & $wingetExe install --id Microsoft.OpenJDK.21 --silent --accept-package-agreements --accept-source-agreements
        # winget exits -1978335189 when the package is already installed — treat as success.
        if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189) {
            # Re-read registry PATH so this session can use the new java binary.
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                        [System.Environment]::GetEnvironmentVariable("PATH", "User")
            if (Get-Command java -ErrorAction SilentlyContinue) {
                Write-Host "Java installed successfully." -ForegroundColor Green
            } else {
                Write-Warning "Java installed but not yet in PATH - restart your terminal then re-run to enable local LanguageTool."
            }
        } else {
            Write-Warning "Java installation failed (exit $LASTEXITCODE). Try re-running as Administrator or install manually: https://adoptium.net"
            Write-Warning "Grammar checking will fall back to LanguageTool public API."
        }
    } else {
        Write-Warning "winget not found. Install Java manually (https://adoptium.net) or re-run from Windows Terminal."
        Write-Warning "Grammar checking will fall back to LanguageTool public API."
    }
} else {
    # Validate minimum version — LanguageTool 6.x requires Java 11+.
    $javaVerLine = (java -version 2>&1)[0] -as [string]
    Write-Host "Java: $javaVerLine" -ForegroundColor Green
    if ($javaVerLine -match '"(\d+)[\._]') {
        $javaMajor = [int]$Matches[1]
        if ($javaMajor -lt 11) {
            Write-Warning "Java $javaMajor detected - LanguageTool requires Java 11+. Grammar checking may fail."
        }
    }
}

# ── Frontend: staleness check + build if needed ───────────────────────────────
$distIndex = "frontend\dist\index.html"
$mustBuild = $false

if (-not (Test-Path $distIndex)) {
    Write-Host "Frontend dist not found - building..." -ForegroundColor Yellow
    $mustBuild = $true
} else {
    $distMtime  = (Get-Item $distIndex).LastWriteTime
    $watchPaths = @("frontend\src", "frontend\index.html", "frontend\package.json", "frontend\vite.config.ts")
    $newerFile  = $null
    foreach ($p in $watchPaths) {
        if (-not (Test-Path $p)) { continue }
        $items = if ((Get-Item $p).PSIsContainer) {
            Get-ChildItem $p -Recurse -File
        } else {
            @(Get-Item $p)
        }
        foreach ($f in $items) {
            if ($f.LastWriteTime -gt $distMtime) { $newerFile = $f.FullName; break }
        }
        if ($newerFile) { break }
    }
    if ($newerFile) {
        Write-Host "Frontend source changed ($newerFile) - rebuilding..." -ForegroundColor Yellow
        $mustBuild = $true
    } else {
        Write-Host "Frontend dist is up to date, skipping build." -ForegroundColor Green
    }
}

if ($mustBuild) {
    Push-Location frontend
    bun run build
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        Write-Error "Frontend build failed (exit $LASTEXITCODE). Aborting."
        exit 1
    }
    Pop-Location
    Write-Host "Frontend built successfully." -ForegroundColor Green
}

# ── Frontend dev server in a new terminal window ──────────────────────────────
$frontendDir = Join-Path $PSScriptRoot "frontend"
Write-Host "Starting frontend dev server (port 5173) in new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontendDir'; bun run dev"

Write-Host "Starting Articulate..." -ForegroundColor Green
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --reload
