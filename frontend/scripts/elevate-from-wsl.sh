#!/usr/bin/env bash
# 在 WSL 中执行：会弹出 Windows UAC，点「是」后配置防火墙与端口转发
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAT="$(wslpath -w "$SCRIPT_DIR/open-port-5173.bat")"
echo "即将以管理员身份打开 Windows 命令行，请在 UAC 中点「是」…"
powershell.exe -Command "Start-Process cmd -Verb RunAs -ArgumentList '/c','$BAT'"
