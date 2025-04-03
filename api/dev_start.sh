#! /usr/bin/env sh

#. /app/prestart.sh

poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload