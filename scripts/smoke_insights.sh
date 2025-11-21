#!/usr/bin/env bash
set -euo pipefail

MONTH_ARG="${1:-}"
if [[ -n "$MONTH_ARG" ]]; then
  MONTH="$MONTH_ARG"
else
  MONTH="$(date '+%Y-%m')"
fi

if [[ ! "$MONTH" =~ ^[0-9]{4}-[0-9]{2}$ ]]; then
  echo "[error] Invalid month format: $MONTH. Expected YYYY-MM." >&2
  exit 1
fi

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
RESUMO_ENDPOINT="$API_BASE_URL/api/resumo?month=$MONTH"
GENERATE_ENDPOINT="$API_BASE_URL/api/insights/generate?month=$MONTH"

INSIGHTS_MAX_PER_MONTH="${INSIGHTS_MAX_PER_MONTH:-}"
if [[ -z "$INSIGHTS_MAX_PER_MONTH" ]] && [[ -f .env ]]; then
  env_value=$(grep -E '^INSIGHTS_MAX_PER_MONTH=' .env | tail -n1 | cut -d '=' -f2-)
  INSIGHTS_MAX_PER_MONTH="${env_value:-}"
fi

if [[ -z "$INSIGHTS_MAX_PER_MONTH" ]]; then
  echo "[error] INSIGHTS_MAX_PER_MONTH must be provided via environment or .env file." >&2
  exit 1
fi

if [[ ! "$INSIGHTS_MAX_PER_MONTH" =~ ^[0-9]+$ ]]; then
  echo "[error] INSIGHTS_MAX_PER_MONTH must be a positive integer." >&2
  exit 1
fi

COOKIE_ARGS=()
if [[ -n "${COOKIE_FILE:-}" ]]; then
  COOKIE_ARGS+=(--cookie "$COOKIE_FILE")
elif [[ -f scripts/cookie.txt ]]; then
  COOKIE_ARGS+=(--cookie "scripts/cookie.txt")
fi

if [[ -n "${AUTH_HEADER:-}" ]]; then
  COOKIE_ARGS+=(-H "Authorization: ${AUTH_HEADER}")
fi

if [[ -n "${EXTRA_HEADERS:-}" ]]; then
  while IFS= read -r header_line; do
    [[ -z "$header_line" ]] && continue
    COOKIE_ARGS+=(-H "$header_line")
  done <<< "$EXTRA_HEADERS"
fi

summary_health="FAILED"
summary_generate="FAILED"
summary_429="FAILED"

printf '== Smoke insights for %s ==\n' "$MONTH"
printf 'Base URL: %s\n' "$API_BASE_URL"
printf 'INSIGHTS_MAX_PER_MONTH: %s\n\n' "$INSIGHTS_MAX_PER_MONTH"

printf '[1/3] Health check GET %s... ' "$RESUMO_ENDPOINT"
if curl -sS -f "${COOKIE_ARGS[@]}" -o /dev/null "$RESUMO_ENDPOINT"; then
  summary_health="OK"
  printf 'OK\n'
else
  printf 'FAILED\n'
fi

success_count=0
if [[ "$summary_health" == "OK" ]]; then
  printf '\n[2/3] Generating insights (expecting %s successful responses)\n' "$INSIGHTS_MAX_PER_MONTH"
  for ((i = 1; i <= INSIGHTS_MAX_PER_MONTH; i++)); do
    printf '  - Attempt %d: ' "$i"
    if curl -sS -f "${COOKIE_ARGS[@]}" -X POST -o /dev/null "$GENERATE_ENDPOINT"; then
      ((success_count++))
      printf 'OK\n'
    else
      printf 'FAILED\n'
      break
    fi
  done

  if (( success_count == INSIGHTS_MAX_PER_MONTH )); then
    summary_generate="OK"
  fi
fi

if (( success_count == INSIGHTS_MAX_PER_MONTH )); then
  printf '\n[3/3] Validating rate limit enforcement (expecting 429)\n'
  printf '  - Additional attempt: '
  if curl -sS -f "${COOKIE_ARGS[@]}" -X POST -o /dev/null "$GENERATE_ENDPOINT"; then
    printf 'UNEXPECTED SUCCESS\n'
  else
    status_code=$(curl -sS "${COOKIE_ARGS[@]}" -X POST -o /dev/null -w '%{http_code}' "$GENERATE_ENDPOINT")
    if [[ "$status_code" == "429" ]]; then
      summary_429="OK"
      printf '429 received\n'
    else
      printf 'Unexpected status %s\n' "$status_code"
    fi
  fi
fi

printf '\nSummary:\n'
printf '  Health check............. %s\n' "$summary_health"
printf '  Successful generations... %s/%s (%s)\n' "$success_count" "$INSIGHTS_MAX_PER_MONTH" "$summary_generate"
printf '  429 after limit......... %s\n' "$summary_429"

printf '\nUsage:\n  bash scripts/smoke_insights.sh 2025-11\n'
