# CPSO 医生地图

安大略省医生注册信息地图展示，数据来源 [CPSO](https://register.cpso.on.ca)。

## 项目结构

- `frontend/` - React + TypeScript 地图前端（Google Maps）
- `CPSO_WEB_DATA/` - 数据库、导出脚本、geocode 管道

## 快速开始

1. **前端**：`cd frontend && pnpm install && pnpm run dev`
2. **配置**：复制 `frontend/.env.example` 为 `frontend/.env`，填入 `VITE_GOOGLE_MAPS_API_KEY`
3. **数据**：参考 `CPSO_WEB_DATA/README.md` 启动 DB、导出 JSON

首次 clone 后若无 `doctors-addresses.json`，前端会自动使用示例数据。
