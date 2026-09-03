#!/usr/bin/env bash

set -euo pipefail

APP_CODE_DIR="${APP_CODE_DIR:-/workspace/code}"
DEFAULT_CODE_DIR="/opt/app-defaults"
APP_FILE="${APP_CODE_DIR}/app.py"
RCLONE_CONFIG_FILE="/workspace/rclone/rclone.conf"

echo "=== Starte Stemgen-Pipeline ==="

# Runtime-Codeverzeichnis erstellen
mkdir -p "${APP_CODE_DIR}"
mkdir -p "/workspace/jobs"
mkdir -p "/workspace/cache/torch"
mkdir -p "/workspace/rclone"

# Standarddateien nur kopieren, wenn im Runtime-Verzeichnis
# noch keine eigene Version vorhanden ist.
#
# Dadurch bleiben Änderungen über WebSSH erhalten.
if [[ ! -f "${APP_FILE}" ]]; then
    echo "Keine eigene app.py gefunden."
    echo "Kopiere Standardversion nach ${APP_FILE}"
    cp "${DEFAULT_CODE_DIR}/app.py" "${APP_FILE}"
fi

# Rclone-Konfiguration erzeugen
echo "=== Konfiguriere MagentaCloud-WebDAV-Verbindung ==="

if [[ -z "${MAGENTA_USER:-}" ]]; then
    echo "WARNUNG: MAGENTA_USER ist nicht gesetzt."
else
    if [[ -z "${MAGENTA_PASS_OBFUSCATED:-}" ]]; then
        echo "WARNUNG: MAGENTA_PASS_OBFUSCATED ist nicht gesetzt."
    else
        cat > "${RCLONE_CONFIG_FILE}" <<EOF
[magentacloud]
type = webdav
url = https://magentacloud.de
user = ${MAGENTA_USER}
pass = ${MAGENTA_PASS_OBFUSCATED}
EOF

        chmod 600 "${RCLONE_CONFIG_FILE}"
        export RCLONE_CONFIG="${RCLONE_CONFIG_FILE}"
    fi
fi

# Diagnoseinformationen
echo "=== Installierte Versionen ==="

echo "Python:"
python --version

echo "PyTorch:"
python -c "import torch; print(torch.__version__); print('CUDA verfügbar:', torch.cuda.is_available())"

echo "Deno:"
deno --version

echo "yt-dlp:"
yt-dlp --version

echo "App-Datei:"
ls -lh "${APP_FILE}"

echo "App-Codeverzeichnis:"
ls -la "${APP_CODE_DIR}"

echo "=== Starte Gradio-Anwendung ==="

# DEV_RELOAD=1 kann in Runpod als Umgebungsvariable gesetzt werden.
#
# Dann wird die Python-Anwendung automatisch neu gestartet,
# sobald app.py im Runtime-Codeverzeichnis geändert wird.
if [[ "${DEV_RELOAD:-0}" == "1" ]]; then
    echo "Automatischer Reload ist AKTIV."
    echo "Änderungen an app.py werden automatisch übernommen."

    exec python -m watchfiles \
        --filter python \
        "python ${APP_FILE}" \
        "${APP_CODE_DIR}"
else
    echo "Automatischer Reload ist deaktiviert."
    echo "Manueller Neustart erforderlich."

    exec python "${APP_FILE}"
fi