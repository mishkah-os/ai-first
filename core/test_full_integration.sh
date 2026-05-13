#!/bin/bash
# Full Integration Test — QDML Platform + POS
set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║            QDML PLATFORM — FULL INTEGRATION TEST            ║"
echo "╚══════════════════════════════════════════════════════════════╝"

cd /srv/apps/ai-first/core

# Start API
python3 main.py > /tmp/qdml-test.log 2>&1 &
API_PID=$!
sleep 3

PASS=0; FAIL=0
check() {
    if [ "$2" = "0" ]; then echo "  ✅ $1"; PASS=$((PASS+1))
    else echo "  ❌ $1"; FAIL=$((FAIL+1)); fi
}

echo ""
echo "═══ 1. Core Health ═══"
STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/health)
check "API Health" $([ "$STATUS" = "200" ] && echo 0 || echo 1)

echo ""
echo "═══ 2. Authentication ═══"
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
check "Login" $([ -n "$TOKEN" ] && echo 0 || echo 1)

VERIFY=$(curl -s -X POST http://localhost:8001/api/auth/verify -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json;print(json.load(sys.stdin).get('ok',False))" 2>/dev/null)
check "Token verify" $([ "$VERIFY" = "True" ] && echo 0 || echo 1)

echo ""
echo "═══ 3. AI Protocol ═══"
# Reveal
R=$(curl -s -X POST http://localhost:8001/api/ai/ -H "Content-Type: application/json" -d '{"action":"reveal","selector":{}}')
check "AI Reveal" $(echo "$R" | python3 -c "import sys,json;d=json.load(sys.stdin);print(0 if d.get('success') else 1)" 2>/dev/null)

# Mini
M=$(curl -s -X POST http://localhost:8001/api/ai/ -H "Content-Type: application/json" -d '{"action":"mini","selector":{"project":"pos"},"level":1}')
check "AI Mini POS" $(echo "$M" | python3 -c "import sys,json;d=json.load(sys.stdin);print(0 if d.get('success') else 1)" 2>/dev/null)

# Compile
C=$(curl -s -X POST http://localhost:8001/api/ai/ -H "Content-Type: application/json" -d '{"action":"compile","selector":{"project":"pos","component":"kds-main-screen"}}')
LINES=$(echo "$C" | python3 -c "import sys,json;print(json.load(sys.stdin).get('lines',0))" 2>/dev/null)
check "AI Compile KDS ($LINES lines)" $([ "$LINES" -gt 100 ] && echo 0 || echo 1)

# Create with Bedrock
CREATE=$(curl -s -X POST http://localhost:8001/api/ai/ -H "Content-Type: application/json" \
  -d '{"action":"create","target":"pos/screen-pos/order-history-widget","prompt":"Create an order history widget showing last 10 orders with status badges"}')
check "AI Create (Bedrock)" $(echo "$CREATE" | python3 -c "import sys,json;d=json.load(sys.stdin);print(0 if d.get('success') else 1)" 2>/dev/null)

echo ""
echo "═══ 4. Kit System ═══"
KITS=$(curl -s http://localhost:8001/api/kits/ | python3 -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null)
check "List kits ($KITS)" $([ "$KITS" = "3" ] && echo 0 || echo 1)

PIPES=$(curl -s http://localhost:8001/api/kits/pipelines | python3 -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null)
check "List pipelines ($PIPES)" $([ "$PIPES" = "3" ] && echo 0 || echo 1)

KIT_COMP=$(curl -s -X POST http://localhost:8001/api/kits/compile-kit/mobile-kit -H "Content-Type: application/json" -d '{"variables":{"app_name":"TestApp"}}')
check "Compile mobile kit" $(echo "$KIT_COMP" | python3 -c "import sys,json;d=json.load(sys.stdin);print(0 if d.get('lines',0)>100 else 1)" 2>/dev/null)

PIPE_EXEC=$(curl -s -X POST http://localhost:8001/api/kits/pipelines/build-mobile-app/execute -H "Content-Type: application/json" \
  -d '{"app_name":"Test","app_id":"test","platforms":["android"]}')
check "Execute pipeline" $(echo "$PIPE_EXEC" | python3 -c "import sys,json;d=json.load(sys.stdin);print(0 if d.get('status')=='completed' else 1)" 2>/dev/null)

echo ""
echo "═══ 5. QDML Protocol ═══"
STATS=$(curl -s -X POST http://localhost:8001/api/qdml -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"action":"stats"}')
check "QDML stats" $(echo "$STATS" | python3 -c "import sys,json;d=json.load(sys.stdin);print(0 if d.get('ok') else 1)" 2>/dev/null)

DESC=$(curl -s -X POST http://localhost:8001/api/qdml -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"action":"describe","project":"pos"}')
check "QDML describe POS" $(echo "$DESC" | python3 -c "import sys,json;d=json.load(sys.stdin);print(0 if d.get('ok') else 1)" 2>/dev/null)

COMPILE=$(curl -s -X POST http://localhost:8001/api/qdml -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"action":"compile","project":"pos","component":"printer-service"}')
check "QDML compile printer" $(echo "$COMPILE" | python3 -c "import sys,json;d=json.load(sys.stdin);print(0 if d.get('ok') else 1)" 2>/dev/null)

echo ""
echo "═══ 6. POS Specific ═══"
# Check all POS components compile
for comp in branch-manager schema-crud menu-engine delivery-engine reservation-engine order-domain pos-main-screen finance-screen dashboard-screen; do
    R=$(curl -s -X POST http://localhost:8001/api/ai/ -H "Content-Type: application/json" -d "{\"action\":\"compile\",\"selector\":{\"project\":\"pos\",\"component\":\"$comp\"}}")
    L=$(echo "$R" | python3 -c "import sys,json;print(json.load(sys.stdin).get('lines',0))" 2>/dev/null)
    check "Compile $comp (${L}L)" $([ "$L" -gt 0 ] && echo 0 || echo 1)
done

echo ""
echo "═══ 7. Database State ═══"
python3 -c "
import asyncio, asyncpg
from config import DATABASE_URL, QDML_SCHEMA
async def check():
    pool = await asyncpg.create_pool(DATABASE_URL)
    schemas = await pool.fetchval(f'SELECT COUNT(*) FROM {QDML_SCHEMA}.schema_registry')
    print(f'  Schema registry: {schemas} tables')
    kits = await pool.fetchval(f'SELECT COUNT(*) FROM {QDML_SCHEMA}.kit_registry')
    print(f'  Kit registry: {kits} kits')
    pipes = await pool.fetchval(f'SELECT COUNT(*) FROM {QDML_SCHEMA}.pipelines')
    print(f'  Pipelines: {pipes}')
    apps = await pool.fetchval(f'SELECT COUNT(*) FROM {QDML_SCHEMA}.app_instances')
    print(f'  App instances: {apps}')
    await pool.close()
asyncio.run(check())
" 2>&1

# Final stats
echo ""
echo "═══ Final System Stats ═══"
curl -s http://localhost:8001/health | python3 -c "
import sys,json
s = json.load(sys.stdin)['stats']
print(f'  Projects:   {s[\"projects\"]}')
print(f'  Modules:    {s[\"modules\"]}')
print(f'  Components: {s[\"components\"]}')
print(f'  Bulks:      {s[\"bulks\"]}')
print(f'  Lines:      {s[\"total_lines\"]:,}')
print(f'  DB:         {s[\"db_size_mb\"]} MB')
" 2>/dev/null

# Cleanup
kill $API_PID 2>/dev/null
wait $API_PID 2>/dev/null

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Results: ✅ ${PASS} passed | ❌ ${FAIL} failed"
echo "════════════════════════════════════════════════════════════════"

if [ $FAIL -eq 0 ]; then
    echo "  🎉 ALL TESTS PASS!"
else
    echo "  ⚠️  Some tests failed. Check logs: /tmp/qdml-test.log"
fi
