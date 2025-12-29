"""HTTP-based client for Large Language Model providers."""
from __future__ import annotations

import json
import os
import time
from typing import Any

from app.core.config import settings


def _should_use_httpx_stub() -> bool:
    """Return True when the lightweight httpx stub should be used."""

    env = (os.getenv("ENV") or getattr(settings, "ENV", "")).strip().lower()
    if env == "production":
        return False

    raw_flag = (os.getenv("DEBUG_HTTPX_STUB") or "").strip().lower()
    return raw_flag in {"1", "true", "yes", "on"}


if _should_use_httpx_stub():
    from app.dev import httpx_stub as httpx  # type: ignore  # pragma: no cover
else:
    import httpx


PROMPT_SYSTEM = (
    "Você é um analista financeiro didático que gera insights claros, sem jargões, "
    "baseados apenas em agregados financeiros mensais. NUNCA cite PII/lojas; use "
    "APENAS agregados."
)
CATEGORY_PROMPT_SYSTEM = (
    "Você é um assistente financeiro que classifica transações em categorias. "
    "Sempre escolha apenas uma categoria da lista fornecida e responda somente com o nome exato."
)


def _resolve_provider() -> str:
    provider = (os.getenv("LLM_PROVIDER") or getattr(settings, "LLM_PROVIDER", "")).strip().lower()
    return provider or "gemini"


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

    provider = _resolve_provider()

    if provider == "gemini":
        return await _generate_with_gemini(summary_json)
    elif provider == "openai":
        return await _generate_with_openai(summary_json)
    elif provider == "ollama":
        return await _generate_with_ollama(summary_json)

    raise ValueError("LLM_PROVIDER inválido. Use 'gemini', 'openai' ou 'ollama'.")


async def _generate_with_gemini(summary_json: dict[str, Any]) -> str:
    prompt = build_user_prompt(summary_json)
    stub_response = _build_stub_content(summary_json, provider_name="Gemini")
    return await _call_gemini(prompt, system_prompt=PROMPT_SYSTEM, stub_response=stub_response)


async def _generate_with_openai(summary_json: dict[str, Any]) -> str:
    prompt = build_user_prompt(summary_json)
    stub_response = _build_stub_content(summary_json, provider_name="OpenAI")
    return await _call_openai(prompt, system_prompt=PROMPT_SYSTEM, stub_response=stub_response)


async def _generate_with_ollama(summary_json: dict[str, Any]) -> str:
    model = getattr(settings, "OLLAMA_MODEL", "")
    base_url = settings.OLLAMA_URL

    if not model:
        raise ValueError("OLLAMA_MODEL não configurado para geração de insights.")
    if not base_url:
        raise ValueError("OLLAMA_URL não configurada para geração de insights.")

    prompt = build_user_prompt(summary_json)
    stub_response = _build_stub_content(summary_json, provider_name="Ollama")

    if str(model).strip().lower() in {"stub", "debug"} or str(base_url).strip().lower() in {"stub", "debug"}:
        return stub_response

    payload = {"model": model, "prompt": prompt, "stream": False}
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(base_url, json=payload)
        response.raise_for_status()
    data = response.json()

    try:
        raw_response = data.get("response") or data.get("message", {}).get("content")
        if not raw_response:
            raise KeyError("missing response")
        return str(raw_response).strip()
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("Resposta inválida recebida do Ollama.") from exc


async def _call_gemini(user_prompt: str, *, system_prompt: str, stub_response: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY não configurada para geração de insights.")

    if api_key.strip().lower() in {"stub", "debug"}:
        return stub_response

    model = os.getenv("GEMINI_MODEL") or getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    params = {"key": api_key}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _combine_prompts(system_prompt, user_prompt)},
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


