#!/bin/bash
set -e

echo "🔄 Ожидание готовности PostgreSQL..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; do
  echo "⏳ PostgreSQL недоступен - ждем..."
  sleep 2
done
echo "✅ PostgreSQL готов!"

echo "🔄 Ожидание готовности Redis..."
until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; do
  echo "⏳ Redis недоступен - ждем..."
  sleep 2
done
echo "✅ Redis готов!"

echo "🚀 Запуск TeammateBot..."
exec python main.py
