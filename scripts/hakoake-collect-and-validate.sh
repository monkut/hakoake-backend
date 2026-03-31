#!/usr/bin/env bash
# hakoake-collect-and-validate.sh — Collect schedules and validate social links.
# Runs every Tuesday; exits early if not the 1st or 3rd Tuesday of the month.
# 1. Collects performance schedules
# 2. Validates YouTube social links
set -euo pipefail

export PATH="/home/monkut/.local/bin:$PATH"

HAKOAKE_DIR="$HOME/projects/hakoake-backend/malcom"
LOG_DIR="$HOME/projects/hakoake-backend/logs"
mkdir -p "$LOG_DIR"

TODAY=$(TZ=Asia/Tokyo date +%Y-%m-%d)
LOGFILE="$LOG_DIR/hakoake-collect-and-validate-${TODAY}.log"

# Tee all output (stdout + stderr) to a dated log file
exec > >(tee "$LOGFILE") 2>&1

# Check if today is the 1st or 3rd Tuesday of the month (in JST)
DAY=$(TZ=Asia/Tokyo date +%-d)
if [ "$DAY" -ge 1 ] && [ "$DAY" -le 7 ]; then
    echo "1st Tuesday — proceeding."
elif [ "$DAY" -ge 15 ] && [ "$DAY" -le 21 ]; then
    echo "3rd Tuesday — proceeding."
else
    echo "Not the 1st or 3rd Tuesday (day=${DAY}), skipping."
    exit 0
fi

cd "$HAKOAKE_DIR"

echo "Collecting schedules..."
uv run python manage.py collect_schedules

echo "Validating YouTube social links..."
uv run python manage.py validate_youtube_sociallinks

echo "Done."
