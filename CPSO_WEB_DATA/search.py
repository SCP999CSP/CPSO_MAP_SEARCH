"""
CPSO 医生搜索：从 API 获取结果并写入 doctors、doctor_addresses 表。
postalCode 从 search_config.yaml 读取，支持多组邮编依次搜索。
"""
import os
import re
import uuid
from pathlib import Path

import psycopg2
import requests
import yaml

from fetch_additional_addresses import clear_additional_addresses, sync_additional_addresses

# 数据库连接（优先使用环境变量）
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cpso_map",
)

# CPSO API（与浏览器请求保持一致）
BASE_URL = "https://register.cpso.on.ca"
SESSION = requests.Session()
HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/Search-Results/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

CONFIG_PATH = Path(__file__).parent / "search_config.yaml"
MISMATCH_PATH = Path(__file__).parent / "search_postal_mismatch.yaml"
DEFAULT_POSTAL_CODES = ["M5A 4"]


def _postal_first4(pc: str | None) -> str:
    """取邮编前四位（去空格、大写）。"""
    if not pc:
        return ""
    s = re.sub(r"\s+", "", str(pc).strip().upper())
    return s[:4]


def load_search_config() -> dict:
    """从 search_config.yaml 加载配置。"""
    if not CONFIG_PATH.exists():
        return {"postal_codes": DEFAULT_POSTAL_CODES}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not cfg or not cfg.get("postal_codes"):
        return {"postal_codes": DEFAULT_POSTAL_CODES}
    return cfg


def build_payload(postal_code: str, cfg: dict) -> dict:
    """根据配置构建单次请求的 payload。"""
    return {
        "cbx-includeinactive": "on" if cfg.get("include_inactive", True) else "off",
        "postalCode": postal_code.strip(),
        "doctorType": cfg.get("doctor_type", "Family Doctor"),
        "LanguagesSelected": cfg.get("languages", "ENGLISH"),
    }


def _get_cpso_number(doc: dict) -> str | None:
    """从医生数据中提取 CPSO 号。"""
    return doc.get("cpsonumber") or doc.get("cpso_number") or doc.get("cpsono")


def _get_full_name(doc: dict) -> str:
    """从医生数据中提取姓名。"""
    name = doc.get("name") or doc.get("fullname") or doc.get("full_name") or ""
    return str(name).strip() or "Unknown"


def _is_family_medicine_only(doc: dict) -> bool:
    """仅录入 specialties 为空或仅为 Family Medicine 的医生。"""
    spec = (doc.get("specialties") or "").strip()
    if not spec:
        return True
    parts = [p.strip() for p in spec.split("|") if p.strip()]
    return len(parts) == 1 and parts[0].lower() == "family medicine"


def _parse_addresses(doc: dict) -> list[dict]:
    """
    从医生数据中解析地址列表。
    API 可能返回扁平字段或嵌套的 addresses 数组。
    """
    addresses = []

    # 嵌套 addresses
    raw_addrs = doc.get("addresses") or doc.get("addressList") or []
    if isinstance(raw_addrs, list):
        for addr in raw_addrs:
            if isinstance(addr, dict):
                addresses.append(_normalize_address(addr, doc))
            elif isinstance(addr, str):
                addresses.append({
                    "full_address": addr,
                    "postal_code": _extract_postal_code(addr),
                    "is_primary": len(addresses) == 0,
                })
    elif isinstance(raw_addrs, dict):
        addresses.append(_normalize_address(raw_addrs, doc))

    # 扁平字段：至少有一条地址信息时单独成一条
    if not addresses:
        addr = _build_flat_address(doc)
        if addr.get("full_address") or addr.get("postal_code"):
            addresses.append(addr)

    if not addresses:
        # 仅 postal code 也当作一条地址
        pc = doc.get("postalcode") or doc.get("postal_code")
        if pc:
            addresses.append({
                "postal_code": str(pc).strip(),
                "full_address": str(pc).strip(),
                "is_primary": True,
            })

    if not addresses:
        addresses.append({"is_primary": True})

    return addresses


