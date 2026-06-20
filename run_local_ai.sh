#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate
export DJANGO_READ_DOT_ENV_FILE=True
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1${LAN_IP:+,$LAN_IP}}"
PORT="${PORT:-8000}"
python manage.py runserver "0.0.0.0:${PORT}" --noreload
