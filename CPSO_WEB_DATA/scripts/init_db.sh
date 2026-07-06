#!/bin/bash
# 用 SQLModel 重建表（删除旧表并创建新表）
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
python -m database.create_tables
echo "Done. Tables created."
