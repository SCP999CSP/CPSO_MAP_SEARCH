"""
CPSO 专科医生搜索：按手写邮编，每个邮编循环固定专科，只写入 doctors 表。

doctorType 固定为 Specialist。specialties 只保留
Hematology、Neurology、Rheumatology、Dermatology、Gastroenterology。
搜到医生但提不出这些词时，记入 specialty_extract_failures.yaml，不改已有 specialties。
totalcount 为 -1（结果超过 100 条）时，把邮编记入 postal_too_broad.yaml，报错并停止后续搜索。

运行：python search_doctors.py
"""
import os
from pathlib import Path

import psycopg2
import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cpso_spdoc",
)

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
FAILURE_PATH = Path(__file__).parent / "specialty_extract_failures.yaml"
TOO_BROAD_PATH = Path(__file__).parent / "postal_too_broad.yaml"

TARGET_SPECIALTIES = (
    "Hematology",
    "Neurology",
    "Rheumatology",
    "Dermatology",
    "Gastroenterology",
)
DOCTOR_TYPE = "Specialist"


def load_search_config() -> dict:
    """从 search_config.yaml 加载邮编与专科列表。"""
    if not CONFIG_PATH.exists():
        return {
            "postal_codes": [],
            "specialist_types": list(TARGET_SPECIALTIES),
            "languages": "ENGLISH",
            "include_inactive": True,
        }
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if not cfg.get("specialist_types"):
        cfg["specialist_types"] = list(TARGET_SPECIALTIES)
    cfg.setdefault("languages", "ENGLISH")
    cfg.setdefault("include_inactive", True)
    cfg.setdefault("postal_codes", [])
    return cfg


def canonical_specialties(*raws: str | None) -> str | None:
    """按 | 切开，只保留 5 个目标专科，并按固定顺序用 ' | ' 连接。"""
    found: set[str] = set()
    for raw in raws:
        if not raw:
            continue
        for part in str(raw).split("|"):
            name = part.strip()
            if name in TARGET_SPECIALTIES:
                found.add(name)
    ordered = [name for name in TARGET_SPECIALTIES if name in found]
    return " | ".join(ordered) if ordered else None


def build_payload(postal_code: str, specialist_type: str, cfg: dict) -> dict:
    """构建与 Advanced Search 一致的专科搜索请求。"""
    return {
        "cbx-includeinactive": "on" if cfg.get("include_inactive", True) else "off",
        "postalCode": postal_code.strip(),
        "doctorType": DOCTOR_TYPE,
        "SpecialistType": specialist_type,
        "LanguagesSelected": cfg.get("languages", "ENGLISH"),
    }


