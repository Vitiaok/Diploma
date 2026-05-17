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

# ── Step 1: Setup portable Python (no install needed!) ───────
Write-Host "[1/4] Setting up Python..." -ForegroundColor Yellow

$pythonDir = "$INSTALL_DIR\python"
$PY        = "$pythonDir\python.exe"

if (-not (Test-Path $PY)) {
    Write-Host "      Downloading portable Python 3.11..." -ForegroundColor Gray
    $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
    $pythonZip = "$env:TEMP\python-embed.zip"
    
    try {
        Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonZip -UseBasicParsing -ErrorAction Stop
    } catch {
        Write-Host "      ERROR: Could not download Python: $_" -ForegroundColor Red
        Read-Host "Press Enter to exit"; exit 1
    }
    
    New-Item -ItemType Directory -Path $pythonDir -Force | Out-Null
    Expand-Archive -Path $pythonZip -DestinationPath $pythonDir -Force
    
    # Enable site-packages (needed for pip to work in embedded Python)
    $pthFile = Get-ChildItem $pythonDir -Filter "python*._pth" | Select-Object -First 1
    if ($pthFile) {
        $content = Get-Content $pthFile.FullName -Raw
        $content = $content -replace '#import site', 'import site'
        Set-Content $pthFile.FullName $content -NoNewline
    }
    
    # Install pip into the embedded Python
    Write-Host "      Installing pip..." -ForegroundColor Gray
    $getPipUrl  = "https://bootstrap.pypa.io/get-pip.py"
    $getPipPath = "$env:TEMP\get-pip.py"
    Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath -UseBasicParsing
    & $PY $getPipPath -q
    
    Write-Host "      Portable Python ready!" -ForegroundColor Green
} else {
    Write-Host "      Portable Python already installed." -ForegroundColor Green
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
    & $PY -m pip install -r $reqFile -q
    Write-Host "      Dependencies installed from requirements.txt!" -ForegroundColor Green
} else {
    Write-Host "      requirements.txt not found, installing core packages..." -ForegroundColor Yellow
}

# Always ensure core packages are present
& $PY -m pip install flask cryptography netifaces-plus -q
Write-Host "      Core packages verified." -ForegroundColor Green

# Quick import test
$testResult = & $PY -c "import flask, cryptography, netifaces; print('OK')" 2>&1
if ($testResult -ne "OK") {
    Write-Host "      ERROR: Import failed: $testResult" -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
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

# Launch node in its own visible window
# (visible window is REQUIRED — Windows Firewall needs to show a dialog on first run!)
Write-Host "  Launching node in new window..." -ForegroundColor Gray
Write-Host "  >>> If Windows asks about Firewall — click ALLOW! <<<" -ForegroundColor Yellow

$proc = Start-Process -FilePath $PY `
    -ArgumentList @("app.py", $nodeName, "$WEB_PORT") `
    -WorkingDirectory $projectPath `
    -PassThru

# Poll until Flask responds (max 60 seconds)
Write-Host "  Waiting for server" -NoNewline -ForegroundColor Yellow
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    Write-Host "." -NoNewline -ForegroundColor Yellow

    # Check if process already died
    if ($proc.HasExited) {
        Write-Host ""
        Write-Host "  Node window closed unexpectedly (crash)." -ForegroundColor Red
        Write-Host "  Run manually to see error:" -ForegroundColor Yellow
        Write-Host "  cd '$projectPath'" -ForegroundColor Gray
        Write-Host "  & '$PY' app.py $nodeName $WEB_PORT" -ForegroundColor Gray
        Read-Host "`nPress Enter to exit"; exit 1
    }

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
    Write-Host "  Browser opened: http://localhost:$WEB_PORT" -ForegroundColor Cyan
    Write-Host "  To stop: close the node window." -ForegroundColor DarkGray
} else {
    Write-Host "  Timeout. Check the node window for errors." -ForegroundColor Yellow
    Write-Host "  Common fix: allow Python through Windows Firewall when prompted." -ForegroundColor Yellow
    Write-Host "  Or open manually: http://localhost:$WEB_PORT" -ForegroundColor Gray
}

Read-Host "`nPress Enter to close this installer window"
