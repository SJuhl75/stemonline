# 🎧 Traktor Stemgen Pipeline

Lädt Audio von YouTube herunter, trennt es in 4 Stems und erzeugt eine
Native-Instruments `.stem.m4a`-Datei, die automatisch zur MagentaCloud
hochgeladen wird.

## Pipeline

1. **yt-dlp** lädt das Audio als FLAC (44,1 kHz / Stereo)
2. **Stemgen** trennt den Track und muxt die `.stem.m4a`
3. **rclone** lädt das Ergebnis zu MagentaCloud hoch

## Separation-Modelle

| Modell | Qualität | Hinweis |
|---|---|---|
| BS RoFormer | höher | empfohlen, langsamer |
| Demucs | gut | schneller, bewährt |

## Ports

| Port | Protokoll | Zweck |
|---|---|---|
| 7860 | HTTP | Gradio WebUI |

## Umgebungsvariablen

| Variable | Pflicht | Beschreibung |
|---|---|---|
| `MAGENTA_USER` | Ja | MagentaCloud-Benutzername (E-Mail) |
| `MAGENTA_PASS_OBFUSCATED` | Ja | rclone-obfusciertes Passwort |
| `DEV_RELOAD` | Nein | `1` = Auto-Reload bei Änderung an `app.py` |

> **Hinweis:** Das rclone-Passwort erhältst du mit
> `rclone obscure DEIN_PASSWORT` auf einem beliebigen Rechner mit rclone.

## WebUI nutzen

1. Über den Connect-Button das WebUI öffnen.
2. YouTube-Link einfügen.
3. Separation-Modell wählen.
4. Zielordner in der MagentaCloud angeben (Standard: `TraktorStems`).
5. Pipeline starten.

## Code zur Laufzeit ändern (WebSSH)

Die Anwendung liegt unter `/workspace/code/app.py` und kann über die
WebSSH-Konsole direkt bearbeitet werden:

```bash
nano /workspace/code/app.py
```

Danach die Anwendung neu starten:

```bash
pkill -f "app.py" && bash /start.sh
```

Mit gesetzter Umgebungsvariable `DEV_RELOAD=1` wird `app.py` bei jeder
Änderung automatisch neu geladen.

## Modell-Cache

Die Separations-Modelle werden unter `/workspace/cache/torch` gespeichert.
Liegt `/workspace` auf einem persistenten Volume, werden die Modelle nur
einmal heruntergeladen.

## Nach dem ersten Start prüfen

```bash
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

Erwartet: `True` und die GPU-Auslastung steigt während der Trennung.