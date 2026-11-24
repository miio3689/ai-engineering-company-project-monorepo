#!/bin/sh
# cron starts every job with an almost empty environment. Save the container
# environment (DATABASE_URL, TARGET_DATE...) quoted, so the job can load it.
set -eu
export -p > /app/.cron-env
chmod 600 /app/.cron-env
exec "$@"
