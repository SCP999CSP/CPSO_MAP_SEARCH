# CPSO 医生数据库

CPSO（College of Physicians and Surgeons of Ontario）安大略省医生注册信息数据库，用于地图展示与地址搜索。数据来源：[register.cpso.on.ca](https://register.cpso.on.ca)。

---

## 数据库概览

| 项目 | 说明 |
|------|------|
| **引擎** | PostgreSQL |
| **数据库名** | `cpso_map` |
| **表** | `doctors`、`doctor_addresses`（一对多） |
| **连接串** | `postgresql://postgres:postgres@localhost:5432/cpso_map` |

---

## 表结构

### 1. `doctors` 医生表

| 字段 | 类型 | 说明 |
|------|------|------|
| `cpso_number` | PK, varchar(20) | CPSO 注册号，唯一标识 |
| `full_name` | varchar | 姓名（如 "Kulpa, Janus"） |
| `registration_status` | varchar, nullable | 注册状态（如 "Active"） |
| `registration_status_label` | varchar, nullable | 状态标签（如 "active"） |
| `additional_address_count` | int, default 0 | 附加地址数量 |
| `created_at` | timestamp | 创建时间 |
| `updated_at` | timestamp | 更新时间 |

### 2. `doctor_addresses` 地址表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | PK, uuid | 主键 |
| `cpso_number` | FK → doctors.cpso_number | 关联医生 |
| `is_primary` | bool, default false | 是否主地址 |
| `not_in_practice` | bool, default false | 是否已停业 |
| `street1` | varchar, nullable | 街道行 1（门牌+路名） |
| `street2` | varchar, nullable | 街道行 2 |
| `street3` | varchar, nullable | 街道行 3 |
| `street4` | varchar, nullable | 街道行 4 |
| `city` | varchar, nullable | 城市 |
| `province` | varchar, nullable | 省份（多为 ON） |
| `postal_code` | varchar, nullable | 邮编（加拿大格式 A1A 1A1） |
| `full_address` | varchar, nullable | 完整地址拼接 |
| `phone` | varchar, nullable | 电话 |
| `fax` | varchar, nullable | 传真 |
| `latitude` | float, nullable | 纬度（geocode 后填充） |
| `longitude` | float, nullable | 经度（geocode 后填充） |
| `geocode_status` | varchar, nullable | geocode 状态：`ok` / `not_found` / `no_address` / `error:...` |
| `geocoded_at` | timestamp, nullable | geocode 完成时间 |
| `created_at` | timestamp | 创建时间 |
| `updated_at` | timestamp | 更新时间 |

### 关系与索引

- **关系**：`doctor_addresses.cpso_number` → `doctors.cpso_number`（一个医生可有多条地址）
- **索引**：`cpso_number`、`city`、`postal_code`、`is_primary`，便于按城市、邮编、主地址筛选

---

## 数据管道

```
CPSO API (search) → search.py → doctors + doctor_addresses
                                     ↓
                              geocode.py → 填充 latitude, longitude
```

| 脚本 | 作用 |
|------|------|
| `search.py` | 调用 CPSO 搜索 API，从 `search_config.yaml` 读取 `postal_codes`，依次搜索并写入；邮编前四位与输入不符的记录写入 `search_postal_mismatch.yaml` |
| `geocode.py` | 对 `latitude IS NULL` 的地址调用 Google Geocoding API 填充经纬度，失败记录写入 `geocode_failures.yaml` |

`search_config.yaml` 示例：

```yaml
postal_codes:
  - "M5A 4"
  - "L4X 2V3"
doctor_type: "Family Doctor"
languages: "ENGLISH"
include_inactive: true
```

---

## 连接与查询

### 连接

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cpso_map
GOOGLE_GEOCODE_API_KEY=...   # geocode.py 必填
```

### 常用 SQL 示例

```sql
-- 按城市查医生
SELECT d.full_name, d.cpso_number, a.full_address, a.city, a.phone
FROM doctors d
JOIN doctor_addresses a ON d.cpso_number = a.cpso_number
WHERE a.city ILIKE '%Toronto%' AND a.is_primary
ORDER BY d.full_name;

-- 按邮编查
SELECT * FROM doctor_addresses WHERE postal_code LIKE 'M5A%';

-- 已 geocode 的地址（可用于地图）
SELECT id, cpso_number, full_address, latitude, longitude, city
FROM doctor_addresses
WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- 统计
SELECT COUNT(*) FROM doctors;
SELECT city, COUNT(*) FROM doctor_addresses GROUP BY city ORDER BY COUNT(*) DESC;
```

---

## 启动与维护

### 启动数据库

```bash
docker-compose up -d
python -m database.create_tables
```

### 导入与 geocode

```bash
python search.py
python geocode.py
```

### 连接 psql

```bash
docker exec -it cpso_postgres psql -U postgres -d cpso_map
```

---

## 供 AI / 外部调用

- **读**：通过 `DATABASE_URL` 连接，查询 `doctors`、`doctor_addresses`
- **写**：本仓库的 `search.py`、`geocode.py` 负责写入；外部仅建议读
- **建议 API**：`GET /doctors`、`GET /doctors/{cpso_number}`、`GET /addresses?city=&postal_code=&lat=&lng=&radius=`
