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
