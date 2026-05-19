#!/usr/bin/env bash
# Mnémlet Demo — terminal cast for launch
# Shows: start → ingest → recall → sleep → vault → briefing
# Run: bash scripts/demo.sh

set -e

BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
YELLOW="\033[33m"
RESET="\033[0m"

echo -e "${BOLD}🧠 Mnémlet v0.1.0 — Self-Hosted Memory Engine${RESET}"
echo -e "${BLUE}Running on: Raspberry Pi 5 (16GB, ARM64)${RESET}"
echo ""

# Start Mnémlet
echo -e "${YELLOW}▶ Starting Mnémlet...${RESET}"
/home/christoph/mnemlet/.venv/bin/mnemlet serve --port 14060 &
PID=$!
sleep 5

# Wait for server to be ready
for i in $(seq 1 10); do
  if curl -s http://localhost:14060/api/v1/health > /dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo -e "${GREEN}✓ Server running at http://127.0.0.1:14060${RESET}"
echo ""

# Ingest memories
echo -e "${YELLOW}▶ Ingesting memories...${RESET}"
echo -e "${BOLD}$ curl -X POST /api/v1/ingest -d '{\"content\":\"Christoph prefers dark mode in all editors\",\"namespace\":\"preferences\",\"importance\":0.9}'${RESET}"
curl -s -X POST http://localhost:14060/api/v1/ingest -H 'Content-Type: application/json' -d '{"content":"Christoph prefers dark mode in all editors","namespace":"preferences","importance":0.9}' | python3 -m json.tool
echo ""

echo -e "${BOLD}$ curl -X POST /api/v1/ingest -d '{\"content\":\"Christoph asked about today\\'s weather in Berlin\",\"namespace\":\"daily_chat\",\"importance\":0.2}'${RESET}"
curl -s -X POST http://localhost:14060/api/v1/ingest -H 'Content-Type: application/json' -d '{"content":"Christoph asked about today'\''s weather in Berlin","namespace":"daily_chat","importance":0.2}' | python3 -m json.tool
echo ""

echo -e "${BOLD}$ curl -X POST /api/v1/ingest -d '{\"content\":\"MiroFish is the main active project\",\"namespace\":\"projects/mirofish\",\"importance\":0.8}'${RESET}"
curl -s -X POST http://localhost:14060/api/v1/ingest -H 'Content-Type: application/json' -d '{"content":"MiroFish is the main active project","namespace":"projects/mirofish","importance":0.8}' | python3 -m json.tool
echo ""

# Show status
echo -e "${YELLOW}▶ Memory status:${RESET}"
echo -e "${BOLD}$ curl /api/v1/status${RESET}"
curl -s http://localhost:14060/api/v1/status | python3 -m json.tool
echo ""

# Recall
echo -e "${YELLOW}▶ Recalling: 'editor theme preference'${RESET}"
echo -e "${BOLD}$ curl /api/v1/recall -d '{\"query\":\"editor theme preference\"}'${RESET}"
curl -s -X POST http://localhost:14060/api/v1/recall -H 'Content-Type: application/json' -d '{"query":"editor theme preference","limit":3}' | python3 -m json.tool
echo ""

# Configure decay
echo -e "${YELLOW}▶ Set decay rates per namespace:${RESET}"
echo -e "${BOLD}$ curl PUT /api/v1/namespaces/preferences/decay -d '{\"lambda\":0.001}'  ← preferences: ~2yr half-life${RESET}"
curl -s -X PUT http://localhost:14060/api/v1/namespaces/preferences/decay -H 'Content-Type: application/json' -d '{"lambda":0.001}' | python3 -m json.tool
echo ""

echo -e "${BOLD}$ curl PUT /api/v1/namespaces/daily_chat/decay -d '{\"lambda\":0.5}'    ← daily chat: ~1.4day half-life${RESET}"
curl -s -X PUT http://localhost:14060/api/v1/namespaces/daily_chat/decay -H 'Content-Type: application/json' -d '{"lambda":0.5}' | python3 -m json.tool
echo ""

# Trigger sleep
echo -e "${YELLOW}▶ Triggering Sleep Engine (night consolidation)...${RESET}"
echo -e "${BOLD}$ curl POST /api/v1/sleep/start${RESET}"
curl -s -X POST http://localhost:14060/api/v1/sleep/start | python3 -m json.tool
sleep 8
curl -s http://localhost:14060/api/v1/sleep/status | python3 -m json.tool
echo ""

# Show vault
echo -e "${YELLOW}▶ Inspectable Markdown Vault:${RESET}"
echo -e "${BOLD}$ ls ~/.mnemlet/vault/preferences/*/${RESET}"
ls ~/.mnemlet/vault/preferences/*/ 2>/dev/null
echo ""
echo -e "${BOLD}$ cat ~/.mnemlet/vault/preferences/*/$(ls ~/.mnemlet/vault/preferences/*/ 2>/dev/null | head -1)${RESET}"
cat ~/.mnemlet/vault/preferences/*/$(ls ~/.mnemlet/vault/preferences/*/ 2>/dev/null | head -1) 2>/dev/null
echo ""

# Show API
echo -e "${YELLOW}▶ API Reference:${RESET}"
echo -e "  GET  /api/v1/health        — Health check"
echo -e "  GET  /api/v1/status        — Memory counts"
echo -e "  POST /api/v1/ingest        — Store memory"
echo -e "  POST /api/v1/recall        — Retrieve memories"
echo -e "  POST /api/v1/decay/run     — Manual decay"
echo -e "  GET  /api/v1/namespaces/{ns}/decay — Config"
echo -e "  GET  /api/v1/vault         — Vault path"
echo -e "  GET  /api/v1/sleep/status  — Sleep state"
echo -e "  POST /api/v1/sleep/start   — Start sleep"
echo -e "  /mcp                        — MCP server (8 tools)"
echo ""

echo -e "${GREEN}${BOLD}🧠 Mnémlet runs on this Pi. Your agents wake up smarter.${RESET}"
echo -e "${BLUE}github.com/christoph/mnemlet${RESET}"

kill $PID 2>/dev/null || true
