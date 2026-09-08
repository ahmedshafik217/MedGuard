#!/bin/sh
set -e

# Fail loudly rather than silently deploying with a guessable secret --
# these two placeholders are the checked-in dev defaults (see
# app/config.py / .env.example) and must never end up on anything
# reachable on the public internet.
if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "dev-key-change-me" ]; then
    echo "ERROR: SECRET_KEY is not set (or is still the dev placeholder)." >&2
    echo "Set a real SECRET_KEY environment variable before deploying -- generate one with:" >&2
    echo "  python3 -c \"import secrets; print(secrets.token_hex(32))\"" >&2
    exit 1
fi

if [ -z "$OWNER_PASSWORD" ] || [ "$OWNER_PASSWORD" = "change-this-password" ]; then
    echo "ERROR: OWNER_PASSWORD is not set (or is still the placeholder)." >&2
    echo "Set a real OWNER_PASSWORD environment variable before deploying." >&2
    exit 1
fi

# Create tables + seed reference antibiotics + the first owner account if
# they don't already exist yet (seed.py is idempotent -- see its own
# docstring). Safe, and necessary, to run this on every container start:
# most free hosting tiers wipe local files on every restart, so the app
# has to be able to fully re-initialize itself every time it boots rather
# than relying on a one-time manual `python3 seed.py` step.
python3 seed.py

exec gunicorn -w 2 -b "0.0.0.0:${PORT:-8000}" --access-logfile - --error-logfile - run:app
