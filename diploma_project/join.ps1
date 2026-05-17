# ================================================================
#  BlockChain File Share Node - Installer & Launcher
#  Usage: Right-click -> "Run with PowerShell"
#      OR: powershell -ExecutionPolicy Bypass -File join.ps1
# ================================================================

$GITHUB_REPO = "https://github.com/Vitiaok/Diploma/archive/refs/heads/main.zip"
$INSTALL_DIR = "$env:USERPROFILE\blockchain-node"
$WEB_PORT    = 8080

Clear-Host
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   BLOCKCHAIN FILE SHARE - Node Installer        " -ForegroundColor Cyan
Write-Host "   Decentralized P2P File Sharing Network        " -ForegroundColor DarkCyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Check Python ─────────────────────────────────────
Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "      OK: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "      Python not found! Please install Python 3.10+ from https://python.org" -ForegroundColor Red
    Write-Host "      Then re-run this script." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Step 2: Download project ─────────────────────────────────
Write-Host "[2/4] Downloading node software from GitHub..." -ForegroundColor Yellow

if (-not (Test-Path $INSTALL_DIR)) {
    New-Item -ItemType Directory -Path $INSTALL_DIR | Out-Null
}

$zipPath = "$env:TEMP\blockchain-node.zip"
try {
    Invoke-WebRequest -Uri $GITHUB_REPO -OutFile $zipPath -UseBasicParsing -ErrorAction Stop
    Write-Host "      Download complete." -ForegroundColor Green
} catch {
    Write-Host "      ERROR: Could not download. Check your internet connection." -ForegroundColor Red
    Write-Host "      Details: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Extract archive
Expand-Archive -Path $zipPath -DestinationPath $INSTALL_DIR -Force

# The zip extracts as "Diploma-main/" — find it and look for diploma_project inside
$repoRoot = Get-ChildItem $INSTALL_DIR -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1

# Try to find diploma_project subfolder
$projectPath = Join-Path $repoRoot.FullName "diploma_project"
if (-not (Test-Path $projectPath)) {
    # Maybe the code is directly in the root
    $projectPath = $repoRoot.FullName
}

Write-Host "      Project path: $projectPath" -ForegroundColor Green

# ── Step 3: Install dependencies ─────────────────────────────
Write-Host "[3/4] Installing Python dependencies..." -ForegroundColor Yellow
$reqFile = Join-Path $projectPath "requirements.txt"
if (Test-Path $reqFile) {
    python -m pip install -r $reqFile -q
    Write-Host "      Dependencies installed!" -ForegroundColor Green
} else {
    Write-Host "      WARNING: requirements.txt not found, skipping." -ForegroundColor Yellow
}

# ── Step 4: Choose node name and start ───────────────────────
Write-Host "[4/4] Setting up your node..." -ForegroundColor Yellow
Write-Host ""
$nodeName = Read-Host "  Enter your node name (e.g. 'alice', 'laptop-john')"
if ([string]::IsNullOrWhiteSpace($nodeName)) {
    $nodeName = "node-" + $env:COMPUTERNAME.ToLower() -replace '[^a-z0-9-]', ''
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  Node name : $nodeName"
Write-Host "  Web UI    : http://localhost:$WEB_PORT"
Write-Host "  Auto-discovery via local network (Multicast)"
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# Open browser after short delay
Start-Sleep -Seconds 2
Start-Process "http://localhost:$WEB_PORT"

# Run the node
Set-Location $projectPath
python app.py $nodeName $WEB_PORT
