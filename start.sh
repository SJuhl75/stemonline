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

# POT Provider starten
echo "=== Starte Rust POT Provider (bgutil-pot) ==="
if command -v bgutil-pot &> /dev/null; then
    bgutil-pot server --host 0.0.0.0 --port 4416 &
    POT_PID=$!
    echo "POT Provider gestartet mit PID ${POT_PID} auf Port 4416."

    sleep 2

    # Healthcheck mit wget (curl ist nicht mehr im Image!)
    if command -v curl &> /dev/null; then
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4416/ping)
    elif command -v wget &> /dev/null; then
        STATUS=$(wget -q -O - http://127.0.0.1:4416/ping >/dev/null 2>&1 && echo "200" || echo "000")
    else
        STATUS="000"
    fi

    if [[ "${STATUS}" == "200" ]]; then
        echo "POT Provider Healthcheck erfolgreich."
    else
        echo "WARNUNG: POT Provider Healthcheck fehlgeschlagen (Status: ${STATUS})."
    fi
else
    echo "WARNUNG: bgutil-pot nicht gefunden."
fi

# WICHTIG: Plugin für yt-dlp korrekt verknüpfen!
# yt-dlp sucht Plugins in ~/.config/yt-dlp/plugins
mkdir -p /root/.config/yt-dlp/plugins
if [[ -d /root/yt-dlp-plugins ]]; then
    ln -sfn /root/yt-dlp-plugins/* /root/.config/yt-dlp/plugins/ 2>/dev/null || true
    echo "yt-dlp Plugin-Verzeichnis verknüpft."
fi

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