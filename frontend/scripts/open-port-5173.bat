@echo off
:: 以管理员身份运行：放行 5173/5174 并转发到 WSL2
echo Getting WSL2 IP...
for /f %%i in ('wsl hostname -I') do set WSL_IP=%%i& goto :got_ip
:got_ip
echo WSL2 IP: %WSL_IP%
echo.

echo Adding firewall rules for 5173 and 5174...
netsh advfirewall firewall add rule name="Vite Dev Server 5173" dir=in action=allow protocol=TCP localport=5173
netsh advfirewall firewall add rule name="Vite Dev Server 5174" dir=in action=allow protocol=TCP localport=5174
echo.

echo Setting port proxy 5173 -^> WSL...
netsh interface portproxy delete v4tov4 listenport=5173 listenaddress=0.0.0.0 2>nul
netsh interface portproxy add v4tov4 listenport=5173 listenaddress=0.0.0.0 connectport=5173 connectaddress=%WSL_IP%
echo.

echo Setting port proxy 5174 -^> WSL...
netsh interface portproxy delete v4tov4 listenport=5174 listenaddress=0.0.0.0 2>nul
netsh interface portproxy add v4tov4 listenport=5174 listenaddress=0.0.0.0 connectport=5174 connectaddress=%WSL_IP%
echo.

echo Done. Other devices: http://^<Windows_WiFi_IP^>:5173 or :5174
echo.
pause
