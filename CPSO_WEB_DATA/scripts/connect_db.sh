#!/bin/bash
# 快速连接 cpso_map 数据库
docker exec -it cpso_postgres psql -U postgres -d cpso_map
