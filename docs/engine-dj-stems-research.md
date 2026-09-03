# Engine-DJ-/Denon-Stem-Format – Untersuchung

Stand: 2026-09-03

## Ausgangslage

Untersucht wurde eine Engine-DJ-Library auf einem Datenträger mit folgenden Dateien:

```text
Engine Library/
├── Database2/
│   ├── hm.db
│   ├── m.db
│   ├── sm.db
│   └── stm.db
└── Stems/
    ├── 4 634c7128-6d88-47f3-ae13-30f137041a70.stems
    ├── 62 634c7128-6d88-47f3-ae13-30f137041a70.stems
    ├── 75 634c7128-6d88-47f3-ae13-30f137041a70.stems
    ├── 100 634c7128-6d88-47f3-ae13-30f137041a70.stems
    ├── 145 634c7128-6d88-47f3-ae13-30f137041a70.stems
    ├── 173 634c7128-6d88-47f3-ae13-30f137041a70.stems
    ├── 179 634c7128-6d88-47f3-ae13-30f137041a70.stems
    ├── 198 634c7128-6d88-47f3-ae13-30f137041a70.stems
    └── 242 634c7128-6d88-47f3-ae13-30f137041a70.stems
```

## Dateinamen

Das Namensschema lautet offenbar:

```text
<Track-ID> <Library-UUID>.stems
```

Die UUID:

```text
634c7128-6d88-47f3-ae13-30f137041a70
```

stimmt mit der UUID in `Database2/m.db` überein.

Beispiel:

```text
4 634c7128-6d88-47f3-ae13-30f137041a70.stems
```

gehört zu `Track.id = 4` in `m.db`.

## Bestätigte Zuordnung

Die Track-IDs der `.stems`-Dateien stimmen mit den IDs in `m.db` überein:

| ID | Titel | Interpret | Länge laut Datenbank |
|---:|---|---|---:|
| 4 | Forever Young | Alphaville | 227 s |
| 62 | Sorry I Am Late | Kollektiv Turmstrasse | 249 s |
| 75 | Back 2 The FVTR | Paul van Dyk & The YellowHeads | 318 s |
| 100 | Don't Stop | Charles D (USA) | 358 s |
| 145 | Can't Stop | Teenage Mutants & Nonameleft | 325 s |
| 173 | Pilot | Adam Beyer | 347 s |
| 179 | Get It | Nicolas Taboada | 425 s |
| 198 | Eat Beats | Justin Hahn | 366 s |
| 242 | Force | 8181 Enzo & Michael Ekow | 163 s |

Die Dauer der jeweiligen `.stems`-Dateien stimmt mit der Track-Länge in `m.db` überein.

## Containeranalyse

Die `.stems`-Dateien sind echte MP4-/ISO-Media-Dateien.

Beispiel:

```text
Container: MP4 / ISO Media
Track-Anzahl: 1
Codec: AAC-LC
Sample Rate: 44.1 kHz
Kanäle: 8
Bitrate: ungefähr 640 kbit/s
```

Beispielausgabe von MP4Box:

```text
# Movie Info - 1 track
Media Type: soun:mp4a
MPEG-4 Audio AAC LC
8 Channel(s)
SampleRate 44100
RFC6381 Codec Parameters: mp4a.40.2
```

Die Datei enthält daher wahrscheinlich vier Stereo-Stems in einem einzigen 8-Kanal-AAC-Stream:

```text
Kanal 1–2: Drums
Kanal 3–4: Bass
Kanal 5–6: Other / Melody
Kanal 7–8: Vocals
```

Die exakte Kanalreihenfolge muss noch bestätigt werden.

## Vergleich mit Native-Instruments-Stems

Die von Stemgen erzeugte Native-Instruments-Datei hat eine andere Struktur:

```text
Container: M4A
Audiostreams: 5
Stream 0: Master
Stream 1: Drums
Stream 2: Bass
Stream 3: Other
Stream 4: Vocals
```

Engine DJ verwendet offenbar dagegen:

```text
Container: MP4/M4A
Audiotracks: 1
Kanäle: 8
Codec: AAC-LC
```

Eine `.stem.m4a`-Datei von Stemgen kann daher nicht einfach in eine Engine-DJ-`.stems`-Datei umbenannt werden.

## Datenbanken

### `m.db`

`m.db` ist die Hauptdatenbank der Musikbibliothek.

Die UUID lautet:

```text
634c7128-6d88-47f3-ae13-30f137041a70
```

Die Tabelle `Track` enthält die IDs, die auch im Dateinamen der `.stems`-Dateien verwendet werden.

### `stm.db`

`stm.db` besitzt eine eigene UUID:

```text
ec7d3e16-db7a-42f2-9ac5-140e608738d0
```

Die Tabelle `Track` in `stm.db` enthält bei dieser Untersuchung keine Datensätze.

