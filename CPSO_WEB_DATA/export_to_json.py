"""
导出 doctor_addresses（含 doctors 姓名）为 JSON，供前端地图使用。
仅导出 latitude/longitude 非空的记录。

运行：python export_to_json.py [--limit N] [--output path]
"""
import argparse
import json
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cpso_map",
)


def main():
    parser = argparse.ArgumentParser(description="Export doctor addresses with lat/lng to JSON")
    parser.add_argument("--limit", type=int, default=None, help="Max records to export (default: all)")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output path (default: ../frontend/public/doctors-addresses.json)",
    )
    args = parser.parse_args()

    output_path = args.output
    if not output_path:
        script_dir = Path(__file__).resolve().parent
        output_path = script_dir.parent / "frontend" / "public" / "doctors-addresses.json"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    conn = psycopg2.connect(DATABASE_URL)

    sql = """
        SELECT
            a.id::text,
            a.cpso_number,
            d.full_name,
            a.latitude,
            a.longitude,
            a.phone,
            a.fax,
            a.full_address,
            a.city,
            a.province,
            a.postal_code
        FROM doctor_addresses a
        JOIN doctors d ON d.cpso_number = a.cpso_number
        WHERE a.latitude IS NOT NULL AND a.longitude IS NOT NULL
        ORDER BY a.cpso_number, a.is_primary DESC
    """
    if args.limit:
        sql += " LIMIT %s"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (args.limit,) if args.limit else None)
        rows = cur.fetchall()

    conn.close()

    # Convert to list of dicts with proper JSON serialization (UUID -> str already via ::text)
    records = []
    for r in rows:
        records.append(
            {
                "id": str(r["id"]),
                "cpso_number": r["cpso_number"],
                "full_name": r["full_name"],
                "latitude": float(r["latitude"]),
                "longitude": float(r["longitude"]),
                "phone": r["phone"],
                "fax": r["fax"],
                "full_address": r["full_address"],
                "city": r["city"],
                "province": r["province"],
                "postal_code": r["postal_code"],
            }
        )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Exported {len(records)} records to {output_path}")


if __name__ == "__main__":
    main()
