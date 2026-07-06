"""
从 CPSO 医生详情页抓取附加地址，写入 doctor_addresses 表。
仅处理 additional_address_count > 0 且「应有数量 != 数据库已有数量」的医生，避免无效遍历。
地址存储时用逗号分隔多行（如 br 分隔），便于 geo 搜索。

运行：python fetch_additional_addresses.py [--limit N] [--dry-run]
"""
import argparse
import os
import re
import time
import uuid

import psycopg2
import requests
from bs4 import BeautifulSoup

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cpso_map",
)
BASE_URL = "https://register.cpso.on.ca"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def _extract_postal_code(text: str) -> str | None:
    m = re.search(r"[A-Z]\d[A-Z]\s*\d[A-Z]\d", text, re.IGNORECASE)
    return m.group(0).strip() if m else None


def _normalize_address_for_geo(addr_text: str) -> str:
    """
    将多行地址（如 <br> 分隔）转为逗号分隔，便于 geo 搜索。
    例如: "555 Mapleview Drive West\\nUnit 6\\nBarrie Ontario L4N 8G5"
    -> "555 Mapleview Drive West, Unit 6, Barrie Ontario L4N 8G5"
    """
    addr_text = (addr_text or "").strip()
    parts = [p.strip() for p in re.split(r"[\n\r]+|\s{2,}", addr_text) if p.strip()]
    return ", ".join(parts) if parts else addr_text


def _parse_address_block(addr_text: str, phone: str | None, fax: str | None) -> dict:
    """
    从地址文本解析 street1-4, city, province, postal_code。
    页面可能将多行拼接，以邮编为锚点拆分 city/province。
    full_address 使用逗号分隔，便于 geo 搜索。
    """
    addr_text = (addr_text or "").strip()
    full = _normalize_address_for_geo(addr_text)
    postal_code = _extract_postal_code(addr_text)
    street1 = street2 = street3 = street4 = city = province = None

    if postal_code:
        pc_pos = addr_text.upper().find(postal_code.upper())
        before_pc = addr_text[:pc_pos].strip() if pc_pos >= 0 else addr_text
        match = re.search(r"(.+?)\s+(Ontario|ON)\s*$", before_pc, re.IGNORECASE)
        if match:
            city_part = match.group(1).strip()
            province = "ON"
            # Split "80 Bond StreetToronto" -> street="80 Bond Street", city="Toronto"
            street_city = re.search(
                r"^(.+?)(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln|Court|Ct|Way|Crescent|Cres|Place|Pl)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)$",
                city_part,
            )
            if street_city:
                street_part = (street_city.group(1) + street_city.group(2)).strip()
                city = street_city.group(3).strip()
            else:
                street_part = city_part
        else:
            street_part = before_pc
        lines = [s.strip() for s in re.split(r"\s{2,}|\n", street_part) if s.strip()]
        if not lines:
            lines = [street_part] if street_part else []
        street1 = lines[0] if lines else None
        street2 = lines[1] if len(lines) > 1 else None
        street3 = lines[2] if len(lines) > 2 else None
        street4 = lines[3] if len(lines) > 3 else None
    elif addr_text:
        street1 = addr_text

    if phone and "No Information Available" in str(phone):
        phone = None
    if fax and "No Information Available" in str(fax):
        fax = None

    return {
        "full_address": full or None,
        "street1": street1,
        "street2": street2,
        "street3": street3,
        "street4": street4,
        "city": city,
        "province": province or "ON",
        "postal_code": postal_code,
        "phone": str(phone).strip() if phone else None,
        "fax": str(fax).strip() if fax else None,
        "is_primary": False,
        "not_in_practice": False,
    }


def fetch_additional_addresses(cpso_number: str) -> list[dict]:
    """
    从 physician-info 页面抓取附加地址（仅 VIEW ADDITIONAL BUSINESS LOCATIONS 之后的 Address 块）。
    """
    url = f"{BASE_URL}/physician-info/?cpsonum={cpso_number}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text("\n", strip=True)

    idx = text.find("VIEW ADDITIONAL BUSINESS LOCATIONS")
    if idx < 0:
        return []
    search_text = text[idx:]

    # 地址块以 Address: 开始，到 Phone: 和可选 Fax:，下一块可能是 Address: 或新 section (Specialties 等)
    addresses = []
    pattern = re.compile(
        r"Address:\s*(.*?)\s*Phone:\s*([^\n]+)"
        r"(?:\s*Extension:\s*([^\n]+))?"
        r"(?:\s*Fax:\s*([^\n]+))?"
        r"(?=\s*(?:Address:|Specialties|Medical Licences|Hospital Privileges|Corporation|Business Address:|Practice Conditions|$))",
        re.S | re.IGNORECASE,
    )
    for m in pattern.finditer(search_text):
        addr_text = m.group(1).strip()
        phone = m.group(2).strip() if m.group(2) else None
        ext = m.group(3).strip() if m.group(3) else None
        fax = m.group(4).strip() if m.group(4) else None
        if phone and ext:
            phone = f"{phone} ext {ext}"
        if not addr_text or "Primary Business Location" in addr_text:
            continue
        parsed = _parse_address_block(addr_text, phone, fax)
        parsed["cpso_number"] = cpso_number
        addresses.append(parsed)

    seen = set()
    dedup = []
    for a in addresses:
        key = a.get("full_address") or (a.get("postal_code") or "")
        if key and key not in seen:
            seen.add(key)
            dedup.append(a)
    return dedup


