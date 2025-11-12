#!/bin/bash
# Smoke test script for Archive Detective backend
set -e

BASE_URL="http://127.0.0.1:8000"
TMP_DIR="/tmp"
JOB_ID=""

echo "🧪 Archive Detective Smoke Tests"
echo "================================"
echo ""

# Function to check if server is running
check_server() {
    if ! curl -s -f "$BASE_URL/ready" > /dev/null 2>&1; then
        echo "❌ Server not running on $BASE_URL"
        echo "   Please start the server with: ./run.sh"
        exit 1
    fi
    echo "✅ Server is running"
}

# Function to kill existing server
kill_server() {
    echo "🛑 Stopping any existing server on port 8000..."
    pkill -f "uvicorn app.main:app" || true
    sleep 2
}

# Function to start server in background
start_server() {
    echo "🚀 Starting server..."
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi
    uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/troveing_server.log 2>&1 &
    SERVER_PID=$!
    echo "   Server PID: $SERVER_PID"
    
    # Wait for server to be ready
    echo "⏳ Waiting for server to start..."
    for i in {1..30}; do
        if curl -s -f "$BASE_URL/ready" > /dev/null 2>&1; then
            echo "✅ Server is ready"
            return 0
        fi
        sleep 1
    done
    echo "❌ Server failed to start"
    cat /tmp/troveing_server.log
    exit 1
}

# Cleanup function
cleanup() {
    if [ ! -z "$SERVER_PID" ]; then
        echo ""
        echo "🛑 Stopping server (PID: $SERVER_PID)..."
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Main test flow
echo "Step 1: Kill & start server"
kill_server
start_server
echo ""

echo "Step 2: Start batch research job"
RESPONSE=$(curl -s -X POST "$BASE_URL/api/research/start-batch" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "Iluka mineral sands rutile zircon (Clarence River, NSW)",
        "years_from": 1945,
        "years_to": 1980,
        "max_pages": 12,
        "page_size": 100,
        "state": "New South Wales"
    }')

JOB_ID=$(echo "$RESPONSE" | jq -r '.job_id // empty')
if [ -z "$JOB_ID" ]; then
    echo "❌ Failed to start batch job"
    echo "Response: $RESPONSE"
    exit 1
fi
echo "✅ Job started: $JOB_ID"
echo ""

echo "Step 3: Poll job status until done"
MAX_WAIT=300  # 5 minutes max
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS_RESPONSE=$(curl -s "$BASE_URL/api/research/job/$JOB_ID")
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status // empty')
    
    if [ "$STATUS" = "done" ]; then
        echo "✅ Job completed"
        break
    elif [ "$STATUS" = "error" ]; then
        ERROR=$(echo "$STATUS_RESPONSE" | jq -r '.error // "Unknown error"')
        echo "❌ Job failed: $ERROR"
        exit 1
    fi
    
    PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.progress // 0')
    echo "   Status: $STATUS, Progress: $(printf "%.0f" $(echo "$PROGRESS * 100" | bc))%"
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if [ "$STATUS" != "done" ]; then
    echo "❌ Job did not complete within timeout"
    exit 1
fi
echo ""

echo "Step 4: Fetch report, markdown, and evidence"
curl -s "$BASE_URL/api/research/job/$JOB_ID/report" > "$TMP_DIR/report.json"
curl -s "$BASE_URL/api/research/job/$JOB_ID/markdown" > "$TMP_DIR/report.md"
curl -s "$BASE_URL/api/research/job/$JOB_ID/evidence" > "$TMP_DIR/evidence.jsonl"

if [ ! -s "$TMP_DIR/report.json" ]; then
    echo "❌ Failed to fetch report"
    exit 1
fi
echo "✅ Fetched outputs to /tmp/"
echo ""

echo "Step 5: Run validator"
if ! python3 validate_report.py "$TMP_DIR/report.json"; then
    echo "❌ Validator failed"
    exit 1
fi
echo "✅ Validator passed"
echo ""

echo "Step 6: JQ assertions"
SOURCES_COUNT=$(jq '.sources | length' "$TMP_DIR/report.json")
if [ "$SOURCES_COUNT" -lt 8 ]; then
    echo "❌ Expected at least 8 sources, got $SOURCES_COUNT"
    exit 1
fi
echo "✅ Sources count: $SOURCES_COUNT"

FINDINGS_COUNT=$(jq '.key_findings | length' "$TMP_DIR/report.json")
EVIDENCE_OK=true
for i in $(seq 0 $((FINDINGS_COUNT - 1))); do
    EVIDENCE_LEN=$(jq ".key_findings[$i].evidence | length" "$TMP_DIR/report.json")
    if [ "$EVIDENCE_LEN" -eq 0 ]; then
        echo "❌ Finding #$((i+1)) has no evidence"
        EVIDENCE_OK=false
    fi
done
if [ "$EVIDENCE_OK" = false ]; then
    exit 1
fi
echo "✅ All findings have evidence"

# Check evidence quote length
QUOTE_LEN_OK=true
for i in $(seq 0 $((FINDINGS_COUNT - 1))); do
    EVIDENCE_COUNT=$(jq ".key_findings[$i].evidence | length" "$TMP_DIR/report.json")
    for j in $(seq 0 $((EVIDENCE_COUNT - 1))); do
        QUOTE=$(jq -r ".key_findings[$i].evidence[$j]" "$TMP_DIR/report.json")
        QUOTE_LEN=${#QUOTE}
        if [ "$QUOTE_LEN" -gt 240 ]; then
            echo "❌ Evidence quote exceeds 240 chars: $QUOTE_LEN"
            QUOTE_LEN_OK=false
        fi
    done
done
if [ "$QUOTE_LEN_OK" = false ]; then
    exit 1
fi
echo "✅ All evidence quotes ≤240 chars"

# Check top-5 relevance
TOP5_REL=$(jq '[.sources[0:5][].relevance] | min' "$TMP_DIR/report.json")
if (( $(echo "$TOP5_REL <= 0" | bc -l) )); then
    echo "❌ Top-5 relevance should be > 0, got $TOP5_REL"
    exit 1
fi
echo "✅ Top-5 relevance > 0 (min: $TOP5_REL)"
echo ""

echo "Step 7: Test dashboard"
DASHBOARD_JSON=$(curl -s "$BASE_URL/api/dashboard")
if [ -z "$DASHBOARD_JSON" ]; then
    echo "❌ Dashboard JSON endpoint failed"
    exit 1
fi
echo "✅ Dashboard JSON OK"

DASHBOARD_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/dashboard")
if [ "$DASHBOARD_RESPONSE" = "200" ]; then
    echo "✅ Dashboard HTML OK"
else
    echo "⚠️  Dashboard HTML check: HTTP $DASHBOARD_RESPONSE (may be redirect or different status)"
    # Don't fail on this - dashboard might redirect or have different status
fi
echo ""

echo "================================"
echo "✅ ALL TESTS PASSED"
echo "================================"
echo ""
echo "Outputs:"
echo "  - Report JSON: $TMP_DIR/report.json"
echo "  - Report Markdown: $TMP_DIR/report.md"
echo "  - Evidence JSONL: $TMP_DIR/evidence.jsonl"
echo ""

