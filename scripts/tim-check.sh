#!/usr/bin/env bash
# tim-check.sh — TIM pipeline diagnostic. Run from project root.
# Usage: ./scripts/tim-check.sh

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS() { echo -e "  ${GREEN}PASS${NC} $1"; }
FAIL() { echo -e "  ${RED}FAIL${NC} $1"; FAILURES=$((FAILURES+1)); }
WARN() { echo -e "  ${YELLOW}WARN${NC} $1"; }
FAILURES=0

echo "=== TIM Pipeline Diagnostic ==="
echo ""

# ── 1. Services up ────────────────────────────────────────────────────────────
echo "1. Services"

for svc in "8001:/health:feed-orchestrator" "8002:/health:semantic-engine" "8003:/health:briefing-generator"; do
  port="${svc%%:*}"; rest="${svc#*:}"; path="${rest%%:*}"; name="${rest##*:}"
  if curl -sf "http://localhost:${port}${path}" > /dev/null 2>&1; then
    PASS "$name (localhost:$port)"
  else
    FAIL "$name unreachable at localhost:$port"
  fi
done

if curl -sf http://localhost:3000 | grep -q "root" 2>/dev/null; then
  PASS "soc-dashboard (localhost:3000)"
else
  FAIL "soc-dashboard unreachable at localhost:3000"
fi

# ── 2. Ollama models ──────────────────────────────────────────────────────────
echo ""
echo "2. Ollama models"

OLLAMA_CID=$(docker ps -qf name=ollama 2>/dev/null)
if [ -z "$OLLAMA_CID" ]; then
  FAIL "ollama container not running"
else
  MODELS=$(docker exec "$OLLAMA_CID" ollama list 2>/dev/null)
  echo "$MODELS" | grep -q "llama3.2:3b"       && PASS "llama3.2:3b"        || FAIL "llama3.2:3b not pulled"
  echo "$MODELS" | grep -q "nomic-embed-text"   && PASS "nomic-embed-text"   || FAIL "nomic-embed-text not pulled"
fi

# ── 3. Feed data ──────────────────────────────────────────────────────────────
echo ""
echo "3. Feed data"

FEEDS=$(curl -sf http://localhost:8001/feeds/status 2>/dev/null)
if [ -z "$FEEDS" ]; then
  FAIL "feeds/status returned nothing"
else
  COUNT=$(echo "$FEEDS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('feeds', [])))" 2>/dev/null)
  [ "$COUNT" = "5" ] && PASS "5 feeds reporting" || FAIL "expected 5 feeds, got ${COUNT:-0}"

  OK=$(echo "$FEEDS" | python3 -c "
import sys,json
d=json.load(sys.stdin)
ok=[f['name'] for f in d.get('feeds',[]) if f.get('status')=='ok']
err=[f['name'] for f in d.get('feeds',[]) if f.get('status')=='error']
print('ok:'+ ','.join(ok) + ' | err:' + ','.join(err) if err else 'ok:'+','.join(ok))
" 2>/dev/null)
  echo "     $OK"
fi

# ── 4. OpenCTI indicators ─────────────────────────────────────────────────────
echo ""
echo "4. OpenCTI data (via briefing-generator)"

BRIEFING_CID=$(docker ps -qf name=briefing 2>/dev/null)
if [ -z "$BRIEFING_CID" ]; then
  FAIL "briefing-generator container not running"
else
  RESULT=$(docker exec "$BRIEFING_CID" python3 -c "
from opencti_client import build_pycti_client
client = build_pycti_client()
r = client.indicator.list(first=1)
print(len(r) if r else 0)
" 2>/dev/null | tail -1)
  [ "${RESULT:-0}" -gt 0 ] 2>/dev/null && PASS "OpenCTI has indicators (unfiltered: $RESULT+)" || FAIL "OpenCTI returned 0 indicators — is it populated?"
fi

STATS=$(curl -sf http://localhost:8003/stats 2>/dev/null)
IOC_24H=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('ioc_count_24h',0))" 2>/dev/null)
[ "${IOC_24H:-0}" -gt 0 ] && PASS "ioc_count_24h: $IOC_24H" || WARN "ioc_count_24h: 0 (IOCs may be older than 24h — try 168h briefing)"

# ── 5. Semantic search / ChromaDB ─────────────────────────────────────────────
echo ""
echo "5. Semantic search"

SEARCH=$(curl -sf "http://localhost:8002/search?q=malware&n_results=5" 2>/dev/null)
IDX_STATUS=$(curl -sf http://localhost:8002/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'), '|', d.get('indexed',0), 'indexed')" 2>/dev/null)
echo "     Index: $IDX_STATUS"

COUNT=$(echo "$SEARCH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null)
[ "${COUNT:-0}" -gt 0 ] && PASS "search('malware') → $COUNT result(s)" || WARN "search returned 0 results — ChromaDB may be empty, wait for index cycle"

# ── 6. LLM round-trip (briefing generation) ───────────────────────────────────
echo ""
echo "6. LLM round-trip (168h briefing — takes 60-90s)"
read -r -p "   Run LLM test? [y/N] " yn
if [[ "$yn" =~ ^[Yy]$ ]]; then
  BID=$(curl -sf -X POST http://localhost:8003/generate \
    -H "Content-Type: application/json" \
    -d '{"period_hours":168}' 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('briefing_id',''))" 2>/dev/null)

  if [ -z "$BID" ]; then
    FAIL "POST /generate returned no briefing_id"
  else
    echo "     briefing_id: $BID — polling..."
    for i in $(seq 1 18); do
      sleep 5
      STATUS=$(curl -sf "http://localhost:8003/briefings/$BID" 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null)
      [ "$STATUS" = "done" ] && break
      [ "$STATUS" = "error" ] && break
      echo -n "."
    done
    echo ""
    if [ "$STATUS" = "done" ]; then
      TEXT=$(curl -sf "http://localhost:8003/briefings/$BID" 2>/dev/null \
        | python3 -c "import sys,json; t=json.load(sys.stdin).get('text',''); print(t[:200])" 2>/dev/null)
      # Check if LLM produced real content vs "no threats" filler
      if echo "$TEXT" | grep -qi "no new indicators\|no new ioc\|not identified any\|lack of activity\|no.*identified"; then
        WARN "LLM generated 'nothing to report' — OpenCTI data may be empty or outside window"
        echo "     Preview: ${TEXT:0:120}..."
      else
        PASS "LLM produced content with real threat data"
        echo "     Preview: ${TEXT:0:120}..."
      fi
    elif [ "$STATUS" = "error" ]; then
      FAIL "generation errored — check: docker logs \$(docker ps -qf name=briefing)"
    else
      FAIL "timed out after 90s (status: $STATUS) — check ollama logs"
    fi
  fi
else
  echo "     Skipped."
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Summary ==="
if [ "$FAILURES" -eq 0 ]; then
  echo -e "${GREEN}All checks passed.${NC}"
else
  echo -e "${RED}$FAILURES check(s) failed.${NC}"
  echo "Common fixes:"
  echo "  Services down    → docker compose --profile platform --profile feeds --profile semantic --profile briefings --profile dashboard up -d"
  echo "  Models missing   → docker exec \$(docker ps -qf name=ollama) ollama pull llama3.2:3b"
  echo "  Code not updated → docker compose --profile platform --profile briefings build briefing-generator && docker compose --profile platform --profile briefings up -d briefing-generator"
  echo "  Empty OpenCTI    → docker compose restart feed-orchestrator   (triggers fresh feed collection)"
fi