def _normalize_address(addr: dict, doc: dict) -> dict:
    """标准化单条地址字典。"""
    street1 = addr.get("street1") or addr.get("street") or addr.get("line1")
    street2 = addr.get("street2") or addr.get("line2")
    street3 = addr.get("street3") or addr.get("line3")
    street4 = addr.get("street4") or addr.get("line4")
    city = addr.get("city") or addr.get("citytown") or doc.get("city")
    province = addr.get("province") or addr.get("prov") or doc.get("province") or "ON"
    postal_code = addr.get("postalcode") or addr.get("postal_code") or doc.get("postalcode")
    full = addr.get("fulladdress") or addr.get("full_address") or addr.get("address")
    phone = addr.get("phonenumber") or addr.get("phone") or doc.get("phonenumber") or doc.get("phone")
    fax = addr.get("fax") or doc.get("fax")
    is_primary = addr.get("isprimary", addr.get("is_primary", True))
    not_in_practice = addr.get("primaryaddressnotinpractice", addr.get("notinpractice", addr.get("not_in_practice", False)))

    parts = [p for p in [street1, street2, street3, street4, city, province, postal_code] if p]
    if not full and parts:
        full = ", ".join(str(p) for p in parts)

    return {
        "street1": _str(street1),
        "street2": _str(street2),
        "street3": _str(street3),
        "street4": _str(street4),
        "city": _str(city),
        "province": _str(province),
        "postal_code": _str(postal_code),
        "full_address": _str(full),
        "phone": _str(phone),
        "fax": _str(fax),
        "is_primary": bool(is_primary),
        "not_in_practice": bool(not_in_practice),
    }


def _build_flat_address(doc: dict) -> dict:
    """
    从扁平字段构建单条地址。
    CPSO API 返回格式：street1-4, city, province, postalcode, phonenumber, fax, primaryaddressnotinpractice
    """
    street1 = doc.get("street1") or doc.get("address") or doc.get("street")
    street2 = doc.get("street2")
    street3 = doc.get("street3")
    street4 = doc.get("street4")
    city = doc.get("city") or doc.get("citytown")
    province = doc.get("province") or doc.get("prov") or "ON"
    postal_code = doc.get("postalcode") or doc.get("postal_code")
    full = doc.get("fulladdress") or doc.get("full_address")
    # API 使用 phonenumber（无空格），非 phone
    phone = doc.get("phonenumber") or doc.get("phone")
    fax = doc.get("fax")
    not_in_practice = doc.get("primaryaddressnotinpractice", doc.get("notinpractice", False))

    parts = [p for p in [street1, street2, street3, street4, city, province, postal_code] if p]
    if not full and parts:
        full = ", ".join(str(p).strip() for p in parts if str(p).strip())
    elif postal_code and not full:
        full = str(postal_code).strip()

    return {
        "street1": _str(street1),
        "street2": _str(street2),
        "street3": _str(street3),
        "street4": _str(street4),
        "city": _str(city),
        "province": _str(province),
        "postal_code": _str(postal_code),
        "full_address": _str(full),
        "phone": _str(phone),
        "fax": _str(fax),
        "is_primary": True,
        "not_in_practice": bool(not_in_practice),
    }


