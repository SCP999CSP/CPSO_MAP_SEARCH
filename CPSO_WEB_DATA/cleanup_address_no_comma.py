"""
临时脚本：清理「数据库附加地址数 > 应有数」的医生中，full_address 不含逗号的附加地址记录。
删除后验证应有数是否与数据库匹配。

运行：python cleanup_address_no_comma.py [--dry-run]
"""
import argparse
import os

import psycopg2

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cpso_map",
)


def load_doctors_with_overflow(conn) -> list[tuple[str, int, int]]:
    """
    查询「数据库附加地址数 > 应有数」的医生。
    返回 [(cpso_number, expected, db_count), ...]
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT d.cpso_number, d.additional_address_count,
                   COALESCE(da.cnt, 0)::int AS db_count
            FROM doctors d
            LEFT JOIN (
                SELECT cpso_number, COUNT(*) AS cnt
                FROM doctor_addresses
                WHERE is_primary = FALSE
                GROUP BY cpso_number
            ) da ON d.cpso_number = da.cpso_number
            WHERE d.additional_address_count > 0
              AND COALESCE(da.cnt, 0) > d.additional_address_count
            ORDER BY d.cpso_number
        """)
        return [(row[0], row[1], row[2]) for row in cur.fetchall()]


def get_addresses_to_delete(conn, cpso_number: str) -> list[tuple[str, str | None]]:
    """
    查询该医生名下「full_address 不含逗号」的附加地址。
    返回 [(id, full_address), ...]
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, full_address
            FROM doctor_addresses
            WHERE cpso_number = %s
              AND is_primary = FALSE
              AND (full_address IS NULL OR TRIM(COALESCE(full_address, '')) = '' OR full_address NOT LIKE %s)
            """,
            (cpso_number, "%,%"),
        )
        rows = cur.fetchall()
        return [(str(row[0]), row[1]) for row in rows]


def delete_addresses(conn, ids: list[str]) -> int:
    """删除指定 id 的地址记录。返回删除条数。"""
    if not ids:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM doctor_addresses WHERE id::text = ANY(%s)",
            (ids,),
        )
        return cur.rowcount


def get_additional_count(conn, cpso_number: str) -> int:
    """查询该医生的附加地址数量。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM doctor_addresses WHERE cpso_number = %s AND is_primary = FALSE",
            (cpso_number,),
        )
        return cur.fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description="清理无逗号格式的附加地址")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将要删除的记录，不执行")
    args = parser.parse_args()

    conn = psycopg2.connect(DATABASE_URL)
    try:
        overflow_list = load_doctors_with_overflow(conn)
        if not overflow_list:
            print("未找到「数据库附加地址数 > 应有数」的医生")
            return

        print(f"找到 {len(overflow_list)} 个医生（数据库附加地址数 > 应有数）")
        if args.dry_run:
            print("（dry-run 模式，不执行删除）")

        total_deleted = 0
        affected_cpsos: list[str] = []

        for cpso, expected, db_count in overflow_list:
            to_del = get_addresses_to_delete(conn, cpso)
            if not to_del:
                print(f"  {cpso}: 应有 {expected}, 数据库 {db_count}，无可删除记录（无逗号）")
                continue

            ids = [r[0] for r in to_del]
            affected_cpsos.append(cpso)
            print(f"  {cpso}: 应有 {expected}, 数据库 {db_count}，将删除 {len(ids)} 条无逗号地址")

            for addr_id, full in to_del:
                preview = (full or "(NULL)")[:60]
                if len(preview) >= 60:
                    preview += "..."
                print(f"    - {addr_id}: {preview}")

            if not args.dry_run:
                n = delete_addresses(conn, ids)
                total_deleted += n
                conn.commit()

        if args.dry_run:
            print(f"\n（dry-run）将删除的记录来自 {len(affected_cpsos)} 个医生")
            return

        print(f"\n已删除 {total_deleted} 条记录")

        # 验证
        print("\n--- 验证 ---")
        matched = 0
        mismatched = []
        for cpso in affected_cpsos:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT additional_address_count FROM doctors WHERE cpso_number = %s",
                    (cpso,),
                )
                row = cur.fetchone()
            if not row:
                continue
            expected = row[0]
            actual = get_additional_count(conn, cpso)
            if expected == actual:
                matched += 1
                print(f"  {cpso}: 匹配（应有 {expected}，已有 {actual}）")
            else:
                mismatched.append((cpso, expected, actual))
                print(f"  {cpso}: 仍不匹配（应有 {expected}，已有 {actual}）")

        print(f"\n汇总: 匹配 {matched}，仍不匹配 {len(mismatched)}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
