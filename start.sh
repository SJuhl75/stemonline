#!/usr/bin/env bash

set -euo pipefail

echo "=== Konfiguriere MagentaCloud-WebDAV-Verbindung ==="

if [[ -z "${MAGENTA_USER:-}" ]]; then
    echo "Fehler: MAGENTA_USER ist nicht gesetzt."
    exit 1
fi

if [[ -z "${MAGENTA_PASS_OBFUSCATED:-}" ]]; then
    echo "Fehler: MAGENTA_PASS_OBFUSCATED ist nicht gesetzt."
    exit 1
fi

export RCLONE_CONFIG=/workspace/rclone/rclone.conf

mkdir -p "$(dirname "$RCLONE_CONFIG")"
mkdir -p /workspace/cache/torch

cat > "$RCLONE_CONFIG" <<EOF
[magentacloud]
type = webdav
url = https://magentacloud.de
user = ${MAGENTA_USER}
pass = ${MAGENTA_PASS_OBFUSCATED}
EOF

chmod 600 "$RCLONE_CONFIG"

echo "=== Prüfe installierte Komponenten ==="

command -v yt-dlp
command -v deno
command -v rclone

echo "yt-dlp-Version:"
yt-dlp --version

echo "Deno-Version:"
deno --version

echo "=== Starte Custom DJ-Stem-Pipeline-WebUI ==="

exec python /workspace/app.py