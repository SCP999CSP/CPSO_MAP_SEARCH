"""
按 CPSO 号打开医生详情页，同一页写入地址和医生资料。

尚无地址的医生：整组替换地址（主地址 is_primary=true），并写入
gender、medical_school、languages_spoken、graduate_data。
已有地址的医生：不改地址，只补这四项仍为空的资料。

运行：python fetch_doctor_details.py [--limit N] [--dry-run]
"""
import argparse
import datetime
import os
import re
import time
import uuid

import psycopg2
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cpso_spdoc",
)
BASE_URL = "https://register.cpso.on.ca"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

PRIMARY_RE = re.compile(
    r"Primary Business Location:\s*(.*?)\s*Business Email:\s*[^\n]*\s*Phone:\s*([^\n]+)"
    r"(?:\s*Extension:\s*([^\n]+))?"
    r"(?:\s*Fax:\s*([^\n]+))?",
    re.S | re.IGNORECASE,
)
PRIMARY_FALLBACK_RE = re.compile(
    r"Primary Business Location:\s*(.*?)\s*Phone:\s*([^\n]+)"
    r"(?:\s*Extension:\s*([^\n]+))?"
    r"(?:\s*Fax:\s*([^\n]+))?",
    re.S | re.IGNORECASE,
)
YEAR_MIN = 1950

ADDITIONAL_RE = re.compile(
    r"Address:\s*(.*?)\s*Phone:\s*([^\n]+)"
    r"(?:\s*Extension:\s*([^\n]+))?"
    r"(?:\s*Fax:\s*([^\n]+))?"
    r"(?=\s*(?:Address:|Specialties|Medical Licences|Hospital Privileges|Corporation|Business Address:|Practice Conditions|$))",
    re.S | re.IGNORECASE,
)


def _extract_postal_code(text: str) -> str | None:
    m = re.search(r"[A-Z]\d[A-Z]\s*\d[A-Z]\d", text, re.IGNORECASE)
    return m.group(0).strip() if m else None


def _normalize_address_for_geo(addr_text: str) -> str:
    """将多行地址转为逗号分隔。"""
    addr_text = (addr_text or "").strip()
    parts = [p.strip() for p in re.split(r"[\n\r]+|\s{2,}", addr_text) if p.strip()]
    return ", ".join(parts) if parts else addr_text


def _parse_address_block(addr_text: str, phone: str | None, fax: str | None) -> dict:
    """从地址文本解析 street1-4, city, province, postal_code。"""
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


def _phone_with_extension(phone: str | None, ext: str | None) -> str | None:
    phone = phone.strip() if phone else None
    ext = ext.strip() if ext else None
    if phone and ext:
        return f"{phone} ext {ext}"
    return phone


def _parse_primary(text: str) -> dict | None:
    """解析 Primary Business Location，取页面中第一次出现。"""
    match = PRIMARY_RE.search(text) or PRIMARY_FALLBACK_RE.search(text)
    if not match:
        return None
    addr_text = match.group(1).strip()
    if not addr_text:
        return None
    phone = _phone_with_extension(match.group(2), match.group(3))
    fax = match.group(4).strip() if match.group(4) else None
    parsed = _parse_address_block(addr_text, phone, fax)
    parsed["is_primary"] = True
    return parsed


def _parse_additional(text: str) -> list[dict]:
    """解析 VIEW ADDITIONAL BUSINESS LOCATIONS 之后的 Address 块。"""
    idx = text.find("VIEW ADDITIONAL BUSINESS LOCATIONS")
    if idx < 0:
        return []
    addresses = []
    for match in ADDITIONAL_RE.finditer(text[idx:]):
        addr_text = match.group(1).strip()
        phone = _phone_with_extension(match.group(2), match.group(3))
        fax = match.group(4).strip() if match.group(4) else None
        if not addr_text or "Primary Business Location" in addr_text:
            continue
        addresses.append(_parse_address_block(addr_text, phone, fax))
    return addresses


def _address_key(addr: dict) -> str:
    return addr.get("full_address") or addr.get("postal_code") or ""


def fetch_page_text(cpso_number: str) -> str:
    """打开 physician-info 页，返回纯文本。"""
    url = f"{BASE_URL}/physician-info/?cpsonum={cpso_number}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text("\n", strip=True)


def _first_field_value(page_text: str, label: str) -> str | None:
    match = re.search(rf"{re.escape(label)}:\s*([^\n]+)", page_text, re.IGNORECASE)
    if not match:
        return None
    val = match.group(1).strip()
    if not val or "no information available" in val.lower():
        return None
    return val


def graduate_year_from_medical_school(medical_school: str) -> str | None:
    """医学院字符串末尾四位为合理年份时返回该年份，否则返回 None。"""
    s = (medical_school or "").rstrip()
    if len(s) < 4 or not s[-4:].isdigit():
        return None
    year = int(s[-4:])
    year_max = datetime.datetime.now().year + 1
    if year < YEAR_MIN or year > year_max:
        return None
    return s[-4:]