async def _call_openai(user_prompt: str, *, system_prompt: str, stub_response: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY não configurada para geração de insights.")

    if api_key.strip().lower() in {"stub", "debug"}:
        return stub_response

    model = os.getenv("OPENAI_MODEL") or getattr(settings, "OPENAI_MODEL", "gpt-4.1-mini")
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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


async def _call_ollama(prompt: str, *, stub_response: str) -> str:
    model = os.getenv("OLLAMA_MODEL") or getattr(settings, "OLLAMA_MODEL", "phi3")
    base_url = os.getenv("OLLAMA_URL") or getattr(settings, "OLLAMA_URL", "")
    if not base_url:
        raise ValueError("OLLAMA_URL não configurada para geração de insights.")

    if str(model).strip().lower() in {"stub", "debug"} or base_url.strip().lower() in {"stub", "debug"}:
        return stub_response

    payload = {"model": model, "prompt": prompt, "stream": False}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(base_url, json=payload)
        response.raise_for_status()
    data = response.json()

    try:
        raw_response = data.get("response") or data.get("message", {}).get("content")
        if not raw_response:
            raise KeyError("missing response")
        return str(raw_response).strip()
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("Resposta inválida recebida do Ollama.") from exc


def _combine_prompts(system_prompt: str, user_prompt: str) -> str:
    return f"{system_prompt}\n\n{user_prompt}".strip()


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


def _build_category_prompt(description: str, category_names: list[str]) -> str:
    categories = "\n".join(f"- {name}" for name in category_names)
    instructions = (
        "Escolha a categoria mais adequada para a transação a seguir usando apenas a lista fornecida. "
        "Responda SOMENTE com o nome exato de uma categoria, sem texto adicional."
    )
    return (
        f"{instructions}\n\nDescrição: {description.strip()}\nCategorias disponíveis:\n{categories}"
    )


def _normalize_category_choice(raw_response: str, category_names: list[str]) -> str:
    cleaned = (raw_response or "").strip().splitlines()[0]
    cleaned = cleaned.strip(" -•\t.:\"'")
    for name in category_names:
        if cleaned.lower() == name.lower():
            return name
    for name in category_names:
        if cleaned.lower() in name.lower() or name.lower() in cleaned.lower():
            return name
    return category_names[0]


async def suggest_category(description: str, category_names: list[str]) -> str:
    """Ask the configured provider to pick the best category for a transaction."""

    valid_categories = [name.strip() for name in category_names if name and name.strip()]
    if not valid_categories:
        raise ValueError("Nenhuma categoria disponível para sugestão.")

    provider = _resolve_provider()
    prompt = _build_category_prompt(description, valid_categories)
    default_choice = valid_categories[0]

    if provider == "gemini":
        raw = await _call_gemini(prompt, system_prompt=CATEGORY_PROMPT_SYSTEM, stub_response=default_choice)
    elif provider == "openai":
        raw = await _call_openai(prompt, system_prompt=CATEGORY_PROMPT_SYSTEM, stub_response=default_choice)
    elif provider == "ollama":
        raw = await _call_ollama(_combine_prompts(CATEGORY_PROMPT_SYSTEM, prompt), stub_response=default_choice)
    else:
        raise ValueError("LLM_PROVIDER inválido. Use 'gemini', 'openai' ou 'ollama'.")

    return _normalize_category_choice(raw, valid_categories)


async def test_llm_connectivity() -> dict[str, Any]:
    """Lightweight connectivity test to the configured provider."""
    provider = _resolve_provider()
    sample_summary = {
        "totals": {"income": 1000, "expense": 800},
        "by_category": [{"name": "geral", "percent": 80}],
        "delta_vs_3m": {"income_pct": 0, "expense_pct": 0},
    }
    started = time.perf_counter()
    try:
        text = await generate_insight(sample_summary)
        duration_ms = (time.perf_counter() - started) * 1000
        return {
            "ok": True,
            "provider": provider,
            "latency_ms": round(duration_ms, 1),
            "preview": (text or "").strip()[:200],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "provider": provider,
            "detail": str(exc),
        }
