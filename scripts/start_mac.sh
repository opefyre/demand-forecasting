#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo "The local environment is missing or incomplete."
  echo "Run ./scripts/setup_mac.sh first."
  exit 1
fi
source .venv/bin/activate
python - <<'PY'
try:
    import fastapi, uvicorn, sklearn, statsforecast, huey, sqlalchemy, pint
except Exception as exc:
    raise SystemExit("The setup is incomplete: " + str(exc) + "\nRun ./scripts/setup_mac.sh again.")
PY
(sleep 1.2 && open "http://127.0.0.1:8010") >/dev/null 2>&1 &
python run.py
