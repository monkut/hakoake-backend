#!/usr/bin/env bash
# hakoake-gen-video.sh — Generate weekly playlist video for hakoake.
# Runs every Monday at 22:00 JST.
# 1. Creates the weekly playlist for the current Monday
# 2. Looks up the created playlist's DB id
# 3. Generates the playlist video
# 4. Posts the Instagram carousel announcement
set -euo pipefail

export PATH="/home/monkut/.local/bin:$PATH"

# Load environment variables from .env
ENV_FILE="$HOME/projects/hakoake-backend/.env"
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
fi

HAKOAKE_DIR="$HOME/projects/hakoake-backend/malcom"
LOG_DIR="$HOME/projects/hakoake-backend/logs"
mkdir -p "$LOG_DIR"

# Get Monday date in JST (the day this script runs)
MONDAY=$(TZ=Asia/Tokyo date +%Y-%m-%d)
LOGFILE="$LOG_DIR/hakoake-gen-video-${MONDAY}.log"

# Tee all output (stdout + stderr) to a dated log file
exec > >(tee "$LOGFILE") 2>&1

# Pre-flight: verify Ollama service is reachable before proceeding
echo "Checking Ollama service availability..."
if ! curl -sf http://127.0.0.1:11434 > /dev/null; then
    echo "ERROR: Ollama is not reachable at http://127.0.0.1:11434. Ensure ollama.service is running (systemctl start ollama)." >&2
    exit 1
fi
echo "Ollama is reachable."

# Pre-flight: ensure mistral-small model is pulled (matches settings.PLAYLIST_INTRO_TEXT_GENERATION_MODEL)
echo "Ensuring mistral-small model is available..."
ollama pull mistral-small

echo "Creating weekly playlist for week starting ${MONDAY}..."
cd "$HAKOAKE_DIR"
uv run python manage.py create_weekly_playlist "$MONDAY"

echo "Looking up playlist DB id for ${MONDAY}..."
# grep '^{' filters out any Django startup messages (e.g. "N objects imported automatically")
# that may be written to stdout before the JSON output
playlist_db_id=$(uv run python manage.py list_weekly_playlist "$MONDAY" --json | grep '^{' | jq -r '.id')

echo "Generating weekly playlist video for playlist id=${playlist_db_id}..."
uv run python manage.py generate_weekly_playlist_video "$playlist_db_id"

echo "Posting weekly playlist announcement to Instagram..."
uv run python manage.py post_weekly_playlist --playlist-id="$playlist_db_id"

echo "Done."
