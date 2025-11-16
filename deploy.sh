#!/usr/bin/env bash
set -e

cd /opt/luro

echo "🔄 Pull do repositório..."
git pull origin main

echo "🐳 Build da imagem web..."
docker compose -f docker-compose.prod.yml build web

echo "🚀 Subindo containers..."
docker compose -f docker-compose.prod.yml up -d

echo "📦 Rodando migrations Alembic..."
docker exec -i luro-web-1 alembic -c /app/alembic.ini upgrade head || true

echo "✨ Deploy completo!"
