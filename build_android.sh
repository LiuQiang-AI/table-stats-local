#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f "buildozer.spec" ]]; then
  if [[ -f "buildozer.spec.example" ]]; then
    cp "buildozer.spec.example" "buildozer.spec"
    echo "[build] Copied buildozer.spec.example -> buildozer.spec"
  else
    echo "[build] Missing buildozer.spec.example" >&2
    exit 1
  fi
fi

python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install buildozer==1.5.0

buildozer -v android debug

echo "[build] Done. Check ./bin/ for APK."

