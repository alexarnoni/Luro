#!/usr/bin/env python3
"""Script de verificação para ambientes de deploy do Luro."""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import subprocess
import sys
from typing import List

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.engine.url import make_url


REQUIRED_ENV_VARS = [
    "ENV",
    "SECRET_KEY",
    "DATABASE_URL",
    "RESEND_API_KEY",
]

PROVIDER_REQUIRED_KEYS = {
    "gemini": ["GEMINI_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
}

BASE_URL = os.getenv("CHECK_DEPLOY_BASE_URL", "http://127.0.0.1:8000")


def check_env_variables() -> List[str]:
    """Verifica se as variáveis de ambiente obrigatórias estão definidas."""

    issues: List[str] = []

    for key in REQUIRED_ENV_VARS:
        if not os.getenv(key):
            issues.append(f"Variável de ambiente ausente: {key}")

    provider_raw = os.getenv("LLM_PROVIDER", "")
    if not provider_raw:
        issues.append("LLM_PROVIDER não definido ou vazio")
        return issues

    provider = provider_raw.strip().lower()
    expected_keys = PROVIDER_REQUIRED_KEYS.get(provider, [])
    for key in expected_keys:
        if not os.getenv(key):
            issues.append(f"Variável de ambiente ausente para o provedor '{provider}': {key}")
    if provider not in PROVIDER_REQUIRED_KEYS:
        issues.append(f"LLM_PROVIDER desconhecido: {provider}")

    return issues


async def check_database_connection(database_url: str) -> List[str]:
    """Testa conexão com o banco executando um SELECT 1."""

    issues: List[str] = []

    try:
        parsed_url = make_url(database_url)
    except Exception as exc:  # pragma: no cover - validação simples de string
        issues.append(f"DATABASE_URL inválida: {exc}")
        return issues

    driver = parsed_url.drivername or ""

    if "async" in driver:
        engine: AsyncEngine | None = None
        try:
            engine = create_async_engine(database_url, future=True)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:  # pragma: no cover - execução em runtime
            issues.append(f"Falha ao conectar ao banco de dados (async): {exc}")
        except Exception as exc:  # pragma: no cover - execução em runtime
            issues.append(f"Erro inesperado ao testar banco de dados (async): {exc}")
        finally:
            if engine is not None:
                await engine.dispose()
        return issues

    loop = asyncio.get_running_loop()

    def sync_check() -> None:
        engine = create_engine(database_url, future=True)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        finally:
            engine.dispose()

    try:
        await loop.run_in_executor(None, sync_check)
    except SQLAlchemyError as exc:  # pragma: no cover - execução em runtime
        issues.append(f"Falha ao conectar ao banco de dados (sync): {exc}")
    except Exception as exc:  # pragma: no cover - execução em runtime
        issues.append(f"Erro inesperado ao testar banco de dados (sync): {exc}")

    return issues


def check_alembic_status() -> List[str]:
    """Executa `alembic current` e confirma se está em head."""

    issues: List[str] = []
    try:
        result = subprocess.run(
            ["alembic", "current"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        issues.append("Comando 'alembic' não encontrado no PATH")
        return issues

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        issues.append(f"Falha ao executar 'alembic current': {output}")
        return issues

    stdout = result.stdout.strip()
    if "(head)" not in stdout:
        issues.append("Migrações não estão em head: " + (stdout or "sem saída"))

    return issues


async def check_api_endpoints(month: str) -> List[str]:
    """Testa os endpoints principais do deploy local."""

    issues: List[str] = []
    resumo_url = f"{BASE_URL}/api/resumo"
    insights_url = f"{BASE_URL}/api/insights/generate"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(resumo_url, params={"month": month})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            issues.append(f"GET /api/resumo falhou: {exc}")

        try:
            response = await client.post(insights_url, params={"month": month})
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            issues.append(
                f"POST /api/insights/generate retornou status inesperado: {exc.response.status_code}"
            )
        except httpx.HTTPError as exc:
            issues.append(f"POST /api/insights/generate falhou: {exc}")

    return issues


async def main() -> int:
    issues: List[str] = []

    issues.extend(check_env_variables())

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        issues.extend(await check_database_connection(database_url))
    else:
        issues.append("DATABASE_URL não definido")

    issues.extend(check_alembic_status())

    month = dt.date.today().strftime("%Y-%m")
    issues.extend(await check_api_endpoints(month))

    if issues:
        print("PENDÊNCIAS DETECTADAS:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:  # pragma: no cover - interação humana
        print("Interrompido pelo usuário", file=sys.stderr)
        exit_code = 130
    sys.exit(exit_code)