def _str(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _extract_postal_code(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"[A-Z]\d[A-Z]\s*\d[A-Z]\d", text, re.IGNORECASE)
    return m.group(0).strip() if m else None


def fetch_search_results(payload: dict) -> tuple[int, list[dict]]:
    """
    调用 CPSO 搜索 API，返回 (totalcount, results)。
    """
    data = payload
    # 先访问首页获取会话 cookie（如 ARRAffinity）
    SESSION.get(f"{BASE_URL}/", headers=HEADERS, timeout=30)
    resp = SESSION.post(
        f"{BASE_URL}/Get-Search-Results/",
        headers=HEADERS,
        data=data,
        timeout=30,
    )
    resp.raise_for_status()
    out = resp.json()
    total = out.get("totalcount", 0)
    results = out.get("results") or []
    return total, results


def _get_additional_address_count(doc: dict) -> int:
    """从 API 结果提取附加地址数量。"""
    add_count = doc.get("additionaladdresscount") or doc.get("additional_address_count")
    if add_count is None:
        addrs = doc.get("addresses") or doc.get("addressList") or []
        return len(addrs) if isinstance(addrs, list) else 0
    return int(add_count)


def upsert_doctor(conn, cpso_number: str, full_name: str, doc: dict) -> None:
    """插入或按 cpso_number 更新 doctors 表（不覆盖 gender 等详情页字段）。"""
    status = doc.get("registrationstatus") or doc.get("registration_status")
    status_label = doc.get("registrationstatuslabel") or doc.get("registration_status_label")
    add_count = _get_additional_address_count(doc)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO doctors (
                cpso_number, full_name,
                registration_status, registration_status_label,
                additional_address_count, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (cpso_number) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                registration_status = EXCLUDED.registration_status,
                registration_status_label = EXCLUDED.registration_status_label,
                additional_address_count = EXCLUDED.additional_address_count,
                updated_at = NOW()
            """,
            (
                cpso_number,
                full_name,
                _str(status),
                _str(status_label),
                add_count,
            ),
        )


def replace_primary_address(conn, cpso_number: str, addr: dict) -> None:
    """删除该医生旧主地址并插入 API 返回的最新主地址。"""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM doctor_addresses WHERE cpso_number = %s AND is_primary = TRUE",
            (cpso_number,),
        )
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
                True,
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


def _mismatch_record(input_pc: str, doc: dict, addr: dict, result_pc: str) -> dict:
    """构建邮编不匹配记录。"""
    def _s(v):
        return str(v).strip() if v is not None and str(v).strip() else None

    return {
        "input_postal_code": input_pc,
        "result_postal_code": result_pc,
        "doctor": {
            "cpso_number": _s(_get_cpso_number(doc)),
            "full_name": _s(_get_full_name(doc)),
            "registration_status": _s(doc.get("registrationstatus") or doc.get("registration_status")),
        },
        "address": {
            "full_address": addr.get("full_address"),
            "street1": addr.get("street1"),
            "street2": addr.get("street2"),
            "city": addr.get("city"),
            "province": addr.get("province"),
            "postal_code": addr.get("postal_code"),
            "phone": addr.get("phone"),
        },
    }


def search_and_save(payload: dict) -> tuple[int, int, int, int, list[dict]]:
    """
    执行搜索并将结果写入数据库（按 cpso_number upsert 医生并同步主/附加地址）。
    返回 (总匹配数, 同步医生数, 写入地址数, 专科过滤数, 邮编前四位不匹配记录列表)。
    """
    total, results = fetch_search_results(payload)
    doctors_synced = 0
    addresses_written = 0
    doctors_filtered = 0
    input_first4 = _postal_first4(payload.get("postalCode", ""))
    mismatches: list[dict] = []

    conn = psycopg2.connect(DATABASE_URL)
    try:
        for doc in results:
            cpso = _get_cpso_number(doc)
            if not cpso:
                continue
            if not _is_family_medicine_only(doc):
                doctors_filtered += 1
                continue

            full_name = _get_full_name(doc)
            upsert_doctor(conn, cpso, full_name, doc)
            doctors_synced += 1

            addrs = _parse_addresses(doc)
            if addrs:
                primary = addrs[0]
                primary["is_primary"] = True
                replace_primary_address(conn, cpso, primary)
                addresses_written += 1

                result_pc = (
                    primary.get("postal_code")
                    or doc.get("postalcode")
                    or doc.get("postal_code")
                )
                if result_pc and _postal_first4(result_pc) != input_first4:
                    mismatches.append(_mismatch_record(
                        payload.get("postalCode", ""), doc, primary, result_pc or ""
                    ))

            add_count = _get_additional_address_count(doc)
            if add_count > 0:
                try:
                    _, inserted = sync_additional_addresses(conn, cpso)
                    addresses_written += inserted
                except Exception as e:
                    print(f"    {cpso}: 附加地址同步失败 - {e}")
            else:
                clear_additional_addresses(conn, cpso)

        conn.commit()
    finally:
        conn.close()

    return total, doctors_synced, addresses_written, doctors_filtered, mismatches


def main():
    cfg = load_search_config()
    postal_codes = cfg.get("postal_codes", DEFAULT_POSTAL_CODES)
    print(f"Fetching CPSO search results for {len(postal_codes)} postal code(s)...")

    total_matches = 0
    total_doctors = 0
    total_addresses = 0
    all_mismatches: list[dict] = []
    failed_postal_codes = 0

    for i, pc in enumerate(postal_codes, 1):
        payload = build_payload(pc, cfg)
        print(f"  [{i}/{len(postal_codes)}] postalCode={pc!r} ...")
        try:
            total, doctors_synced, addresses_written, doctors_filtered, mismatches = search_and_save(payload)
            total_matches += total
            total_doctors += doctors_synced
            total_addresses += addresses_written
            all_mismatches.extend(mismatches)
            parts = [f"matches: {total}", f"synced: {doctors_synced} doctors, {addresses_written} addresses"]
            if doctors_filtered:
                parts.append(f"filtered: {doctors_filtered}")
            if mismatches:
                parts.append(f"邮编不匹配: {len(mismatches)}")
            print(f"    -> {', '.join(parts)}")
        except requests.exceptions.RequestException as e:
            failed_postal_codes += 1
            print(f"    -> 请求失败，已跳过: {e}")
            continue
        except Exception as e:
            failed_postal_codes += 1
            print(f"    -> 处理失败，已跳过: {e}")
            continue

    if all_mismatches:
        with open(MISMATCH_PATH, "w", encoding="utf-8") as f:
            yaml.dump({"mismatches": all_mismatches}, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"\n邮编前四位不匹配记录已写入 {MISMATCH_PATH}（共 {len(all_mismatches)} 条）")

    print(f"\nTotal matches: {total_matches}")
    print(f"Synced: {total_doctors} doctors, {total_addresses} addresses.")
    if failed_postal_codes:
        print(f"Skipped due to errors: {failed_postal_codes} postal code(s).")


if __name__ == "__main__":
    main()
