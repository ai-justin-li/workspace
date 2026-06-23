#!/bin/bash
source .venv/bin/activate

echo "Starting SoCo Spa Mobile API on port 8000..."
echo "→ This Mac (Safari):   http://localhost:8000/mobile/"

# Try common Mac Wi-Fi / Ethernet interfaces
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || ipconfig getifaddr en2 2>/dev/null)
if [ -n "$IP" ]; then
  echo "→ Phone on same Wi-Fi: http://$IP:8000/mobile/"
else
  echo "→ Phone on same Wi-Fi: http://YOUR-MAC-IP:8000/mobile/   (run: ipconfig getifaddr en0)"
fi

echo ""
uvicorn mobile_api:app --reload --host 0.0.0.0 --port 8000
