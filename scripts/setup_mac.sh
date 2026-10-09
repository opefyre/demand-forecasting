#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "DemandLab — macOS setup"
echo

find_python() {
  for candidate in python3.12 python3.13 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      local version
      version="$($candidate -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
      case "$version" in
        3.10|3.11|3.12|3.13)
          command -v "$candidate"
          return 0
          ;;
      esac
    fi
  done
  return 1
}

PYTHON="$(find_python || true)"
if [[ -z "$PYTHON" ]]; then
  echo "Python 3.10–3.13 is required."
  echo "Recommended: brew install python@3.12"
  exit 1
fi

echo "Using $($PYTHON --version) at $PYTHON"

# LightGBM uses OpenMP on macOS. Install it when Homebrew is available,
# but do not make the whole POC fail if this optional model cannot be installed.
if command -v brew >/dev/null 2>&1; then
  if ! brew list libomp >/dev/null 2>&1; then
    echo "Installing libomp for optional LightGBM support..."
    brew install libomp
  fi
fi

echo "Rebuilding the local virtual environment..."
rm -rf .venv
"$PYTHON" -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

if python -m pip install "lightgbm>=4.6,<5"; then
  echo "LightGBM installed."
else
  echo "LightGBM could not be installed; the app will continue with the remaining statistical + ML models."
fi

echo
echo "Checking installation..."
python - <<'PY'
import fastapi, uvicorn, pandas, numpy, sklearn, openpyxl, statsmodels, statsforecast, huey, pint
print("  FastAPI:", fastapi.__version__)
print("  pandas:", pandas.__version__)
print("  NumPy:", numpy.__version__)
print("  scikit-learn:", sklearn.__version__)
print("  statsmodels:", statsmodels.__version__)
print("  StatsForecast:", statsforecast.__version__)
print("  Huey:", huey.__version__)
try:
    import lightgbm
    print("  LightGBM:", lightgbm.__version__)
except Exception as exc:
    print("  LightGBM: unavailable (optional)", exc)
print("  Engine imports: OK")
PY

echo
echo "Running forecasting smoke test..."
python scripts/smoke_test.py

echo
echo "Setup complete."
echo "Start the app with: ./scripts/start_mac.sh"
