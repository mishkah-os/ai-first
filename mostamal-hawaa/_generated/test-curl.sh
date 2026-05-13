#!/bin/bash
# Auto-generated tests for mostamal-hawaa
echo "Testing mostamal-hawaa on port 9001..."

# Health check
STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:9001/health 2>/dev/null || echo "000")
if [ "$STATUS" = "200" ]; then echo "✅ Health: OK"; else echo "❌ Health: $STATUS"; fi

# API test
STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:9001/ 2>/dev/null || echo "000")
if [ "$STATUS" = "200" ]; then echo "✅ Root: OK"; else echo "❌ Root: $STATUS"; fi

echo "Done."
