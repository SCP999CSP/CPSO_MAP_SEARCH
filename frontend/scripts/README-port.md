# WSL2 下让局域网访问 Vite 开发服务器

Vite 在 WSL2 内运行，其他设备需通过 **Windows 主机 IP** 访问。需要：

1. Windows 防火墙放行 5173 / 5174 端口  
2. 将 Windows 的 5173、5174 转发到 WSL2  

## 方法一：在 WSL 里一键触发 UAC（推荐）

在 WSL 终端执行（会弹出 Windows UAC，点「是」）：

```bash
bash ~/projects/CPSO_MAP_search/frontend/scripts/elevate-from-wsl.sh
```

或进入 `frontend/scripts` 后：`bash ./elevate-from-wsl.sh`

## 方法二：运行批处理

1. 在资源管理器打开 `\\wsl$\...\frontend\scripts\`  
2. 右键 **`open-port-5173.bat`** → **以管理员身份运行**

## 方法三：PowerShell（管理员）

1. 以 **管理员身份** 打开 Windows PowerShell  
2. 进入项目目录：
   ```
   cd C:\...\CPSO_MAP_search\frontend\scripts
   ```
3. 执行：
   ```
   .\open-port-5173.ps1
   ```
   若提示执行策略受限，先运行：`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

## 方法二：手动执行命令

在 **管理员 PowerShell** 中：

```powershell
# 1. 防火墙放行
netsh advfirewall firewall add rule name="Vite 5173" dir=in action=allow protocol=TCP localport=5173

# 2. 获取 WSL2 IP（在 WSL 终端运行 hostname -I 取第一个 IP）
# 3. 端口转发（把 192.168.x.x 换成上面得到的 WSL2 IP）
netsh interface portproxy add v4tov4 listenport=5173 listenaddress=0.0.0.0 connectport=5173 connectaddress=192.168.x.x
```

**注意**：WSL2 重启后 IP 可能变化，需重新运行端口转发。

## 撤销

```powershell
netsh interface portproxy delete v4tov4 listenport=5173 listenaddress=0.0.0.0
netsh interface portproxy delete v4tov4 listenport=5174 listenaddress=0.0.0.0
netsh advfirewall firewall delete rule name="Vite Dev Server 5173"
netsh advfirewall firewall delete rule name="Vite Dev Server 5174"
```