def profile_from_text(text: str) -> dict[str, str | None]:
    """从同一页文本解析性别、医学院、语言和毕业年份。"""
    medical_school = _first_field_value(text, "Medical School")
    graduate_data = graduate_year_from_medical_school(medical_school) if medical_school else None
    return {
        "gender": _first_field_value(text, "Gender"),
        "medical_school": medical_school,
        "languages_spoken": _first_field_value(text, "Languages Spoken"),
        "graduate_data": graduate_data,
    }


def addresses_from_text(cpso_number: str, text: str) -> list[dict]:
    """从页面文本解析主地址和附加地址。主地址在前，并按全文去重。"""
    results: list[dict] = []
    seen: set[str] = set()

    primary = _parse_primary(text)
    if primary:
        primary["cpso_number"] = cpso_number
        key = _address_key(primary)
        if key:
            seen.add(key)
        results.append(primary)

    for addr in _parse_additional(text):
        addr["is_primary"] = False
        addr["cpso_number"] = cpso_number
        key = _address_key(addr)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        results.append(addr)
    return results


def fetch_practice_addresses(cpso_number: str) -> list[dict]:
    """抓取该医生的主地址和附加地址。"""
    return addresses_from_text(cpso_number, fetch_page_text(cpso_number))


def _insert_address_row(conn, cpso_number: str, addr: dict) -> None:
    with conn.cursor() as cur:
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


def replace_addresses(conn, cpso_number: str, addrs: list[dict]) -> int:
    """删除该医生全部地址后再插入。返回插入条数。"""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM doctor_addresses WHERE cpso_number = %s",
            (cpso_number,),
        )
    inserted = 0
    for addr in addrs:
        _insert_address_row(conn, cpso_number, addr)
        inserted += 1
    return inserted


def update_doctor_profile(conn, cpso_number: str, profile: dict[str, str | None]) -> None:
    """写入详情页上的四项资料。传入 None 时保留原值。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE doctors
            SET gender = COALESCE(%s, gender),
                medical_school = COALESCE(%s, medical_school),
                languages_spoken = COALESCE(%s, languages_spoken),
                graduate_data = COALESCE(%s, graduate_data),
                updated_at = NOW()
            WHERE cpso_number = %s
            """,
            (
                profile.get("gender"),
                profile.get("medical_school"),
                profile.get("languages_spoken"),
                profile.get("graduate_data"),
                cpso_number,
            ),
        )


def load_doctors_to_fetch(conn, limit: int = 0) -> list[tuple[str, bool]]:
    """尚无地址，或 gender 仍为空的医生。返回 (cpso_number, 是否已有地址)。"""
    with conn.cursor() as cur:
        sql = """
            SELECT d.cpso_number,
                   EXISTS (
                       SELECT 1 FROM doctor_addresses a WHERE a.cpso_number = d.cpso_number
                   ) AS has_addresses
            FROM doctors d
            WHERE NOT EXISTS (
                    SELECT 1 FROM doctor_addresses a WHERE a.cpso_number = d.cpso_number
                  )
               OR d.gender IS NULL
               OR TRIM(COALESCE(d.gender, '')) = ''
            ORDER BY d.cpso_number
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
        cur.execute(sql)
        return [(row[0], bool(row[1])) for row in cur.fetchall()]


def main():
    parser = argparse.ArgumentParser(
        description="Fetch addresses and profile fields from the physician page"
    )
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 个医生（0=全部）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不写入数据库")
    args = parser.parse_args()

    conn = psycopg2.connect(DATABASE_URL)
    try:
        doctor_list = load_doctors_to_fetch(conn, args.limit)
    except Exception as e:
        print(f"查询数据库失败: {e}")
        conn.close()
        return

    if not doctor_list:
        print("没有待处理的医生（地址和 gender 都已有的会跳过）")
        conn.close()
        return

    print(f"待处理: {len(doctor_list)} 个医生")
    if args.dry_run:
        print("（dry-run 模式，不写入数据库）")

    total_inserted = 0
    try:
        for i, (cpso, has_addresses) in enumerate(doctor_list, 1):
            try:
                text = fetch_page_text(cpso)
                profile = profile_from_text(text)
                if has_addresses:
                    inserted = 0
                    primary_count = 0
                    address_note = "地址已有，未改"
                else:
                    addrs = addresses_from_text(cpso, text)
                    primary_count = sum(1 for addr in addrs if addr.get("is_primary"))
                    inserted = len(addrs)
                    address_note = f"主地址 {primary_count}, 共 {inserted} 条"
                if not args.dry_run:
                    if not has_addresses:
                        inserted = replace_addresses(conn, cpso, addrs)
                    update_doctor_profile(conn, cpso, profile)
                    conn.commit()
                total_inserted += inserted
                print(
                    f"  [{i}/{len(doctor_list)}] {cpso}: {address_note}; "
                    f"gender={profile.get('gender')!r}, "
                    f"medical_school={profile.get('medical_school')!r}, "
                    f"languages={profile.get('languages_spoken')!r}, "
                    f"graduate_data={profile.get('graduate_data')!r}"
                )
            except Exception as e:
                print(f"  [{i}/{len(doctor_list)}] {cpso}: 错误 - {e}")
                if conn and not args.dry_run:
                    conn.rollback()
            time.sleep(0.5)

        print(f"\n完成: 共写入 {total_inserted} 条地址")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
