#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f ".env" ]; then
  echo "Arquivo .env não encontrado. Copie .env.example e preencha as variáveis antes do deploy."
  exit 1
fi

echo "🔄 Pull do repositório..."
git pull origin main

echo "🐳 Build da imagem web..."
docker compose -f docker-compose.prod.yml build web

echo "🚀 Subindo containers..."
docker compose -f docker-compose.prod.yml up -d

echo "📦 Rodando migrations Alembic..."
docker compose -f docker-compose.prod.yml exec -T web alembic -c /app/alembic.ini upgrade head || true

echo "✨ Deploy completo!"
