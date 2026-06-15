#!/usr/bin/env bash
# ─────────────────────────────────────────────────
# Inthon IDE Launcher — Linux / macOS
# ─────────────────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "  ██████████████████████████████████████"
echo "  ██  INTHON IDE  —  Agent-Level Code  ██"
echo "  ██████████████████████████████████████"
echo ""

# Kill any existing server on 7474
lsof -ti tcp:7474 | xargs kill -9 2>/dev/null || true

echo "  [*] Starting Inthon compiler server..."
python3 "$SCRIPT_DIR/inthon_server.py" &
SERVER_PID=$!

echo "  [*] Waiting for server to initialize..."
sleep 2

# Verify server
if curl -s http://localhost:7474/health > /dev/null 2>&1; then
  echo "  [OK] Server running on http://localhost:7474 (PID $SERVER_PID)"
else
  echo "  [?] Server may still be starting..."
fi

echo "  [*] Opening Inthon IDE..."

# Open browser based on OS
if [[ "$OSTYPE" == "darwin"* ]]; then
  open "$SCRIPT_DIR/inthon-ide.html"
elif command -v xdg-open &>/dev/null; then
  xdg-open "$SCRIPT_DIR/inthon-ide.html"
elif command -v firefox &>/dev/null; then
  firefox "$SCRIPT_DIR/inthon-ide.html" &
elif command -v chromium &>/dev/null; then
  chromium "$SCRIPT_DIR/inthon-ide.html" &
else
  echo "  [!] Please open inthon-ide.html manually in your browser"
fi

echo ""
echo "  IDE launched! Press Ctrl+C to stop the server."
echo ""

# Wait for Ctrl+C and cleanup
trap "echo '  Stopping server...'; kill $SERVER_PID 2>/dev/null; exit 0" INT TERM
wait $SERVER_PID