def _str(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _get_cpso_number(doc: dict) -> str | None:
    return _str(doc.get("cpsonumber") or doc.get("cpso_number") or doc.get("cpsono"))


def _get_full_name(doc: dict) -> str:
    name = doc.get("name") or doc.get("fullname") or doc.get("full_name") or ""
    return str(name).strip() or "Unknown"


def _get_additional_address_count(doc: dict) -> int:
    add_count = doc.get("additionaladdresscount") or doc.get("additional_address_count")
    if add_count is None:
        return 0
    return int(add_count)


def fetch_search_results(payload: dict) -> tuple[int, list[dict]]:
    """调用 CPSO 搜索 API，返回 (totalcount, results)。"""
    resp = SESSION.post(
        f"{BASE_URL}/Get-Search-Results/",
        headers=HEADERS,
        data=payload,
        timeout=30,
    )
    resp.raise_for_status()
    out = resp.json()
    total = out.get("totalcount", 0)
    results = out.get("results") or []
    return total, results


def _existing_specialties(conn, cpso_number: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT specialties FROM doctors WHERE cpso_number = %s",
            (cpso_number,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return row[0]


def upsert_doctor(
    conn,
    cpso_number: str,
    full_name: str,
    doc: dict,
    specialties: str | None,
) -> None:
    """插入或按 cpso_number 更新医生。specialties 为 None 时保留原值。"""
    status = doc.get("registrationstatus") or doc.get("registration_status")
    status_label = doc.get("registrationstatuslabel") or doc.get("registration_status_label")
    add_count = _get_additional_address_count(doc)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO doctors (
                cpso_number, full_name,
                registration_status, registration_status_label,
                specialties, additional_address_count,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (cpso_number) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                registration_status = EXCLUDED.registration_status,
                registration_status_label = EXCLUDED.registration_status_label,
                additional_address_count = EXCLUDED.additional_address_count,
                specialties = COALESCE(EXCLUDED.specialties, doctors.specialties),
                updated_at = NOW()
            """,
            (
                cpso_number,
                full_name,
                _str(status),
                _str(status_label),
                specialties,
                add_count,
            ),
        )


def _failure_key(record: dict) -> tuple:
    return (
        record.get("cpso_number"),
        record.get("raw_specialties"),
        record.get("postal_code"),
        record.get("specialist_type"),
    )


def load_failures() -> list[dict]:
    if not FAILURE_PATH.exists():
        return []
    with open(FAILURE_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    failures = data.get("failures") or []
    return failures if isinstance(failures, list) else []


def save_failures(failures: list[dict]) -> None:
    with open(FAILURE_PATH, "w", encoding="utf-8") as f:
        yaml.dump(
            {"failures": failures},
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )


def record_too_broad(postal_code: str, specialist_type: str) -> None:
    """把结果过多的邮编追加写入 postal_too_broad.yaml。"""
    rows: list[dict] = []
    if TOO_BROAD_PATH.exists():
        with open(TOO_BROAD_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        loaded = data.get("too_broad") or []
        if isinstance(loaded, list):
            rows = loaded
    record = {"postal_code": postal_code, "specialist_type": specialist_type}
    if record not in rows:
        rows.append(record)
    with open(TOO_BROAD_PATH, "w", encoding="utf-8") as f:
        yaml.dump(
            {"too_broad": rows},
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )


def search_and_save(payload: dict, specialist_type: str) -> tuple[int, int, int, list[dict]]:
    """
    搜索并只 upsert 医生。
    返回 (总匹配数, upsert 医生数, 提取失败数, 新的失败记录)。
    """
    total, results = fetch_search_results(payload)
    if total == -1:
        return total, 0, 0, []

    doctors_synced = 0
    extract_failed = 0
    failures: list[dict] = []
    postal_code = payload.get("postalCode", "")

    conn = psycopg2.connect(DATABASE_URL)
    try:
        for doc in results:
            cpso = _get_cpso_number(doc)
            if not cpso:
                continue

            raw_specialties = doc.get("specialties")
            extracted = canonical_specialties(
                raw_specialties if isinstance(raw_specialties, str) else _str(raw_specialties)
            )
            if extracted is None:
                specialties_value = None
                extract_failed += 1
                failures.append({
                    "cpso_number": cpso,
                    "full_name": _get_full_name(doc),
                    "raw_specialties": _str(raw_specialties),
                    "postal_code": postal_code,
                    "specialist_type": specialist_type,
                })
            else:
                existing = _existing_specialties(conn, cpso)
                specialties_value = canonical_specialties(existing, extracted)

            upsert_doctor(conn, cpso, _get_full_name(doc), doc, specialties_value)
            doctors_synced += 1

        conn.commit()
    finally:
        conn.close()

    return total, doctors_synced, extract_failed, failures


def main():
    cfg = load_search_config()
    postal_codes = [str(pc).strip() for pc in cfg.get("postal_codes") or [] if str(pc).strip()]
    specialist_types = [
        str(name).strip() for name in cfg.get("specialist_types") or [] if str(name).strip()
    ]
    if not postal_codes:
        print("search_config.yaml 里没有 postal_codes，未发起搜索。")
        return
    if not specialist_types:
        print("search_config.yaml 里没有 specialist_types，未发起搜索。")
        return

    print(
        f"Fetching CPSO specialist results for {len(postal_codes)} postal code(s) "
        f"x {len(specialist_types)} specialist type(s)..."
    )
    SESSION.get(f"{BASE_URL}/", headers=HEADERS, timeout=30)

    total_matches = 0
    total_doctors = 0
    total_failed = 0
    all_failures: list[dict] = load_failures()
    seen_failures = {_failure_key(row) for row in all_failures}
    failed_requests = 0

    for i, pc in enumerate(postal_codes, 1):
        for specialist_type in specialist_types:
            payload = build_payload(pc, specialist_type, cfg)
            print(f"  [{i}/{len(postal_codes)}] postalCode={pc!r} SpecialistType={specialist_type!r} ...")
            try:
                total, doctors_synced, extract_failed, failures = search_and_save(
                    payload, specialist_type
                )
            except requests.exceptions.RequestException as e:
                failed_requests += 1
                print(f"    -> 请求失败，已跳过: {e}")
                continue
            except Exception as e:
                failed_requests += 1
                print(f"    -> 处理失败，已跳过: {e}")
                continue

            if total == -1:
                record_too_broad(pc, specialist_type)
                if total_failed:
                    save_failures(all_failures)
                print(
                    f"错误: postalCode={pc!r} SpecialistType={specialist_type!r} "
                    f"结果超过 100 条 (totalcount=-1)，已写入 {TOO_BROAD_PATH}，停止搜索。"
                )
                print(f"停止前已写入匹配 {total_matches}，upsert {total_doctors} 行。")
                raise SystemExit(1)

            if total > 0:
                total_matches += total
            total_doctors += doctors_synced
            total_failed += extract_failed
            for row in failures:
                key = _failure_key(row)
                if key not in seen_failures:
                    all_failures.append(row)
                    seen_failures.add(key)
            parts = [
                f"matches: {total}",
                f"upserted: {doctors_synced} doctors",
            ]
            if extract_failed:
                parts.append(f"专科提取失败: {extract_failed}")
            print(f"    -> {', '.join(parts)}")

    if total_failed:
        save_failures(all_failures)
        print(f"\n专科关键词提取失败已写入 {FAILURE_PATH}（本文件共 {len(all_failures)} 条）")

    print(f"\nTotal matches: {total_matches}")
    print(f"Upserted doctor rows this run: {total_doctors}")
    print(f"Specialty extract failures this run: {total_failed}")
    if failed_requests:
        print(f"Skipped due to errors: {failed_requests} request(s).")


if __name__ == "__main__":
    main()
