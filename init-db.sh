#!/bin/bash
set -e

echo "🔄 Ожидание готовности PostgreSQL и Redis..."

python3 << 'PYTHON_SCRIPT'
import asyncio
import asyncpg
import redis.asyncio as aioredis
import os
import sys

async def wait_for_services():
    max_retries = 30
    retry_delay = 2

    # Проверка PostgreSQL
    for i in range(max_retries):
        try:
            conn = await asyncpg.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=int(os.getenv('DB_PORT', 5432)),
                user=os.getenv('DB_USER', 'teammates_user'),
                password=os.getenv('DB_PASSWORD'),
                database=os.getenv('DB_NAME', 'teammates')
            )
            await conn.close()
            print("✅ PostgreSQL готов!")
            break
        except Exception as e:
            print(f"⏳ PostgreSQL недоступен (попытка {i+1}/{max_retries}) - ждем...")
            await asyncio.sleep(retry_delay)
    else:
        print("❌ PostgreSQL недоступен после всех попыток")
        sys.exit(1)

    # Проверка Redis
    for i in range(max_retries):
        try:
            redis_password = os.getenv('REDIS_PASSWORD', '')
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = os.getenv('REDIS_PORT', 6379)
            if redis_password:
                redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}"
            else:
                redis_url = f"redis://{redis_host}:{redis_port}"
            redis = aioredis.from_url(redis_url)
            await redis.ping()
            await redis.close()
            print("✅ Redis готов!")
            break
        except Exception as e:
            print(f"⏳ Redis недоступен (попытка {i+1}/{max_retries}) - ждем...")
            await asyncio.sleep(retry_delay)
    else:
        print("❌ Redis недоступен после всех попыток")
        sys.exit(1)

asyncio.run(wait_for_services())
PYTHON_SCRIPT

echo "🚀 Запуск TeammateBot..."
exec python main.py
