import os

from dotenv import load_dotenv
from sqlmodel import create_engine

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cpso_spdoc",
)

# Neon 会关闭空闲连接，取用前先探活
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