### `PerformanceData` in `m.db`

Für die untersuchten Tracks existieren normale Analyseinformationen:

```text
trackData: ungefähr 42–46 Bytes
overviewWaveFormData: ungefähr 2–2,6 KB
beatData: ungefähr 57–98 Bytes
quickCues: ungefähr 31–95 Bytes
loops: ungefähr 192–216 Bytes
```

Diese Datenmengen enthalten offensichtlich keine Audio-Stems. Die eigentlichen Stem-Audiodaten liegen separat in den `.stems`-Dateien.

## FFmpeg-Verhalten

FFmpeg erkennt die Dateien als:

```text
AAC-LC
44.1 kHz
8 Kanäle
```

Beim Dekodieren treten jedoch zahlreiche Fehler auf, unter anderem:

```text
channel element ... is not allocated
```

```text
Too large remapped id is not implemented
```

```text
Sample rate index in program config element does not match ...
```

MP4Box kann die Containerstruktur dagegen erfolgreich analysieren.

Die Ursache ist noch ungeklärt. Mögliche Erklärungen:

- ungewöhnliche 8-Kanal-AAC-Konfiguration
- spezielles Kanal-Mapping
- Engine-DJ-spezifische AAC-Struktur
- inkompatible FFmpeg-Version
- proprietäre oder geschützte Audiostruktur

Es ist noch nicht bewiesen, dass die Dateien verschlüsselt sind.

## Aktueller Stand

Bestätigt:

- `.stems` ist ein echter MP4-/AAC-Container
- eine Datei enthält einen 8-Kanal-AAC-Stream
- die Dateinummer entspricht sehr wahrscheinlich der Track-ID aus `m.db`
- die UUID im Dateinamen entspricht der UUID aus `m.db`
- Trackdauer und `.stems`-Dauer stimmen überein
- `m.db` enthält keine großen Audio-BLOBs
- `stm.db` ist bei dieser Untersuchung leer
- das Format unterscheidet sich vom Native-Instruments-Stem-Format

Noch offen:

- exakte Kanalreihenfolge
- exakte AAC-Encoderparameter
- ob zusätzliche Engine-DJ-Metadaten benötigt werden
- ob ein selbst erzeugter 8-Kanal-AAC-Container akzeptiert wird
- ob die `.stems`-Datei ohne Datenbankeintrag funktioniert
- ob Engine DJ ausschließlich den Dateinamen zur Zuordnung verwendet
- ob das Format teilweise proprietär oder geschützt ist

## Nächster geplanter Test

Auf einer Kopie der Engine-DJ-Library:

1. Vier Stem-WAV-Dateien erzeugen.
2. In acht Kanäle zusammenführen.
3. Als AAC-LC in einen MP4-Container schreiben.
4. Das Ergebnis nach folgendem Schema benennen:

```text
<Track-ID> <m.db-UUID>.stems
```

5. Eine einzelne bestehende `.stems`-Datei ersetzen.
6. Die Library in Engine DJ beziehungsweise auf dem Denon-Gerät testen.

Die Original-Library darf dabei nicht verändert werden.

## Datenschutz und Repository

Nicht in Git committen:

- Audio-Dateien
- komplette Engine-Library
- Datenbanken
- Backups
- persönliche Dateipfade
- Seriennummern
- Zugangsdaten

## Weitere Erkenntnisse
Engine-DJ-.stems:
- MP4/ISO Media
- ein Audiotrack
- AAC-LC
- mp4a.40.2
- 8 Kanäle
- 44,1 kHz meistens
- ungefähr 640 kbit/s
- 9796 Frames bei 227,439 Sekunden
- 28 Bytes AAC-Extradata
- ftyp/free/mdat/moov-Struktur
- Dateiname verwendet Track-ID aus m.db
- UUID stammt aus m.db
- stm.db enthält bei diesem Export keine Track-Datensätze

Die aktuelle Schlussfolgerung lautet daher:

Wir können wahrscheinlich aus unseren vier Stem-WAV-Dateien einen technischen Engine-DJ-Kandidaten erzeugen, indem wir sie als achtkanaligen AAC-LC-Stream verpacken. Ob Engine DJ die Datei akzeptiert, hängt aber von Kanalreihenfolge, AAC-Konfiguration und möglicherweise dem Dateinamen-/Datenbankbezug ab.

## Struktur ddj-Format
Ergebnis des neuen DJ-AAC-Formats:

Lgr2WMjvlM8.ddj
├── audio/
│   └── original.flac
├── stems/
│   ├── vocals.m4a
│   ├── melody.m4a
│   ├── bass.m4a
│   └── drums.m4a
├── manifest.json
└── README.txt

## Extraktion des ddj-Formats
import zipfile

with zipfile.ZipFile("Lgr2WMjvlM8.ddj") as archive:
    archive.extractall("zielordner")