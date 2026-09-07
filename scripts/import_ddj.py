#!/usr/bin/env python3

import argparse
import base64
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

# Pflichtdateien im Container (flach)
REQUIRED_DDJ_FILES = [
    "original.flac",
    "track.stems",
    "manifest.json",
]

def fail(message):
    raise RuntimeError(message)

def run_command(command, description):
    print()
    print("=" * 80)
    print(description)
    print(" ".join(str(x) for x in command))
    print("=" * 80)

    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode != 0:
        raise RuntimeError(
            f"{description} fehlgeschlagen.\n"
            f"Exit-Code: {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    return result

def find_engine_dir(current_dir):
    engine_dir = current_dir / "Engine Library"
    if not engine_dir.is_dir():
        fail(f"Engine Library nicht gefunden in: {current_dir}")
    return engine_dir

def check_disk_space(required_bytes, target_dir):
    free_bytes = shutil.disk_usage(target_dir).free
    if free_bytes < required_bytes:
        fail(
            f"Zu wenig Speicherplatz. Benötigt: {required_bytes / (1024**3):.2f} GB, "
            f"Verfügbar: {free_bytes / (1024**3):.2f} GB"
        )
    print(f"Speicherplatz OK (verfügbar: {free_bytes / (1024**3):.2f} GB)")

def create_engine_backup(engine_dir, library_root):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = library_root / f"Engine-Library-Backup-{timestamp}.zip"
    print(f"Erstelle Sicherheitsbackup: {backup_path}")

    with zipfile.ZipFile(backup_path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in engine_dir.rglob("*"):
            if not path.is_file():
                continue
            archive_name = Path("Engine Library") / path.relative_to(engine_dir)
            archive.write(path, archive_name.as_posix())

    print(f"Backup erstellt: {backup_path} ({backup_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return backup_path

def safe_extract_zip(zip_path, target_dir):
    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                fail(f"Unsicherer Pfad im DDJ-Archiv: {member.filename}")
        archive.extractall(target_dir)

def validate_ddj(ddj_path, extract_dir):
    print(f"Prüfe DDJ-Container: {ddj_path}")
    if not ddj_path.is_file():
        fail(f"DDJ-Datei nicht gefunden: {ddj_path}")
    if not zipfile.is_zipfile(ddj_path):
        fail("Die Datei ist kein gültiges ZIP-Archiv.")

    safe_extract_zip(ddj_path, extract_dir)

    missing = []
    for relative_path in REQUIRED_DDJ_FILES:
        if not (extract_dir / relative_path).is_file():
            missing.append(relative_path)

    if missing:
        fail("Fehlende Dateien im DDJ-Container:\n" + "\n".join(f"- {path}" for path in missing))

    manifest_path = extract_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"manifest.json ist ungültiges JSON: {exc}")

    print("DDJ-Container ist gültig.")
    return manifest

def get_audio_info(audio_path):
    command = [
        "ffprobe", "-hide_banner", "-v", "error",
        "-show_entries", "format=duration,size,bit_rate:stream=codec_name,profile,sample_rate,channels,bit_rate",
        "-of", "json", str(audio_path)
    ]
    result = run_command(command, "Analysiere Audio")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"ffprobe lieferte ungültiges JSON: {exc}")

    format_data = data.get("format", {})
    audio_stream = next((s for s in data.get("streams", []) if s.get("codec_name")), None)

    if audio_stream is None:
        fail(f"Kein Audiostream gefunden: {audio_path}")

    duration = float(format_data.get("duration", 0))
    if duration <= 0:
        fail(f"Keine gültige Audiodauer gefunden: {audio_path}")

    return {
        "duration": duration,
        "size": int(format_data.get("size", 0)),
        "bit_rate": int(float(format_data.get("bit_rate", 0) or 0)),
        "codec_name": audio_stream.get("codec_name"),
        "profile": audio_stream.get("profile"),
        "sample_rate": int(audio_stream.get("sample_rate", 0) or 0),
        "channels": int(audio_stream.get("channels", 0) or 0),
    }

def get_artwork_bytes_and_hash(flac_path):
    """
    Extrahiert die Bilddaten aus der FLAC und berechnet den 16-Byte-MD5-Hash.
    Gibt (bytes, binary_hash) zurück, oder (None, None) wenn kein Artwork vorhanden.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="artwork_extract_"))
    temp_image = temp_dir / "cover.jpg"

    command = [
        "ffmpeg", "-y", "-i", str(flac_path), "-an", "-c:v", "copy", str(temp_image)
    ]
    result = run_command(command, "Extrahiere Artwork")

    if result.returncode != 0 or not temp_image.exists():
        # Fallback: Konvertieren
        command = ["ffmpeg", "-y", "-i", str(flac_path), "-an", "-c:v", "mjpeg", "-q:v", "2", str(temp_image)]
        result = run_command(command, "Extrahiere Artwork (Konvertierung)")

    if not temp_image.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("Warnung: Kein Artwork in der FLAC gefunden.")
        return None, None

    image_bytes = temp_image.read_bytes()
    # Engine DJ nutzt den RAW-MD5-Digest (16 Bytes), NICHT den Hex-String!
    binary_hash = hashlib.md5(image_bytes).digest()

    shutil.rmtree(temp_dir, ignore_errors=True)
    return image_bytes, binary_hash

def setup_album_art(connection, artwork_dir, flac_path):
    """
    Erstellt den AlbumArt-Eintrag in der Datenbank (falls nötig) und speichert die Datei.
    Gibt die albumArtId zurück, oder None, wenn kein Artwork vorhanden.
    """
    image_bytes, binary_hash = get_artwork_bytes_and_hash(flac_path)
    if image_bytes is None:
        return None

    artwork_dir.mkdir(parents=True, exist_ok=True)

    # Prüfen, ob der Hash bereits existiert (BLOB-Vergleich)
    cursor = connection.execute("SELECT id FROM AlbumArt WHERE hash = ?", (binary_hash,))
    row = cursor.fetchone()
    if row:
        album_art_id = row[0]
        print(f"Artwork existiert bereits (ID: {album_art_id}).")
    else:
        # Neuen Eintrag erstellen (Hash als 16-Byte BLOB speichern)
        cursor = connection.execute(
            "INSERT INTO AlbumArt (hash, albumArt) VALUES (?, ?)",
            (binary_hash, None)
        )
        connection.commit()
        album_art_id = cursor.lastrowid
        print(f"Neues Artwork angelegt (ID: {album_art_id}).")

    # Dateiname = URL-sicheres Base64 des 16-Byte-Hashes (ohne Padding "=")
    filename = base64.urlsafe_b64encode(binary_hash).decode('ascii').rstrip('=') + ".jpg"
    artwork_path = artwork_dir / filename
    if not artwork_path.exists():
        artwork_path.write_bytes(image_bytes)
        print(f"Artwork-Datei gespeichert: {artwork_path}")

    return album_art_id

def get_track_metadata(manifest, args, original_flac):
    title = args.title or manifest.get("metadata", {}).get("title") or original_flac.stem
    artist = args.artist or manifest.get("metadata", {}).get("artist") or "Unknown Artist"
    album = args.album or manifest.get("metadata", {}).get("album", "")
    genre = args.genre or manifest.get("metadata", {}).get("genre", "")
    year = args.year or manifest.get("metadata", {}).get("year", 0)
    filename = args.filename or f"{Path(args.input).stem}.flac"

    return {
        "title": str(title),
        "artist": str(artist),
        "album": str(album),
        "genre": str(genre),
        "year": int(year or 0),
        "filename": str(filename),
    }

def get_library_information(connection):
    row = connection.execute("SELECT uuid FROM Information LIMIT 1").fetchone()
    if not row or not row[0]:
        fail("Keine Library-UUID in m.db.Information gefunden.")
    return row[0]

def get_next_track_id(connection):
    row = connection.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM Track").fetchone()
    return int(row[0])

def insert_track(connection, track_id, metadata, audio_info, path, album_art_id):
    columns = [
        "id", "path", "filename", "length", "bitrate", "fileBytes",
        "title", "artist", "album", "genre", "year", "comment", "label",
        "composer", "remixer", "fileType", "isAnalyzed", "isAvailable",
        "isMetadataImported", "originTrackId", "originDatabaseUuid",
        "albumArtId"
    ]
    values = [
        track_id, path, metadata["filename"],
        int(round(audio_info["duration"])),
        int(round(audio_info["bit_rate"] / 1000)) if audio_info["bit_rate"] else 0,
        audio_info["size"], metadata["title"], metadata["artist"],
        metadata["album"], metadata["genre"], metadata["year"],
        "", "", "", "", "flac", 0, 1, 1, 0, "",
        album_art_id
    ]

    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO Track ({', '.join(columns)}) VALUES ({placeholders})"
    connection.execute(sql, values)

def verify_database(connection, track_id):
    integrity = connection.execute("PRAGMA integrity_check").fetchone()
    if not integrity or integrity[0] != "ok":
        fail(f"Datenbankintegrität fehlgeschlagen: {integrity}")

    track = connection.execute(
        """SELECT id, filename, title, artist, fileType, length, fileBytes, isAnalyzed, isAvailable, albumArtId
           FROM Track WHERE id = ?""",
        (track_id,)
    ).fetchone()
    if track is None:
        fail(f"Der neue Track {track_id} wurde nicht gefunden.")

    performance = connection.execute(
        "SELECT trackId FROM PerformanceData WHERE trackId = ?", (track_id,)
    ).fetchone()
    if performance is None:
        fail("Für den neuen Track wurde kein PerformanceData-Datensatz erzeugt.")

    print()
    print("Datenbankprüfung erfolgreich.")
    print(f"Neuer Track-ID: {track[0]}")
    print(f"Dateiname:      {track[1]}")
    print(f"Titel:          {track[2]}")
    print(f"Interpret:      {track[3]}")
    print(f"Dateityp:       {track[4]}")
    print(f"Länge:          {track[5]} Sekunden")
    print(f"isAnalyzed:     {track[7]}")
    print(f"isAvailable:    {track[8]}")
    print(f"albumArtId:     {track[9]}")
    print("PerformanceData: vorhanden")

def import_ddj(args):
    library_root = Path.cwd()
    ddj_path = Path(args.input).expanduser().resolve()

    engine_dir = find_engine_dir(library_root)
    database_path = engine_dir / "Database2" / "m.db"
    stems_output_dir = engine_dir / "Stems"
    artwork_dir = engine_dir / "Artwork"

    if not database_path.is_file():
        fail(f"Engine-Datenbank nicht gefunden: {database_path}")

    ddj_size = ddj_path.stat().st_size
    required_bytes = ddj_size * 3
    check_disk_space(required_bytes, library_root)

    backup_path = create_engine_backup(engine_dir, library_root)

    with tempfile.TemporaryDirectory(prefix="ddj_import_") as temp_dir_string:
        temp_dir = Path(temp_dir_string)

        manifest = validate_ddj(ddj_path, temp_dir)
        original_flac = temp_dir / "original.flac"
        track_stems = temp_dir / "track.stems"

        metadata = get_track_metadata(manifest, args, original_flac)
        original_info = get_audio_info(original_flac)

        print()
        print("=== DDJ-Importdaten ===")
        print(f"Titel:       {metadata['title']}")
        print(f"Interpret:   {metadata['artist']}")
        print(f"Dateiname:   {metadata['filename']}")
        print(f"Dauer:       {original_info['duration']:.3f} Sekunden")
        print(f"Sample Rate: {original_info['sample_rate']} Hz")
        print(f"Kanäle:      {original_info['channels']}")
        print(f"Codec:       {original_info['codec_name']}")

        # Datenbank nur lesen für IDs
        connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        library_uuid = get_library_information(connection)
        new_track_id = get_next_track_id(connection)
        connection.close()

        original_target = library_root / metadata["filename"]
        stems_output_dir.mkdir(parents=True, exist_ok=True)
        stem_target = stems_output_dir / f"{new_track_id} {library_uuid}.stems"

        if original_target.exists():
            fail(f"Originaldatei existiert bereits: {original_target}")
        if stem_target.exists():
            fail(f"Stem-Datei existiert bereits: {stem_target}")

        # Schreibzugriff für Artwork und Track
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")

            # Artwork einrichten (mit korrektem Base64-Dateinamen)
            album_art_id = setup_album_art(connection, artwork_dir, original_flac)

            # Original und Stems kopieren
            print(f"Kopiere Original-FLAC nach: {original_target}")
            shutil.copy2(original_flac, original_target)

            print(f"Kopiere Stem-Datei nach: {stem_target}")
            shutil.copy2(track_stems, stem_target)

            # Datenbank-Backup
            database_backup = database_path.with_name(database_path.name + ".before-ddj-import")
            shutil.copy2(database_path, database_backup)
            print(f"Datenbankkopie erstellt: {database_backup}")

            database_relative_path = f"../{metadata['filename']}"

            connection.execute("BEGIN")
            insert_track(connection, new_track_id, metadata, original_info, database_relative_path, album_art_id)
            verify_database(connection, new_track_id)
            connection.commit()

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        # Container löschen
        print(f"Lösche Container-Datei: {ddj_path}")
        ddj_path.unlink()

        print()
        print("=" * 80)
        print("IMPORT ERFOLGREICH")
        print("=" * 80)
        print(f"Backup:        {backup_path}")
        print(f"Original:      {original_target}")
        print(f"Stem-Datei:    {stem_target}")
        print(f"Track-ID:      {new_track_id}")
        print(f"Library-UUID:  {library_uuid}")
        print(f"Datenbank:     {database_path}")
        print("=" * 80)
        print()
        print("Bitte Engine DJ vollständig neu starten oder den USB-Stick erneut einlesen lassen.")

def main():
    parser = argparse.ArgumentParser(description="Importiert einen experimentellen .ddj-Container in eine Engine-DJ-Library.")
    parser.add_argument("input", help="Pfad zur .ddj-Datei")
    parser.add_argument("--title", help="Titel des neuen Tracks")
    parser.add_argument("--artist", help="Interpret des neuen Tracks")
    parser.add_argument("--album", default="", help="Album")
    parser.add_argument("--genre", default="", help="Genre")
    parser.add_argument("--year", type=int, default=0, help="Erscheinungsjahr")
    parser.add_argument("--filename", help="Zieldateiname der Original-FLAC")
    args = parser.parse_args()

    try:
        import_ddj(args)
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        return 130
    except Exception as exc:
        print(f"\nFEHLER:\n{exc}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())