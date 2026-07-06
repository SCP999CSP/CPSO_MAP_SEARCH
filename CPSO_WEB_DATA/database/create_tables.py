"""
用 SQLModel 删除旧表并创建新表（开发用；会清空数据）。

日常 schema 变更请用 Alembic：uv run alembic upgrade head

运行：python -m database.create_tables
"""
import os

from sqlalchemy import text
from sqlmodel import SQLModel, create_engine

from database.models import Doctor, DoctorAddress  # noqa: F401 - 确保模型被加载

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cpso_map",
)


def main():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS doctor_address CASCADE"))  # 旧表名（typo）
        conn.execute(text("DROP TABLE IF EXISTS doctor_addresses CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS doctors CASCADE"))
        conn.commit()

    SQLModel.metadata.create_all(engine)
    print("Tables recreated: doctors, doctor_addresses")


if __name__ == "__main__":
    main()
