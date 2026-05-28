#!/usr/bin/env bash
# Mnémlet Demo - v0.3 Trust / Security / Privacy release surface
# Shows: API-key auth -> Secret Guard -> Audit -> Explain Trust
# Run: bash scripts/demo.sh

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
YELLOW="\033[33m"
DIM="\033[2m"
RESET="\033[0m"

DATA_DIR="$(mktemp -d -t mnemlet-demo.XXXXXX)"
SERVER_LOG="${DATA_DIR}/server.log"
PID=""

cleanup() {
  if [[ -n "${PID}" ]]; then
    kill "${PID}" >/dev/null 2>&1 || true
    wait "${PID}" >/dev/null 2>&1 || true
  fi
  rm -rf "${DATA_DIR}"
}
trap cleanup EXIT

json_get() {
  .venv/bin/python -c "import json,sys; print(json.load(sys.stdin)$1)"
}

pretty_json() {
  .venv/bin/python -m json.tool
}

port_is_free() {
  .venv/bin/python - "$1" <<'PY'
import socket
import sys

port = int(sys.argv[1])
try:
    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
        raise SystemExit(1)
except OSError:
    raise SystemExit(0)
PY
}

if [[ -n "${MNEMLET_DEMO_PORT:-}" ]]; then
  PORT="${MNEMLET_DEMO_PORT}"
  if ! port_is_free "${PORT}"; then
    echo "MNEMLET_DEMO_PORT is already in use: ${PORT}" >&2
    exit 1
  fi
elif port_is_free 14060; then
  PORT="14060"
elif port_is_free 14061; then
  PORT="14061"
else
  echo "Neither demo port 14060 nor 14061 is free" >&2
  exit 1
fi

BASE="http://127.0.0.1:${PORT}"
export MNEMLET_API_KEY="$(.venv/bin/mnemlet auth generate-key)"

auth_header=(-H "X-Mnemlet-Key: ${MNEMLET_API_KEY}")
json_header=(-H 'Content-Type: application/json')

echo -e "${BOLD}Mnémlet v0.3 - Trust / Security / Privacy${RESET}"
echo -e "${BLUE}Throwaway demo vault: ${DATA_DIR}${RESET}"
echo -e "${DIM}Demo key generated in-process and discarded on exit.${RESET}"
echo ""

echo -e "${YELLOW}> Starting isolated authenticated Mnémlet demo server...${RESET}"
MNEMLET_DATA_DIR="${DATA_DIR}" MNEMLET_API_KEY="${MNEMLET_API_KEY}" \
  .venv/bin/mnemlet serve --host 127.0.0.1 --port "${PORT}" >"${SERVER_LOG}" 2>&1 &
PID=$!

for _ in $(seq 1 30); do
  if ! kill -0 "${PID}" >/dev/null 2>&1; then
    echo "Demo server exited before becoming healthy" >&2
    .venv/bin/python - "${SERVER_LOG}" <<'PY' >&2
from pathlib import Path
import sys

print(Path(sys.argv[1]).read_text(errors="replace")[:4000])
PY
    exit 1
  fi
  if curl -fsS "${auth_header[@]}" "${BASE}/api/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS "${auth_header[@]}" "${BASE}/api/v1/health" >/dev/null
echo -e "${GREEN}OK Demo server running at ${BASE}${RESET}"
echo ""

echo -e "${YELLOW}> Remembering an authenticated preference...${RESET}"
echo -e "${BOLD}$ curl -X POST ${BASE}/api/v1/remember -H 'Content-Type: application/json' -H 'X-Mnemlet-Key: ...' -d '{... preference ...}'${RESET}"
PREF_JSON="$(curl -fsS -X POST "${BASE}/api/v1/remember" \
  "${auth_header[@]}" \
  "${json_header[@]}" \
  -d '{"content":"Christoph prefers dark mode in all editors","namespace":"preferences","importance":0.9,"memory_type":"preference"}')"
printf '%s\n' "${PREF_JSON}" | pretty_json
PREF_ID="$(printf '%s\n' "${PREF_JSON}" | json_get '["memory_id"]')"
echo ""

echo -e "${YELLOW}> Secret Guard blocks a fake test key before storage...${RESET}"
FAKE_KEY="sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
echo -e "${BOLD}$ curl -X POST ${BASE}/api/v1/ingest -H 'Content-Type: application/json' -H 'X-Mnemlet-Key: ...' -d '{... fake key ...}'${RESET}"
SECRET_RESPONSE="$(curl -sS -X POST "${BASE}/api/v1/ingest" \
  "${auth_header[@]}" \
  "${json_header[@]}" \
  -d "{\"content\":\"temporary test token ${FAKE_KEY}\",\"namespace\":\"security-demo\"}")"
printf '%s\n' "${SECRET_RESPONSE}" | pretty_json
echo ""

echo -e "${YELLOW}> Audit shows success and blocked security events...${RESET}"
echo -e "${BOLD}$ curl ${BASE}/api/v1/audit -H 'X-Mnemlet-Key: ...'${RESET}"
curl -fsS "${auth_header[@]}" "${BASE}/api/v1/audit?limit=8" | pretty_json
echo ""

echo -e "${YELLOW}> Explain includes a Trust block for the stored memory...${RESET}"
echo -e "${BOLD}$ curl ${BASE}/api/v1/explain/${PREF_ID} -H 'X-Mnemlet-Key: ...'${RESET}"
curl -fsS "${auth_header[@]}" "${BASE}/api/v1/explain/${PREF_ID}" | pretty_json
echo ""

echo -e "${GREEN}${BOLD}Mnémlet runs locally with throwaway auth, sanitized audit, and inspectable trust metadata.${RESET}"
echo ""
echo -e "${YELLOW}> v0.4 (opt-in): intelligent memory extraction${RESET}"
echo -e "${DIM}With an LLM enabled ([llm].enabled + [intelligence].extraction_enabled), the${RESET}"
echo -e "${DIM}'mnemlet_observe' MCP tool buffers conversations and the LLM extracts memories${RESET}"
echo -e "${DIM}and summaries per session. Disabled here (no LLM). See docs/INTELLIGENT_EXTRACTION.md${RESET}"
echo -e "${DIM}github.com/christoph/mnemlet${RESET}"
