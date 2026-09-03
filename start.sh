#!/bin/bash 
echo "=== Konfiguriere MagentaCloud WebDAV Verbindung ==="

# rclone Config-Ordner erstellen
mkdir -p ~/.config/rclone/

# Erstellt die verschlüsselte Verbindung on-the-fly beim Start des Pods
cat <<EOF > ~/.config/rclone/rclone.conf
[magentacloud]
type = webdav
url = https://magentacloud.de
user = $MAGENTA_USER
pass = $MAGENTA_PASS_OBFUSCATED
EOF

echo "=== Starte Custom DJ-Stem-Pipeline WebUI ==="
python /workspace/app.py
