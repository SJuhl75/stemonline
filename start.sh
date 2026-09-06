#!/usr/bin/env bash

set -euo pipefail

APP_CODE_DIR="${APP_CODE_DIR:-/workspace/code}"
DEFAULT_CODE_DIR="/opt/app-defaults"
APP_FILE="${APP_CODE_DIR}/app.py"
RCLONE_CONFIG_FILE="/workspace/rclone/rclone.conf"
MAGENTA_WEBDAV_URL="${MAGENTA_WEBDAV_URL:-https://magentacloud.de/remote.php/webdav/}"

echo "=== Starte Stemgen-Pipeline ==="

mkdir -p "${APP_CODE_DIR}"
mkdir -p "/workspace/jobs"
mkdir -p "/workspace/cache/torch"
mkdir -p "/workspace/rclone"

if [[ ! -f "${APP_FILE}" ]]; then
    cp "${DEFAULT_CODE_DIR}/app.py" "${APP_FILE}"
fi

# Rclone Konfiguration
if [[ -z "${MAGENTA_USER:-}" ]]; then
    echo "WARNUNG: MAGENTA_USER ist nicht gesetzt."
else
    if [[ -z "${MAGENTA_PASS_OBFUSCATED:-}" ]]; then
        echo "WARNUNG: MAGENTA_PASS_OBFUSCATED ist nicht gesetzt."
    else
        cat > "${RCLONE_CONFIG_FILE}" <<EOF
[magentacloud]
type = webdav
url = ${MAGENTA_WEBDAV_URL}
vendor = other
user = ${MAGENTA_USER}
pass = ${MAGENTA_PASS_OBFUSCATED}
EOF
        chmod 600 "${RCLONE_CONFIG_FILE}"
        export RCLONE_CONFIG="${RCLONE_CONFIG_FILE}"
    fi
fi

# --- POT Provider Setup ---
echo "=== Starte Rust POT Provider (bgutil-pot) ==="

# 1. curl installieren (falls es im Image fehlt)
if ! command -v curl &> /dev/null; then
    echo "Installiere curl..."
    apt-get update -qq && apt-get install -y -qq curl
fi

# 2. Server starten
if command -v bgutil-pot &> /dev/null; then
    bgutil-pot server --host 0.0.0.0 --port 4416 &
    POT_PID=$!
    echo "POT Provider gestartet mit PID ${POT_PID} auf Port 4416."

    sleep 2

    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4416/ping)
    if [[ "${STATUS}" == "200" ]]; then
        echo "POT Provider Healthcheck erfolgreich."
    else
        echo "WARNUNG: POT Provider Healthcheck fehlgeschlagen (Status: ${STATUS})."
    fi
else
    echo "WARNUNG: bgutil-pot nicht gefunden."
fi

# --- YouTube IP-Blacklist Check ---
echo "=== Prüfe YouTube IP-Status ==="

# Testvideo (harmlos, von YouTube selbst: "Me at the zoo")
TEST_URL="https://www.youtube.com/watch?v=jNQXAC9IVRw"
# Client für den Test: mweb ist oft toleranter als tv
TEST_CLIENT="mweb"

# Führe einen Test aus, um zu sehen, ob Metadaten abrufbar sind (ohne Download)
if yt-dlp --no-playlist --skip-download --no-warnings --retries 0 \
    --extractor-args "youtube:player_client=${TEST_CLIENT}" \
    "$TEST_URL" > /dev/null 2>&1; then
    echo "✅ YouTube-Status: IP scheint derzeit OK zu sein (Client: ${TEST_CLIENT})."
else
    echo "❌ YouTube-Status: IP blockiert oder extrem riskant (Client: ${TEST_CLIENT})."
    echo "   Bitte beachte: Downloads im WebUI könnten fehlschlagen."
    echo "   Lösung: Nutze einen Residential Proxy oder wechsle die Region."
fi

# --- Ende Setup ---

echo "=== Installierte Versionen ==="
python --version
python -c "import torch; print(torch.__version__); print('CUDA:', torch.cuda.is_available())"
deno --version
yt-dlp --version

echo "=== Starte Gradio-Anwendung ==="
if [[ "${DEV_RELOAD:-0}" == "1" ]]; then
    exec python -m watchfiles --filter python "python ${APP_FILE}" "${APP_CODE_DIR}"
else
    exec python "${APP_FILE}"
fi