"""
从 CPSO physician-info 页面抓取 General Information，补全 doctors 表：
gender, medical_school, languages_spoken, graduate_data（医学院字符串末尾四位年份）。

仅处理 gender 为空的记录。graduate_data：medical_school 去除尾部空白后最后 4 个字符
须为十进制年份且在合理范围内，否则 ValueError，该条不写入。

运行：python addmore_docinfo.py [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import time

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

YEAR_MIN = 1950


def _first_field_value(page_text: str, label: str) -> str | None:
    m = re.search(rf"{re.escape(label)}:\s*([^\n]+)", page_text, re.IGNORECASE)
    if not m:
        return None
    val = m.group(1).strip()
    if not val or "no information available" in val.lower():
        return None
    return val


def graduate_year_from_medical_school(medical_school: str) -> str:
    s = (medical_school or "").rstrip()
    if len(s) < 4:
        raise ValueError(f"medical_school 过短，无法取后四位年份: {medical_school!r}")
    last4 = s[-4:]
    if not last4.isdigit():
        raise ValueError(f"medical_school 后四位非数字: {medical_school!r}")
    y = int(last4)
    y_max = datetime.datetime.now().year + 1
    if y < YEAR_MIN or y > y_max:
        raise ValueError(f"medical_school 后四位年份超出范围 [{YEAR_MIN}, {y_max}]: {last4}")
    return last4


def fetch_profile_fields(cpso_number: str) -> dict[str, str | None]:
    url = f"{BASE_URL}/physician-info/?cpsonum={cpso_number}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text("\n", strip=True)

    gender = _first_field_value(text, "Gender")
    medical_school = _first_field_value(text, "Medical School")
    languages = _first_field_value(text, "Languages Spoken")

    graduate_data: str | None = None
    if medical_school:
        graduate_data = graduate_year_from_medical_school(medical_school)

    return {
        "gender": gender,
        "medical_school": medical_school,
        "languages_spoken": languages,
        "graduate_data": graduate_data,
    }


def load_doctors_missing_gender(conn, limit: int = 0) -> list[str]:
    with conn.cursor() as cur:
        sql = """
            SELECT cpso_number
            FROM doctors
            WHERE gender IS NULL OR TRIM(COALESCE(gender, '')) = ''
            ORDER BY cpso_number
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
        cur.execute(sql)
        return [row[0] for row in cur.fetchall()]


def update_doctor_profile(
    conn,
    cpso_number: str,
    gender: str | None,
    medical_school: str | None,
    languages_spoken: str | None,
    graduate_data: str | None,
) -> None:
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
            (gender, medical_school, languages_spoken, graduate_data, cpso_number),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch gender / medical school / languages / grad year from CPSO pages"
    )
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 个医生（0=全部）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不写入数据库")
    args = parser.parse_args()

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cpso_list = load_doctors_missing_gender(conn, args.limit)
    except Exception as e:
        print(f"查询数据库失败: {e}")
        conn.close()
        return

    if not cpso_list:
        print("没有 gender 为空的医生记录")
        conn.close()
        return

    print(f"待处理: {len(cpso_list)} 个医生（gender 为空）")
    if args.dry_run:
        print("（dry-run 模式，不写入数据库）")

    ok = 0
    try:
        for i, cpso in enumerate(cpso_list, 1):
            try:
                fields = fetch_profile_fields(cpso)
                if not any(
                    [
                        fields.get("gender"),
                        fields.get("medical_school"),
                        fields.get("languages_spoken"),
                        fields.get("graduate_data"),
                    ]
                ):
                    print(f"  [{i}/{len(cpso_list)}] {cpso}: 跳过 — 未解析到任何目标字段")
                    continue

                print(
                    f"  [{i}/{len(cpso_list)}] {cpso}: "
                    f"gender={fields.get('gender')!r}, "
                    f"medical_school={fields.get('medical_school')!r}, "
                    f"languages={fields.get('languages_spoken')!r}, "
                    f"graduate_data={fields.get('graduate_data')!r}"
                )
                if not args.dry_run:
                    update_doctor_profile(
                        conn,
                        cpso,
                        fields.get("gender"),
                        fields.get("medical_school"),
                        fields.get("languages_spoken"),
                        fields.get("graduate_data"),
                    )
                    conn.commit()
                ok += 1
            except ValueError as e:
                print(f"  [{i}/{len(cpso_list)}] {cpso}: 校验错误 — {e}")
                if conn and not args.dry_run:
                    conn.rollback()
            except Exception as e:
                print(f"  [{i}/{len(cpso_list)}] {cpso}: 错误 — {e}")
                if conn and not args.dry_run:
                    conn.rollback()
            time.sleep(0.5)

        print(f"\n完成: 成功处理 {ok} 条")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
