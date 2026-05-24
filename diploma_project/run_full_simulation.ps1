param(
    [int]$nodes = 5,
    [int]$transfers = 10,
    [int]$filesizeKB = 100
)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " FULL AUTOMATED SCALABILITY SIMULATION" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Nodes: $nodes | Concurrent Transfers: $transfers | File Size: $filesizeKB KB" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Launching $nodes nodes in the background..." -ForegroundColor Green
for ($i = 1; $i -le $nodes; $i++) {
    Start-Process python -ArgumentList "app.py" -WindowStyle Minimized
    Start-Sleep -Seconds 1
}

Write-Host "[2/3] Waiting 15 seconds for nodes to auto-discover each other..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

Write-Host "[3/3] Triggering Traffic Simulator..." -ForegroundColor Green
python analysis\traffic_simulator.py $transfers $filesizeKB

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Simulation Finished!" -ForegroundColor Green
Write-Host " Check your metrics CSV files in the project folder." -ForegroundColor Yellow
Write-Host " To clean up, simply close the minimized Python windows in your taskbar." -ForegroundColor Yellow
