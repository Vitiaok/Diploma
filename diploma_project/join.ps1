# ═══════════════════════════════════════════════════════════════
#  BlockChain File Share Node - Installer & Launcher
#  Usage: Right-click -> Run with PowerShell
#         або: powershell -ExecutionPolicy Bypass -File join.ps1
# ═══════════════════════════════════════════════════════════════

$GITHUB_REPO = "https://github.com/Vitiaok/diploma_project/archive/refs/heads/main.zip"
$INSTALL_DIR = "$env:USERPROFILE\blockchain-node"
$WEB_PORT    = 8080

Write-Host ""
Write-Host "  ██████╗ ██╗      ██████╗  ██████╗██╗  ██╗ ██████╗██╗  ██╗ █████╗ ██╗███╗   ██╗" -ForegroundColor Cyan
Write-Host "  ██╔══██╗██║     ██╔═══██╗██╔════╝██║ ██╔╝██╔════╝██║  ██║██╔══██╗██║████╗  ██║" -ForegroundColor Cyan
Write-Host "  ██████╔╝██║     ██║   ██║██║     █████╔╝ ██║     ███████║███████║██║██╔██╗ ██║" -ForegroundColor Cyan
Write-Host "  ██╔══██╗██║     ██║   ██║██║     ██╔═██╗ ██║     ██╔══██║██╔══██║██║██║╚██╗██║" -ForegroundColor Cyan
Write-Host "  ██████╔╝███████╗╚██████╔╝╚██████╗██║  ██╗╚██████╗██║  ██║██║  ██║██║██║ ╚████║" -ForegroundColor Cyan
Write-Host "  ╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝" -ForegroundColor Cyan
Write-Host "                         Decentralized File Sharing Node" -ForegroundColor DarkCyan
Write-Host ""

# ── Крок 1: Перевіряємо Python ──────────────────────────────────
Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "      Found: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "      Python not found! Installing via winget..." -ForegroundColor Red
    winget install Python.Python.3.11 -e --silent
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine")
}

# ── Крок 2: Завантажуємо проект ─────────────────────────────────
Write-Host "[2/4] Downloading node software..." -ForegroundColor Yellow
if (-not (Test-Path $INSTALL_DIR)) {
    New-Item -ItemType Directory -Path $INSTALL_DIR | Out-Null
}

$zipPath = "$env:TEMP\blockchain-node.zip"
Invoke-WebRequest -Uri $GITHUB_REPO -OutFile $zipPath -UseBasicParsing
Expand-Archive -Path $zipPath -DestinationPath $INSTALL_DIR -Force

# Знаходимо розпаковану папку
$extracted = Get-ChildItem $INSTALL_DIR -Directory | Select-Object -First 1
$projectPath = $extracted.FullName
Write-Host "      Downloaded to: $projectPath" -ForegroundColor Green

# ── Крок 3: Встановлюємо залежності ─────────────────────────────
Write-Host "[3/4] Installing dependencies..." -ForegroundColor Yellow
Set-Location $projectPath
python -m pip install -r requirements.txt -q
Write-Host "      Dependencies installed!" -ForegroundColor Green

# ── Крок 4: Вибір імені вузла ───────────────────────────────────
Write-Host "[4/4] Setting up your node..." -ForegroundColor Yellow
Write-Host ""
$nodeName = Read-Host "  Enter your node name (e.g. 'alice', 'laptop-bob')"
if ([string]::IsNullOrWhiteSpace($nodeName)) {
    $nodeName = "node-" + $env:COMPUTERNAME.ToLower()
}

Write-Host ""
Write-Host "  Starting node '$nodeName'..." -ForegroundColor Green
Write-Host "  Web interface will open at: http://localhost:$WEB_PORT" -ForegroundColor Cyan
Write-Host "  The node will auto-discover peers on the local network." -ForegroundColor DarkGray
Write-Host ""

# Відкриваємо браузер після запуску
Start-Process "http://localhost:$WEB_PORT"

# Запускаємо вузол
python app.py $nodeName $WEB_PORT
