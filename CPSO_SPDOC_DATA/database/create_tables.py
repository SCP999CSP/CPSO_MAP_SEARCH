"""
用 SQLModel 创建表（不删除已有数据）。

需先有空库 cpso_spdoc。现有 Postgres 容器：

    docker start cpso_postgres
    docker exec cpso_postgres psql -U postgres -c "CREATE DATABASE cpso_spdoc"

运行：python -m database.create_tables
"""
import os

from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine

from database.models import Doctor, DoctorAddress  # noqa: F401 - 确保模型被加载

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cpso_spdoc",
)


def main():
    engine = create_engine(DATABASE_URL)
    SQLModel.metadata.create_all(engine)
    print("Tables ready: doctors, doctor_addresses")


if __name__ == "__main__":
    main()
