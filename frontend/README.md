# CPSO 医生地图

React + TypeScript 前端，在地图上展示医生地址（经纬度来自 `doctor_addresses` 表）。

## 功能

- 地图上显示医生位置（圆点）
- 鼠标悬停：显示姓名、电话、传真
- 点击：跳转到医生详情页

## 数据

默认使用 `public/doctors-addresses.json`。使用真实数据前需运行导出脚本：

```bash
cd ../CPSO_WEB_DATA
python3 export_to_json.py --limit 200   # 可选 --limit 限制条数
```

输出会写入 `frontend/public/doctors-addresses.json`。

## 启动

```bash
npm install
npm run dev
```

访问 http://localhost:5173

## Docker

多阶段构建：Node 编译静态资源，nginx 提供 `dist`，并配置 SPA 回退（`/doctor/...` 等路由）。

```bash
# 构建（Google Maps Key 在构建时写入前端包，勿把含真实 Key 的镜像推送到公开仓库）
docker build -t cpso-frontend \
  --build-arg VITE_GOOGLE_MAPS_API_KEY=你的Key \
  .

docker run --rm -p 8080:80 cpso-frontend
```

或使用 Compose（可在本目录放 `.env`，含 `VITE_GOOGLE_MAPS_API_KEY=...`）：

```bash
docker compose up --build
```

浏览器访问 http://localhost:8080

镜像内的 `doctors-addresses.json` 来自构建时 `public/` 目录；更新数据后需重新 `docker build`。
