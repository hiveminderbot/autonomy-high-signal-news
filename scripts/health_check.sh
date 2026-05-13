#!/usr/bin/env bash
# health_check.sh — Validate high-signal-news GitHub Pages deployment
# Usage: ./scripts/health_check.sh [URL]
# Exit 0 if healthy, 1 if unhealthy

set -euo pipefail

URL="${1:-https://hiveminderbot.github.io/autonomy-high-signal-news/}"
TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

echo "=== High-Signal News Dashboard Health Check ==="
echo "Target URL: $URL"
echo ""

# 1. HTTP status check
echo "[1/4] Checking HTTP status..."
HTTP_CODE=$(curl -sL -o "$TMPFILE" -w "%{http_code}" "$URL" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    echo "  FAIL: HTTP $HTTP_CODE (expected 200)"
    echo "  Response preview:"
    head -3 "$TMPFILE" || true
    echo ""
    echo "DIAGNOSIS: GitHub Pages is not enabled for this repository."
    echo "  - If repo is PRIVATE: GitHub Pages requires Pro/Team/Enterprise plan."
    echo "  - If repo is PUBLIC: enable Pages in Settings → Pages → Source = main /docs."
    exit 1
fi
echo "  PASS: HTTP 200"

# 2. Title check — accept any briefing title (Daily Briefing or Morning Briefing)
echo "[2/4] Checking page title..."
TITLE=$(grep -oP '(?<=<title>).*?(?=</title>)' "$TMPFILE" || echo "NOT FOUND")
if echo "$TITLE" | grep -qi 'briefing'; then
    echo "  PASS: Briefing title found: $TITLE"
else
    echo "  FAIL: Expected briefing title, got: $TITLE"
    exit 1
fi

# 3. Content check — look for article links as evidence of real content
echo "[3/4] Checking article links..."
LINK_COUNT=$(grep -oP 'href="https?://[^"]+"' "$TMPFILE" | wc -l)
if [ "$LINK_COUNT" -gt 10 ]; then
    echo "  PASS: $LINK_COUNT external links found"
else
    echo "  FAIL: Only $LINK_COUNT external links found (expected >10)"
    exit 1
fi

# 4. Story/article count check
echo "[4/4] Checking story count..."
if grep -q 'Stories:' "$TMPFILE" || grep -q 'stories' "$TMPFILE"; then
    STORIES=$(grep -oiP '\d+\s+stories' "$TMPFILE" | head -1 || echo "present")
    echo "  PASS: Story count marker present ($STORIES)"
else
    echo "  WARN: No explicit story count marker, but links present"
fi

echo ""
echo "=== ALL CHECKS PASSED ==="
echo "Dashboard is live and serving real content."
exit 0
