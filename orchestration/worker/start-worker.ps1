<#
.SYNOPSIS
    Starts the GitHub-to-Antigravity Local Task Worker.

.DESCRIPTION
    Verifies all local prerequisites:
    - Python 3 installation
    - GitHub CLI (gh) installation and authentication
    - Repository remote origin verification
    - Antigravity CLI (agy) availability
    Then launches the task worker with graceful Ctrl+C handling.
#>

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting GitHub-to-Antigravity Local Task Worker" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Resolve repository root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkerDir = $ScriptDir
$RepoRoot = (Get-Item "$WorkerDir\..\..").FullName
Set-Location $RepoRoot

Write-Host "`n[1/5] Verifying working directory..." -ForegroundColor Yellow
Write-Host "      Repository Root: $RepoRoot" -ForegroundColor Gray

# 2. Verify Python
Write-Host "`n[2/5] Checking Python availability..." -ForegroundColor Yellow
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    Write-Host "ERROR: Python is not found in your PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ from https://www.python.org/downloads/ or via winget:" -ForegroundColor Gray
    Write-Host "  winget install --id Python.Python.3.10" -ForegroundColor Gray
    Exit 1
}
$PythonVersion = & python --version 2>&1
Write-Host "      Found: $PythonVersion" -ForegroundColor Green

# 3. Verify GitHub CLI & Authentication
Write-Host "`n[3/5] Checking GitHub CLI (gh) and authentication..." -ForegroundColor Yellow
$GhCmd = Get-Command gh -ErrorAction SilentlyContinue
if (-not $GhCmd) {
    Write-Host "ERROR: GitHub CLI ('gh') is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Install GitHub CLI from https://cli.github.com or via winget:" -ForegroundColor Gray
    Write-Host "  winget install --id GitHub.cli" -ForegroundColor Gray
    Exit 1
}

# Run auth status check
$GhAuth = & gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: GitHub CLI is not authenticated." -ForegroundColor Red
    Write-Host "Please authenticate your GitHub CLI account by running:" -ForegroundColor Yellow
    Write-Host "  gh auth login" -ForegroundColor Yellow
    Exit 1
}
Write-Host "      GitHub CLI is authenticated." -ForegroundColor Green

# 4. Verify Repository Identity
Write-Host "`n[4/5] Verifying repository identity..." -ForegroundColor Yellow
$ExpectedRepo = "nikhilsonwani34/apex-career-institute-automated"
$RemoteUrl = & git config --get remote.origin.url 2>&1
if ($RemoteUrl -notmatch "apex-career-institute-automated") {
    Write-Host "WARNING: Remote origin URL ('$RemoteUrl') does not match expected '$ExpectedRepo'." -ForegroundColor Yellow
    Write-Host "Make sure you are running inside the correct repository workspace." -ForegroundColor Yellow
} else {
    Write-Host "      Repository verified: $ExpectedRepo" -ForegroundColor Green
}

# 5. Verify Antigravity CLI (agy)
Write-Host "`n[5/5] Checking Antigravity CLI (agy)..." -ForegroundColor Yellow
$AgyCmd = Get-Command agy -ErrorAction SilentlyContinue

if (-not $AgyCmd) {
    # Check default install path in ~/.gemini/bin
    $DefaultGeminiBin = Join-Path $env:USERPROFILE ".gemini\bin"
    $DefaultAgyExe = Join-Path $DefaultGeminiBin "agy.exe"
    
    if (Test-Path $DefaultAgyExe) {
        Write-Host "      Found agy at $DefaultAgyExe (adding to current session PATH)." -ForegroundColor Gray
        $env:PATH = "$DefaultGeminiBin;$env:PATH"
        $AgyCmd = Get-Command agy -ErrorAction SilentlyContinue
    }
}

if (-not $AgyCmd) {
    Write-Host "ERROR: Antigravity CLI ('agy') was not found." -ForegroundColor Red
    Write-Host "Please install agy using the official installer in PowerShell:" -ForegroundColor Yellow
    Write-Host "  irm https://antigravity.google/cli/install.ps1 | iex" -ForegroundColor Yellow
    Write-Host "Or ensure C:\Users\$env:USERNAME\.gemini\bin is in your system PATH." -ForegroundColor Gray
    Exit 1
}

$AgyVersion = & agy --version 2>&1
Write-Host "      Found Antigravity CLI: $AgyVersion" -ForegroundColor Green

# Ensure config.json exists
$ConfigFile = Join-Path $WorkerDir "config.json"
$ConfigExample = Join-Path $WorkerDir "config.example.json"
if (-not (Test-Path $ConfigFile) -and (Test-Path $ConfigExample)) {
    Write-Host "`n[*] Creating initial config.json from config.example.json..." -ForegroundColor Gray
    Copy-Item $ConfigExample $ConfigFile
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  All prerequisites satisfied! Starting worker loop..." -ForegroundColor Cyan
Write-Host "  Press Ctrl+C at any time to shut down cleanly." -ForegroundColor Gray
Write-Host "==========================================================`n" -ForegroundColor Cyan

# Launch the worker
$WorkerScript = Join-Path $WorkerDir "task_worker.py"
try {
    & python $WorkerScript @args
} catch {
    Write-Host "`nWorker stopped." -ForegroundColor Gray
}

