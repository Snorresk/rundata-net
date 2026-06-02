#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate
export DJANGO_READ_DOT_ENV_FILE=True
python manage.py runserver 0.0.0.0:8000 --noreload
