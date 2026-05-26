#!/usr/bin/env bash
# Mnémlet Demo — v0.2 terminal cast for launch surface
# Shows: remember → sleep briefing → context pack → explain → vault
# Run: bash scripts/demo.sh

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
YELLOW="\033[33m"
DIM="\033[2m"
RESET="\033[0m"

if [[ -n "${MNEMLET_DEMO_PORT:-}" ]]; then
  PORT="${MNEMLET_DEMO_PORT}"
elif (exec 3<>/dev/tcp/127.0.0.1/14060) >/dev/null 2>&1; then
  PORT="14061"
else
  PORT="14060"
fi
BASE="http://127.0.0.1:${PORT}"
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

echo -e "${BOLD}Mnémlet v0.2.0 — Memory that forgets, sleeps, and explains itself${RESET}"
echo -e "${BLUE}Throwaway demo vault: ${DATA_DIR}${RESET}"
echo ""

echo -e "${YELLOW}▶ Starting isolated Mnémlet demo server...${RESET}"
MNEMLET_DATA_DIR="${DATA_DIR}" .venv/bin/mnemlet serve --host 127.0.0.1 --port "${PORT}" >"${SERVER_LOG}" 2>&1 &
PID=$!

for _ in $(seq 1 30); do
  if curl -fsS "${BASE}/api/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS "${BASE}/api/v1/health" >/dev/null
echo -e "${GREEN}✓ Demo server running at ${BASE}${RESET}"
echo ""

echo -e "${YELLOW}▶ Remembering three v0.2 memories...${RESET}"
echo -e "${BOLD}$ curl -X POST ${BASE}/api/v1/remember -d '{... preference ...}'${RESET}"
PREF_JSON="$(curl -fsS -X POST "${BASE}/api/v1/remember" \
  -H 'Content-Type: application/json' \
  -d '{"content":"Christoph prefers dark mode in all editors","namespace":"preferences","importance":0.9,"memory_type":"preference"}')"
printf '%s\n' "${PREF_JSON}" | pretty_json
PREF_ID="$(printf '%s\n' "${PREF_JSON}" | json_get '["memory_id"]')"
echo ""

echo -e "${BOLD}$ curl -X POST ${BASE}/api/v1/remember -d '{... project fact ...}'${RESET}"
curl -fsS -X POST "${BASE}/api/v1/remember" \
  -H 'Content-Type: application/json' \
  -d '{"content":"Mnémlet v0.2 adds context packs, provenance, and review commands","namespace":"projects/mnemlet","importance":0.85,"memory_type":"fact"}' | pretty_json
echo ""

echo -e "${BOLD}$ curl -X POST ${BASE}/api/v1/remember -d '{... transient event ...}'${RESET}"
curl -fsS -X POST "${BASE}/api/v1/remember" \
  -H 'Content-Type: application/json' \
  -d '{"content":"Today Christoph is polishing the public v0.2 launch surface","namespace":"daily_chat","importance":0.35,"memory_type":"event"}' | pretty_json
echo ""

echo -e "${YELLOW}▶ Running Sleep Engine...${RESET}"
echo -e "${BOLD}$ curl -X POST ${BASE}/api/v1/sleep/start${RESET}"
curl -fsS -X POST "${BASE}/api/v1/sleep/start" | pretty_json

for _ in $(seq 1 150); do
  STATUS_JSON="$(curl -fsS "${BASE}/api/v1/sleep/status")"
  STATE="$(printf '%s\n' "${STATUS_JSON}" | json_get '["state"]')"
  BRIEFING_READY="$(printf '%s\n' "${STATUS_JSON}" | json_get '["checkpoint"].get("_task_prepare_briefing")')"
  if [[ "${STATE}" == "completed" || "${BRIEFING_READY}" == "True" ]]; then
    break
  fi
  sleep 1
done

echo -e "${BOLD}$ curl ${BASE}/api/v1/sleep/status${RESET}"
curl -fsS "${BASE}/api/v1/sleep/status" | pretty_json
echo ""

echo -e "${YELLOW}▶ Morning briefing written to the Markdown vault:${RESET}"
BRIEFING_FILE="$(find "${DATA_DIR}/vault/__system__/morning_briefing" -name 'briefing-*.md' | sort | tail -1)"
echo -e "${BOLD}$ sed -n '1,18p' ${BRIEFING_FILE#${DATA_DIR}/}${RESET}"
sed -n '1,18p' "${BRIEFING_FILE}"
echo ""

echo -e "${YELLOW}▶ Context Pack with abstention/provenance metadata:${RESET}"
echo -e "${BOLD}$ curl -X POST ${BASE}/api/v1/context -d '{"query":"editor theme preference"}'${RESET}"
curl -fsS -X POST "${BASE}/api/v1/context" \
  -H 'Content-Type: application/json' \
  -d '{"query":"editor theme preference","namespace":"preferences","limit":3,"min_score":0.1}' | pretty_json
echo ""

echo -e "${YELLOW}▶ Explain why Mnémlet knows this:${RESET}"
echo -e "${BOLD}$ curl ${BASE}/api/v1/explain/${PREF_ID}${RESET}"
curl -fsS "${BASE}/api/v1/explain/${PREF_ID}" | pretty_json
echo ""

echo -e "${YELLOW}▶ Inspectable vault file:${RESET}"
VAULT_FILE="$(find "${DATA_DIR}/vault/preferences" -name "${PREF_ID}.md" | sort | tail -1)"
echo -e "${BOLD}$ sed -n '1,16p' ${VAULT_FILE#${DATA_DIR}/}${RESET}"
sed -n '1,16p' "${VAULT_FILE}"
echo ""

echo -e "${GREEN}${BOLD}Mnémlet runs locally. Your agents wake up with memory they can inspect.${RESET}"
echo -e "${DIM}github.com/christoph/mnemlet${RESET}"