def insert_address(conn, cpso_number: str, addr: dict) -> bool:
    """插入地址，若已存在则跳过。与 search.py 逻辑一致。"""
    with conn.cursor() as cur:
        full = addr.get("full_address")
        if full:
            cur.execute(
                "SELECT 1 FROM doctor_addresses WHERE cpso_number = %s AND full_address = %s",
                (cpso_number, full),
            )
            if cur.fetchone():
                return False
        elif addr.get("postal_code"):
            cur.execute(
                "SELECT 1 FROM doctor_addresses WHERE cpso_number = %s AND postal_code = %s AND (full_address IS NULL OR full_address = '')",
                (cpso_number, addr["postal_code"]),
            )
            if cur.fetchone():
                return False

        cur.execute(
            """
            INSERT INTO doctor_addresses (
                id, cpso_number, is_primary, not_in_practice,
                street1, street2, street3, street4,
                city, province, postal_code, full_address,
                phone, fax, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                str(uuid.uuid4()),
                cpso_number,
                addr.get("is_primary", False),
                addr.get("not_in_practice", False),
                addr.get("street1"),
                addr.get("street2"),
                addr.get("street3"),
                addr.get("street4"),
                addr.get("city"),
                addr.get("province"),
                addr.get("postal_code"),
                addr.get("full_address"),
                addr.get("phone"),
                addr.get("fax"),
            ),
        )
        return True


def load_doctors_with_additional(conn, limit: int = 0) -> list[tuple[str, int]]:
    """
    从数据库查询 additional_address_count > 0 且「应有数量 != 数据库已有数量」的医生。
    仅返回需要补充抓取的记录。
    """
    with conn.cursor() as cur:
        sql = """
            SELECT d.cpso_number, d.additional_address_count
            FROM doctors d
            LEFT JOIN (
                SELECT cpso_number, COUNT(*) AS cnt
                FROM doctor_addresses
                WHERE is_primary = FALSE
                GROUP BY cpso_number
            ) da ON d.cpso_number = da.cpso_number
            WHERE d.additional_address_count > 0
              AND COALESCE(da.cnt, 0) != d.additional_address_count
            ORDER BY d.cpso_number
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
        cur.execute(sql)
        return [(row[0], row[1]) for row in cur.fetchall()]


def get_address_count(conn, cpso_number: str) -> int:
    """查询该医生在 doctor_addresses 中的地址数量。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM doctor_addresses WHERE cpso_number = %s",
            (cpso_number,),
        )
        return cur.fetchone()[0]


def get_additional_address_count(conn, cpso_number: str) -> int:
    """查询该医生在 doctor_addresses 中已存在的附加地址数量（is_primary = false）。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM doctor_addresses WHERE cpso_number = %s AND is_primary = FALSE",
            (cpso_number,),
        )
        return cur.fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description="Fetch additional addresses from CPSO physician pages")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 个医生（0=全部）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不写入数据库")
    args = parser.parse_args()

    conn = psycopg2.connect(DATABASE_URL)
    try:
        doctor_list = load_doctors_with_additional(conn, args.limit)
    except Exception as e:
        print(f"查询数据库失败: {e}")
        conn.close()
        return
    if not doctor_list:
        print("未找到需补充的医生（应有数量与数据库不符的 additional_address_count > 0 记录）")
        conn.close()
        return

    print(f"待处理: {len(doctor_list)} 个医生（应有数量与数据库不符）")
    if args.dry_run:
        print("（dry-run 模式，不写入数据库）")
    total_inserted = 0
    try:
        for i, (cpso, add_count) in enumerate(doctor_list, 1):
            try:
                db_existing = get_additional_address_count(conn, cpso)
                addrs = fetch_additional_addresses(cpso)
                inserted = 0
                for addr in addrs:
                    if args.dry_run:
                        inserted += 1
                    elif insert_address(conn, cpso, addr):
                        inserted += 1
                total_inserted += inserted
                print(
                    f"  [{i}/{len(doctor_list)}] {cpso}: 应有 {add_count}, "
                    f"数据库已有 {db_existing}, 抓取 {len(addrs)}, 插入 {inserted}"
                )
            except Exception as e:
                print(f"  [{i}/{len(doctor_list)}] {cpso}: 错误 - {e}")
            if conn and not args.dry_run:
                conn.commit()
            time.sleep(0.5)

        print(f"\n完成: 共插入 {total_inserted} 条附加地址")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
