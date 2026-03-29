# run.ps1 — Start Articulate backend on Windows
# Usage: .\run.ps1 [auto|laptop|pc|gemini]
#
# auto (default): uses API mode if LLM_API_KEY is set in .env.gemini,
#                 falls back to GPU (pc) mode otherwise.
param(
    [string]$Profile = "auto"
)

# ── Auto-detect mode ──────────────────────────────────────────────────────────
if ($Profile -eq "auto") {
    $geminiEnv = ".env.gemini"
    $hasApiKey = $false
    if (Test-Path $geminiEnv) {
        $keyLine = Get-Content $geminiEnv | Where-Object { $_ -match '^LLM_API_KEY=' }
        if ($keyLine) {
            $keyValue = ($keyLine -split '=', 2)[1].Trim()
            # A real key: non-empty and not the placeholder string
            $hasApiKey = $keyValue -and $keyValue -ne "" -and $keyValue -notlike "your-*"
        }
    }
    if ($hasApiKey) {
        $Profile = "gemini"
        Write-Host "[auto] API key found  -> using API mode (no GPU)" -ForegroundColor Cyan
    } else {
        $Profile = "pc"
        Write-Host "[auto] No API key     -> using GPU mode (Ollama)" -ForegroundColor Cyan
    }
}

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
    # Ensure CUDA runtime libs for ctranslate2/faster-whisper (cublas, cudnn)
    $hasCublas = uv pip show nvidia-cublas-cu12 2>$null
    $hasCudnn  = uv pip show nvidia-cudnn-cu12  2>$null
    if (-not $hasCublas -or -not $hasCudnn) {
        Write-Host "Installing GPU extras (nvidia CUDA libs)..." -ForegroundColor Yellow
        uv pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
    } else {
        Write-Host "GPU extras already installed." -ForegroundColor Green
    }
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

# Conditional SSL
$sslArgs = @()
if (Test-Path "certs/cert.pem") {
    $sslArgs = @("--ssl-certfile", "certs/cert.pem", "--ssl-keyfile", "certs/key.pem")
    Write-Host "HTTPS enabled (certs/cert.pem found)" -ForegroundColor Green
} else {
    Write-Warning "certs/ not found, running HTTP only (for phone mic: enable chrome://flags/#unsafely-treat-insecure-origin-as-secure)"
}

# On Windows, ctranslate2's C extension (_ext.pyd) loads CUDA DLLs at import time
# via the OS loader — before any Python code in transcription.py can run.
# The nvidia-cublas-cu12 package installs cublas64_12.dll under site-packages/nvidia/cublas/bin/
# but does NOT register that directory (no __init__.py → no os.add_dll_directory()).
# Adding the nvidia bin dirs to PATH here ensures the OS DLL loader finds them.
$SitePackages = uv run python -c "import sysconfig; print(sysconfig.get_path('purelib'))" 2>$null
if ($SitePackages) {
    $NvidiaCublasBin = Join-Path $SitePackages "nvidia\cublas\bin"
    $NvidiaCudnnBin  = Join-Path $SitePackages "nvidia\cudnn\bin"
    $NvidiaCudartBin = Join-Path $SitePackages "nvidia\cuda_runtime\bin"
    foreach ($dir in @($NvidiaCublasBin, $NvidiaCudnnBin, $NvidiaCudartBin)) {
        if (Test-Path $dir) {
            $env:PATH = "$dir;$env:PATH"
            Write-Host "Added to PATH: $dir" -ForegroundColor Cyan
        }
    }
}

Write-Host "Starting Articulate ($Profile profile)..." -ForegroundColor Green
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --reload @sslArgs
