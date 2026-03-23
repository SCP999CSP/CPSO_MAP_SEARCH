# WSL2 端口 5173/5174 放行与转发
# 以管理员身份运行 PowerShell，执行: .\open-port-5173.ps1

Write-Host "Adding firewall rules for 5173 and 5174..." -ForegroundColor Cyan
netsh advfirewall firewall add rule name="Vite Dev Server 5173" dir=in action=allow protocol=TCP localport=5173
netsh advfirewall firewall add rule name="Vite Dev Server 5174" dir=in action=allow protocol=TCP localport=5174

$wslIp = (wsl hostname -I 2>$null).Trim().Split()[0]
if (-not $wslIp) {
    Write-Host "Could not get WSL2 IP. Make sure WSL is running." -ForegroundColor Red
    exit 1
}
Write-Host "WSL2 IP: $wslIp" -ForegroundColor Green

foreach ($port in @(5173, 5174)) {
    Write-Host "Port proxy ${port} -> ${wslIp}:${port}..." -ForegroundColor Cyan
    netsh interface portproxy delete v4tov4 listenport=$port listenaddress=0.0.0.0 2>$null
    netsh interface portproxy add v4tov4 listenport=$port listenaddress=0.0.0.0 connectport=$port connectaddress=$wslIp
}

Write-Host "Done. Other devices: http://<YOUR_WINDOWS_IP>:5173 or :5174" -ForegroundColor Green
