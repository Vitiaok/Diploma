param(
    [int]$count = 5
)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Starting Local P2P Cluster ($count nodes)" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

for ($i = 1; $i -le $count; $i++) {
    Write-Host "Launching Node $i..." -ForegroundColor Green
    
    # Запускаємо процес у новому мінімізованому вікні, щоб не заважало
    Start-Process python -ArgumentList "app.py" -WindowStyle Minimized
    
    # Чекаємо секунду, щоб порти розподілилися без конфліктів та ноди встигли зв'язатися
    Start-Sleep -Seconds 1 
}

Write-Host ""
Write-Host "Done! $count nodes are running." -ForegroundColor Yellow
Write-Host "To close them, simply close the minimized Python windows in your taskbar." -ForegroundColor Yellow
