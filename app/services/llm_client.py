"""HTTP-based client for Large Language Model providers."""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

from app.core.config import settings

PROMPT_SYSTEM = (
    "Você é um analista financeiro didático que gera insights claros, sem jargões, "
    "baseados apenas em agregados financeiros mensais. NUNCA cite PII/lojas; use "
    "APENAS agregados."
)


def build_user_prompt(summary_json: dict[str, Any]) -> str:
    """Build the end-user prompt enforcing the required output format."""

    serialized = json.dumps(summary_json, ensure_ascii=False, indent=2, sort_keys=True)
    instructions = (
        "Com base nos dados agregados mensais a seguir, produza insights em português "
        "seguindo exatamente o formato solicitado:\n"
        "1) Diagnóstico (até 6 frases);\n"
        "2) 3 ações práticas (bullets);\n"
        "3) 1 'Vitória rápida';\n"
        "4) 1 CTA de meta simples.\n"
        "Mantenha tom positivo, sem mencionar dados sensíveis ou estabelecimentos."  # noqa: E501
    )

    return f"{instructions}\n\nAgregados mensais:\n{serialized}"


async def generate_insight(summary_json: dict[str, Any]) -> str:
    """Generate a monthly insight using the configured LLM provider."""

    provider = (os.getenv("LLM_PROVIDER") or getattr(settings, "LLM_PROVIDER", "")).strip().lower()
    if not provider:
        provider = "gemini"

    if provider == "gemini":
        return await _generate_with_gemini(summary_json)
    if provider == "openai":
        return await _generate_with_openai(summary_json)

    raise ValueError("LLM_PROVIDER inválido. Use 'gemini' ou 'openai'.")


async def _generate_with_gemini(summary_json: dict[str, Any]) -> str:
    api_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY não configurada para geração de insights.")

    if api_key.strip().lower() in {"stub", "debug"}:
        return _build_stub_content(summary_json, provider_name="Gemini")

    model = os.getenv("GEMINI_MODEL") or getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
    prompt = build_user_prompt(summary_json)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    params = {"key": api_key}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{PROMPT_SYSTEM}\n\n{prompt}"},
                ]
            }
        ]
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, params=params, json=payload)
        response.raise_for_status()
    data = response.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover - defensive
        raise ValueError("Resposta inválida recebida do Gemini.") from exc


async def _generate_with_openai(summary_json: dict[str, Any]) -> str:
    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY não configurada para geração de insights.")

    if api_key.strip().lower() in {"stub", "debug"}:
        return _build_stub_content(summary_json, provider_name="OpenAI")

    model = os.getenv("OPENAI_MODEL") or getattr(settings, "OPENAI_MODEL", "gpt-4.1-mini")
    prompt = build_user_prompt(summary_json)
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": PROMPT_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
    data = response.json()

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover - defensive
        raise ValueError("Resposta inválida recebida do OpenAI.") from exc


def _build_stub_content(summary_json: dict[str, Any], provider_name: str) -> str:
    """Provide a deterministic offline response for local testing environments."""

    totals = summary_json.get("totals", {})
    income = float(totals.get("income") or 0.0)
    expense = float(totals.get("expense") or 0.0)
    savings = income - expense

    categories = summary_json.get("by_category") or []
    top_category = categories[0] if categories else {"name": "despesas", "percent": 0}
    delta = summary_json.get("delta_vs_3m", {}) or {}
    income_delta = float(delta.get("income_pct") or 0.0)
    expense_delta = float(delta.get("expense_pct") or 0.0)

    diagnosis = (
        f"[{provider_name} stub] Diagnóstico: receitas de R$ {income:,.2f} e despesas de "
        f"R$ {expense:,.2f}; poupança de R$ {savings:,.2f} no mês."
    )
    action_one = (
        f"- Reforce o controle da categoria {top_category.get('name')} que responde por "
        f"{top_category.get('percent', 0):.1f}% das saídas."
    )
    action_two = (
        f"- Ajuste o orçamento se as receitas variaram {income_delta:+.1f}% vs. 3m."  # noqa: E501
    )
    action_three = (
        f"- Planeje despesas recorrentes para manter as saídas em {expense_delta:+.1f}% "
        "da média trimestral."
    )
    quick_win = "Vitória rápida: reserve 10 minutos para revisar assinaturas pouco usadas."
    cta = "Próxima meta: definir uma reserva de emergência equivalente a 3 meses de despesas."  # noqa: E501

    return "\n".join([
        diagnosis,
        action_one,
        action_two,
        action_three,
        quick_win,
        cta,
    ])
