# dev.ps1 - Start Articulate backend + frontend dev server in two windows
# Usage: .\dev.ps1 [auto|laptop|pc|gemini]
param(
    [string]$Profile = "auto"
)

$root = $PSScriptRoot

Write-Host "Starting backend (run.ps1 $Profile)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$root\run.ps1", $Profile

Write-Host "Starting frontend (bun run dev)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; bun run dev"
