#!/bin/sh
set -eu

cd /app/website
npm run dev -- --host 0.0.0.0 --port 5174 &
website_pid=$!

cd /app/backoffice
npm run dev -- --hostname 0.0.0.0 --port 3000 &
backoffice_pid=$!

trap 'kill "$website_pid" "$backoffice_pid" 2>/dev/null || true' HUP INT TERM
wait