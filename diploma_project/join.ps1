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
    Write-Host "      Dependencies installed from requirements.txt!" -ForegroundColor Green
} else {
    Write-Host "      requirements.txt not found, installing core packages..." -ForegroundColor Yellow
}

# Always ensure core packages are present (fallback)
python -m pip install flask cryptography netifaces-plus -q
Write-Host "      Core packages verified." -ForegroundColor Green

# Quick import test
$testResult = python -c "import flask, cryptography, netifaces; print('OK')" 2>&1
if ($testResult -ne "OK") {
    Write-Host "      ERROR: Package import failed: $testResult" -ForegroundColor Red
    Write-Host "      Try running: pip install flask cryptography netifaces-plus" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "      Import test passed!" -ForegroundColor Green

# ── Step 4: Start the node ───────────────────────────────────
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
Write-Host "  Network   : Auto-discovery (Multicast LAN)"
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# Launch node in a new visible window
Write-Host "  Launching node..." -ForegroundColor Gray
$args = "app.py", $nodeName, "$WEB_PORT"
Start-Process -FilePath "python" `
    -ArgumentList $args `
    -WorkingDirectory $projectPath

# Poll until Flask responds (max 40 seconds)
Write-Host "  Waiting for server to start" -NoNewline -ForegroundColor Yellow
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 1
    Write-Host "." -NoNewline -ForegroundColor Yellow
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:$WEB_PORT/api/status" `
            -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
        $ready = $true
        break
    } catch {}
}

Write-Host ""
if ($ready) {
    Write-Host "  Server is READY!" -ForegroundColor Green
    Start-Process "http://localhost:$WEB_PORT"
    Write-Host "  Browser opened at http://localhost:$WEB_PORT" -ForegroundColor Cyan
    Write-Host "  To stop the node: close the Python window." -ForegroundColor DarkGray
} else {
    Write-Host "  Server did not respond in 40s." -ForegroundColor Yellow
    Write-Host "  Check the Python window for errors." -ForegroundColor Yellow
    Write-Host "  Then try: http://localhost:$WEB_PORT" -ForegroundColor DarkGray
}

Read-Host "`nPress Enter to close this window"
