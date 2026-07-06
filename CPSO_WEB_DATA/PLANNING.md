# CPSO Doctor Map — 数据库规划

## 📌 目标

**本文件夹仅负责数据库设计与管理**：建立清晰、可扩展的 CPSO 医生数据库。  
FastAPI 后端及其他应用作为**独立项目**，通过 `DATABASE_URL` 连接本库。

---

## 📁 本仓库目录结构（仅数据库相关）

```
CPSO_WEB_DATA/
├── docker-compose.yml          # PostgreSQL 容器
├── .env.example                # 连接串模板（供外部调用方参考）
├── database/
│   ├── models.py               # SQLModel 表定义（Doctor, DoctorAddress）
│   ├── create_tables.py        # 建表脚本（删除旧表并创建）
│   └── migrations/             # 可选：后续 schema 变更
├── scripts/
│   ├── init_db.sh              # 执行 create_tables
│   └── connect_db.sh           # 快速连接
├── search.py                   # CPSO 爬虫/搜索（已有）
└── main.py                     # 入口（已有）
```

---

## 🗓 阶段规划

### Phase 1：数据库基础（当前）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 1.1 | 创建 `docker-compose.yml` | PostgreSQL 容器 |
| 1.2 | 创建 `database/models.py`（SQLModel） | 表结构 + 索引 |
| 1.3 | 配置 `.env.example` | 为 FastAPI 预留 `DATABASE_URL` |
| 1.4 | 启动并验证 | `docker-compose up -d` + 建表 |

**验收**：能通过 `psql` 连接并看到 `doctors`、`doctor_addresses` 表。

---

### Phase 2：数据导入

| 步骤 | 内容 | 产出 |
|------|------|------|
| 2.1 | 编写 ETL 脚本 | `search.py` → 解析 → 写入 DB |
| 2.2 | 批量插入逻辑 | 支持 `doctors` + `doctor_addresses` |
| 2.3 | 幂等 / 去重 | 按 `cpso_number` upsert |

---

### Phase 3：Geocoding 管道

| 步骤 | 内容 | 产出 |
|------|------|------|
| 3.1 | 选择服务 | Nominatim / Google / 其他 |
| 3.2 | 批量 geocode | 填充 `latitude`, `longitude` |
| 3.3 | 状态字段 | `geocode_status`, `geocoded_at` |

---

### Phase 4：外部 FastAPI 项目（与本仓库分离）

FastAPI 后端部署在**独立项目**中，通过 `DATABASE_URL` 连接本库。本仓库不做 API 实现。

| 步骤 | 内容 | 产出 |
|------|------|------|
| 4.1 | 在外部项目中新建 FastAPI 应用 | 独立代码库 |
| 4.2 | 配置 `DATABASE_URL` 指向本库 | 连接 `cpso_map` |
| 4.3 | 使用本 schema 设计 API | 示例：<br>• `GET /doctors?city=Toronto`<br>• `GET /doctors/{cpso_number}`<br>• `GET /addresses?lat=&lng=&radius=` |

---

## 🔗 供外部调用（FastAPI 等）

外部项目连接本库时使用以下信息。

### 1. 数据库连接字符串

```env
# .env.example（本仓库提供，供调用方复制参考）
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cpso_map
```

外部 FastAPI 项目通过 `sqlalchemy.create_engine(DATABASE_URL)` 或 async 驱动连接。

### 2. 表与 API 的映射

| 表 | 主要用途 | 建议 API |
|----|----------|----------|
| `doctors` | 医生信息 | `GET /doctors`, `GET /doctors/{cpso}` |
| `doctor_addresses` | 地图点位、搜索 | `GET /addresses`, 按城市/邮编/经纬度筛选 |

### 3. 索引已为查询优化

- `idx_doctor_addresses_cpso_number` → 按医生查地址
- `idx_doctor_addresses_city` → 按城市筛选
- `idx_doctor_addresses_postal_code` → 按邮编筛选
- `idx_doctor_addresses_is_primary` → 主地址优先

### 4. 预留字段

- `latitude` / `longitude` → 地图前端 / 地理搜索
- `geocode_status` → 可做过滤（仅返回已 geocode 的地址）

---

## 🐳 Phase 1 具体步骤

### 1. 启动 PostgreSQL

```bash
docker-compose up -d
```

### 2. 执行建表（SQLModel）

```bash
python -m database.create_tables
# 或
bash scripts/init_db.sh
```

### 3. 验证

```bash
docker exec -it cpso_postgres psql -U postgres -d cpso_map -c "\dt"
```

应看到 `doctors`、`doctor_addresses`。

---

## 📦 本仓库依赖

仅用于 ETL、Geocoding 等数据库管理相关脚本：

```
requests          # CPSO 爬虫（search.py）
psycopg2-binary   # 写入 PostgreSQL
sqlmodel          # 表定义与建表（SQLModel = SQLAlchemy + Pydantic）
```

FastAPI、asyncpg 等由**外部调用项目**自行管理。

---

## ✅ 小结

- ✅ 本仓库：**仅负责数据库设计与数据管理**
- ✅ PostgreSQL (Docker) + 双表 schema
- ✅ lat/lng 初始 NULL，后续 geocode
- ✅ 索引已设计
- ✅ `.env.example` 供外部项目参考连接串
- ⏳ FastAPI 等在独立项目中实现
