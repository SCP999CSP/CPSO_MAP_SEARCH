"""
CPSO 地址 Geocoding：将 doctor_addresses 中的地址转为经纬度。
使用 Google Geocoding API。

运行：python geocode.py [--limit N] [--dry-run]
环境变量：GOOGLE_GEOCODE_API_KEY（必填）、DATABASE_URL
"""
import argparse
import os
import re
from pathlib import Path

import psycopg2
import requests
import yaml

# 加载 .env（若存在）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cpso_map",
)
GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
FAILURES_PATH = Path(__file__).parent / "geocode_failures.yaml"


def _append_canada(addr: str) -> str:
    """地址末尾补充 Canada。"""
    if "Canada" in addr:
        return addr
    return f"{addr}, Canada"


def _max_number_in(s: str) -> int:
    """提取字符串中的最大数字，无则返回 0。"""
    nums = re.findall(r"\d+", s)
    return max((int(n) for n in nums), default=0)


def build_address_candidates(row: dict) -> list[str]:
    """
    构建 geocoding 候选地址列表。
    - street1（含最大门牌号的那段）为底线：不得去除，作为是否「可继续降级」的判断标准
    - 不去掉邮编
    - 不设层级限制：按「street number 从大到小」依次去除可删段，直到只剩 street1 为止
    """
    postal_pattern = re.compile(r"^[A-Z]\d[A-Z]\s*\d[A-Z]\d$", re.IGNORECASE)

    full = row.get("full_address")
    if full and str(full).strip():
        parts = [p.strip() for p in str(full).split(",") if p.strip()]
    else:
        parts = [
            row.get("street1"),
            row.get("street2"),
            row.get("street3"),
            row.get("street4"),
            row.get("city"),
            row.get("province"),
            row.get("postal_code"),
        ]
        parts = [str(p).strip() for p in parts if p and str(p).strip()]

    if not parts:
        return []

    # street1 = 含最大门牌号的那段（排除邮编），不可去除；若皆无数则取首段
    street1_idx = 0
    street1_num = -1
    for i, p in enumerate(parts):
        if not p or postal_pattern.match(p):
            continue
        n = _max_number_in(p)
        if n > street1_num:
            street1_num = n
            street1_idx = i

    # 可去除的索引：非 street1、非邮编，按门牌号从大到小排序
    removable = []
    for i, p in enumerate(parts):
        if i == street1_idx or not p or postal_pattern.match(p):
            continue
        removable.append((i, _max_number_in(p)))
    removable.sort(key=lambda x: -x[1])

    candidates = []
    seen = set()

    def add(remaining: list[str]) -> None:
        addr = _append_canada(", ".join(remaining))
        if addr not in seen:
            seen.add(addr)
            candidates.append(addr)

    add(parts)

    # 按 removable 顺序依次去除，直到只剩 street1 相关
    exclude = set()
    for i, _ in removable:
        exclude.add(i)
        remaining = [p for j, p in enumerate(parts) if j not in exclude]
        if remaining:
            add(remaining)

    return candidates


def _failure_record(row: dict, last_tried_address: str | None) -> dict:
    """构建失败记录字典，供写入 YAML。"""
    def _s(v):
        return str(v) if v is not None else None

    return {
        "doctor": {
            "cpso_number": _s(row.get("cpso_number")),
            "full_name": _s(row.get("full_name")),
            "registration_status": _s(row.get("registration_status")),
            "registration_status_label": _s(row.get("registration_status_label")),
        },
        "address": {
            "id": _s(row.get("id")),
            "full_address": _s(row.get("full_address")),
            "street1": _s(row.get("street1")),
            "street2": _s(row.get("street2")),
            "street3": _s(row.get("street3")),
            "street4": _s(row.get("street4")),
            "city": _s(row.get("city")),
            "province": _s(row.get("province")),
            "postal_code": _s(row.get("postal_code")),
            "phone": _s(row.get("phone")),
            "fax": _s(row.get("fax")),
            "is_primary": row.get("is_primary"),
            "not_in_practice": row.get("not_in_practice"),
        },
        "last_tried_address": last_tried_address,
    }


def geocode_address(address: str, api_key: str) -> tuple[float, float] | None:
    """调用 Google Geocoding API 获取经纬度。"""
    resp = requests.get(
        GOOGLE_GEOCODE_URL,
        params={"address": address, "key": api_key},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        return None
    loc = data["results"][0]["geometry"]["location"]
    return (float(loc["lat"]), float(loc["lng"]))


def main():
    parser = argparse.ArgumentParser(description="Geocode doctor addresses")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 条（0=全部）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不写入数据库")
    args = parser.parse_args()

    api_key = os.getenv("GOOGLE_GEOCODE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_GEOCODE_API_KEY environment variable is required.")
        return

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.cpso_number, a.is_primary, a.not_in_practice,
                       a.street1, a.street2, a.street3, a.street4,
                       a.city, a.province, a.postal_code, a.full_address,
                       a.phone, a.fax,
                       d.full_name, d.registration_status, d.registration_status_label
                FROM doctor_addresses a
                JOIN doctors d ON a.cpso_number = d.cpso_number
                WHERE a.latitude IS NULL AND a.longitude IS NULL
                ORDER BY a.is_primary DESC, a.created_at
                """
                + (" LIMIT %s" if args.limit else ""),
                (args.limit,) if args.limit else (),
            )
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description]
            rows = [dict(zip(columns, r)) for r in rows]

        if not rows:
            print("没有待 geocode 的地址。")
            return

        print(f"待处理: {len(rows)} 条")
        ok, fail = 0, 0
        failures: list[dict] = []

        for i, row in enumerate(rows):
            candidates = build_address_candidates(row)
            if not candidates:
                print(f"  [{i+1}] 跳过（无有效地址） id={row['id']}")
                fail += 1
                if not args.dry_run:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE doctor_addresses SET geocode_status = %s WHERE id = %s",
                            ("no_address", row["id"]),
                        )
                failures.append(_failure_record(row, None))
                continue

            result = None
            used_level = 0
            for level, addr in enumerate(candidates, 1):
                try:
                    result = geocode_address(addr, api_key)
                    if result:
                        used_level = level
                        break
                except Exception:
                    pass

            if result:
                lat, lon = result
                suffix = f" (#{used_level})" if used_level > 1 else ""
                print(f"  [{i+1}] OK{suffix}  {candidates[0][:45]}... -> ({lat:.6f}, {lon:.6f})")
                if not args.dry_run:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE doctor_addresses
                            SET latitude = %s, longitude = %s,
                                geocode_status = 'ok', geocoded_at = NOW()
                            WHERE id = %s
                            """,
                            (lat, lon, row["id"]),
                        )
                ok += 1
            else:
                print(f"  [{i+1}] 未找到（已试 {len(candidates)} 个候选） {candidates[0][:45]}...")
                if not args.dry_run:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE doctor_addresses SET geocode_status = %s WHERE id = %s",
                            ("not_found", row["id"]),
                        )
                fail += 1
                failures.append(_failure_record(row, candidates[-1]))

            if not args.dry_run:
                conn.commit()

        if failures and not args.dry_run:
            with open(FAILURES_PATH, "w", encoding="utf-8") as f:
                yaml.dump({"failures": failures}, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            print(f"\n失败记录已写入 {FAILURES_PATH}（共 {len(failures)} 条）")

        print(f"\n完成: 成功 {ok}, 失败 {fail}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
