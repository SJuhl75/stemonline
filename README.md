# 🎧 Traktor & Denon (Engine DJ) Stemgen Pipeline

Lädt Audio von YouTube herunter, trennt es in 4 Stems und erzeugt sowohl eine 
Native-Instruments `.stem.m4a`-Datei als auch eine Engine DJ-kompatible `.stems`-Datei 
(im `.ddj`-Container). Das Ergebnis wird automatisch zur MagentaCloud hochgeladen.

## Pipeline

1. **yt-dlp** lädt das Audio als FLAC (44,1 kHz / Stereo) inklusive Thumbnail
2. **Audio-Normalisierung** (optional) bringt den Pegel auf ein einheitliches Level und bettet Metadaten sowie Artwork ein
3. **Stemgen** trennt den Track in 4 Stems und muxt die `.stem.m4a`
4. **Engine DJ Encoding** wandelt die 4 Stems in eine native (verschlüsselte) `.stems`-Datei um
5. **Paketierung** verpackt alles in einen `.ddj`-Container (für DJ-Systeme)
6. **rclone** lädt das Ergebnis zu MagentaCloud hoch

## Performance
Aus einem knapp 7 minütigen Track lassen sich mittels des RoFormer-Modell und einer RTX 3080 in knapp sechs Minuten hochwertige Stems erzeugen, die auf dem Denon DJ PRIME 2 wiedergegeben werden können. Hierzu ist ein kleines Import-Skript notwendig, dass die Stems an die richtigen Stelle kopiert und die erforderlichen Datensätze in der Engine Library erzeugt.
Alternativ kann dieses Repo mit Runpod verwendet werden; als Docker-Image ist hierzu ghcr.io/sjuhl75/stemonline:<tag>
anzugeben; für <tag> entweder "latest" oder das neuste Tag ohne das vorangestellte "build-" verwenden.

## Eingebundene Projekte & Danksagungen

Dieses Projekt wäre ohne die fantastische Arbeit der folgenden Open-Source-Repositories nicht möglich:

### [Stemgen](https://github.com/axeldelafosse/stemgen) von Axel Delafosse
**Beitrag:** Dieses Tool ist das Herzstück der Stems-Trennung. Es nutzt moderne KI-Modelle (BS RoFormer, Demucs), um den ursprünglichen Track in seine Bestandteile (Drums, Bass, Melody, Vocals) zu zerlegen. 
**Referenz:** Wird im Dockerfile als `/opt/stemgen` geklont und in der Pipeline als `stemgen.py` ausgeführt.

### [Engine DJ Stems Research](https://github.com/danielkinahan/engine-dj-stems-research) von Daniel Kinahan (basierend auf der Arbeit von Ryan Marsh)
**Beitrag:** Dieses Projekt hat das native Engine DJ `.stems`-Format erfolgreich entschlüsselt. Das darin enthaltene `encode_stems.py`-Skript nimmt unsere 4 einzelnen Stems, kodiert sie als 8-Kanal-AAC, verschlüsselt sie mit AES-128-ECB (dem von Engine DJ verwendeten Verfahren) und verpackt sie in den nativen `.stems`-Container. Dadurch sind die Tracks auf DJ-Hardware wie dem PRIME 2 direkt abspielbar.
**Referenz:** Wird im Dockerfile als `/opt/engine-dj-stems-research` geklont und in `app.py` innerhalb der Funktion `create_dj_aac_container` aufgerufen.

## Separation-Modelle

| Modell | Qualität | Hinweis |
|---|---|---|
| BS RoFormer | höher | empfohlen, langsamer |
| Demucs | gut | schneller, bewährt |

## Ausgabeformate

| Format | Beschreibung |
|---|---|
| AAC | Native-Instruments `.stem.m4a` mit verlustbehafteten Streams |
| ALAC | Native-Instruments `.stem.m4a` mit verlustfreien Streams |
| DJ-AAC (DDJ) | `.ddj`-Container mit Original-FLAC, vier separaten AAC-Dateien, Artwork und nativer Engine DJ `.stems`-Datei |

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