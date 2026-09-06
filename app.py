import os

# Muss vor Importen gesetzt werden, die MKL verwenden
os.environ.setdefault("MKL_THREADING_LAYER", "GNU")

import glob
import json
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import gradio as gr


STEMGEN_DIR = "/opt/stemgen"
WORK_DIR = "/workspace"
ENCODE_STEMS_SCRIPT = "/opt/engine-dj-stems-research/encode_stems.py"

# Permanentes Verzeichnis für Downloads
DOWNLOAD_DIR = "/workspace/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

MODEL_NAMES = {
    "BS RoFormer": "bs_roformer",
    "Demucs": "htdemucs",
}

OUTPUT_FORMATS = {
    "AAC – klein und kompatibel": "aac",
    "ALAC – verlustfrei und groß": "alac",
    "DJ-AAC – DDJ-Container": "ddj",
}

def run_command(command, cwd=None, description="Befehl"):
    """Führt einen Prozess aus und gibt bei Fehlern stdout/stderr aus."""
    command_display = " ".join(str(x) for x in command)

    print()
    print("=" * 80)
    print(f"START: {description}")
    print(f"Kommando: {command_display}")
    print(f"Arbeitsverzeichnis: {cwd}")
    print("=" * 80)

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"{description} konnte nicht gestartet werden.\n"
            f"Programm nicht gefunden: {command[0]}"
        ) from exc

    print(f"Exit-Code: {result.returncode}")

    if result.stdout:
        print(f"{description} STDOUT:")
        print(result.stdout)

    if result.stderr:
        print(f"{description} STDERR:")
        print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            f"{description} fehlgeschlagen.\n\n"
            f"Exit-Code: {result.returncode}\n"
            f"Kommando: {command_display}\n\n"
            f"STDOUT:\n{result.stdout[-10000:]}\n\n"
            f"STDERR:\n{result.stderr[-10000:]}"
        )

    return result

def get_files_recursively(directory):
    """Gibt alle Dateien in einem Verzeichnis rekursiv zurück."""
    return [path for path in Path(directory).rglob("*") if path.is_file()]

def find_stemgen_output(output_dir):
    """Sucht die von Stemgen erzeugte .stem.m4a-Datei."""
    generated_files = glob.glob(
        os.path.join(output_dir, "**", "*.stem.m4a"),
        recursive=True,
    )

    if not generated_files:
        return None

    generated_files.sort(key=lambda path: os.path.getsize(path), reverse=True)
    return generated_files[0]

def normalize_audio_file(input_path, output_path, metadata, artwork_path):
    """
    Normalisiert die Lautstärke, setzt Metadaten (Titel, Artist, Genre)
    und bettet das Artwork (Cover) in die FLAC-Datei ein.
    """
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-i", artwork_path,
        "-map", "0:a",
        "-map", "1:v",
        "-c:v", "mjpeg",
        "-disposition:v:0", "attached_pic",
        "-metadata", f"title={metadata.get('title', 'Unknown Title')}",
        "-metadata", f"artist={metadata.get('artist', 'Unknown Artist')}",
        "-metadata", f"genre={metadata.get('genre', '')}",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ar", "44100", "-ac", "2",
        output_path
    ]
    run_command(cmd, description="Audio-Normalisierung & Metadaten/Artwork")
    return output_path

def create_dj_aac_container(
    original_flac_path,
    generated_stem_m4a,
    archive_path,
    model_label,
    model_name,
    youtube_url,
    artwork_path
):
    archive_path = Path(archive_path)
    package_dir = Path(
        tempfile.mkdtemp(
            prefix="ddj_package_",
            dir=archive_path.parent,
        )
    )

    try:
        audio_dir = package_dir / "audio"
        stems_dir = package_dir / "stems"

        audio_dir.mkdir(parents=True, exist_ok=True)
        stems_dir.mkdir(parents=True, exist_ok=True)

        packaged_original = audio_dir / "original.flac"
        shutil.copy2(original_flac_path, packaged_original)

        if artwork_path and os.path.exists(artwork_path):
            shutil.copy2(artwork_path, package_dir / "artwork.png")

        stem_streams = {
            "vocals": 4,
            "melody": 3,
            "bass": 2,
            "drums": 1,
        }

        packaged_stems = {}

        for stem_name, stream_index in stem_streams.items():
            output_stem = stems_dir / f"{stem_name}.aac"

            extract_cmd = [
                "ffmpeg", "-hide_banner", "-y", "-i", str(generated_stem_m4a),
                "-map", f"0:a:{stream_index}",
                "-c", "copy", "-vn", "-f", "adts",
                str(output_stem),
            ]

            run_command(
                extract_cmd,
                description=f"Extrahiere {stem_name}-AAC-Stream als ADTS",
            )

            if not output_stem.exists():
                raise RuntimeError(f"Stem-Datei wurde nicht erzeugt: {output_stem}")

            packaged_stems[stem_name] = {
                "path": f"stems/{stem_name}.aac",
                "stream_index_source": stream_index,
                "size_bytes": output_stem.stat().st_size,
            }

        output_stems_path = package_dir / "track.stems"

        encode_cmd = [
            "python3", ENCODE_STEMS_SCRIPT,
            "--drums", str(stems_dir / "drums.aac"),
            "--bass", str(stems_dir / "bass.aac"),
            "--melody", str(stems_dir / "melody.aac"),
            "--vocals", str(stems_dir / "vocals.aac"),
            str(output_stems_path),
        ]

        run_command(encode_cmd, description="Generiere native Engine DJ .stems Datei")

        if not output_stems_path.exists():
            raise RuntimeError(f"Die .stems Datei wurde nicht erzeugt: {output_stems_path}")

        manifest = {
            "format": "DDJ experimental container",
            "format_version": 1,
            "file_extension": ".ddj",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": {
                "youtube_url": youtube_url,
                "original_file": "audio/original.flac",
            },
            "separation": {
                "model_label": model_label,
                "model_name": model_name,
                "device": "cuda",
            },
            "audio": {
                "input_format": "FLAC",
                "stem_format": "AAC-LC",
                "sample_rate_hz": 44100,
                "channels_per_stem": 2,
            },
            "engine_dj_native_file": "track.stems",
            "engine_dj_working_hypothesis": {
                "container": "MP4/M4A",
                "audio_streams": 1,
                "channels": 8,
                "codec": "AAC-LC",
                "channel_order": [
                    "vocals_left", "vocals_right",
                    "melody_left", "melody_right",
                    "bass_left", "bass_right",
                    "drums_left", "drums_right",
                ],
                "note": "The channel order is an experimental hypothesis and has not yet been confirmed against Engine DJ.",
            },
            "stems": packaged_stems,
        }

        manifest_path = package_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        readme_text = """DDJ experimental container

This file is a ZIP archive with the .ddj extension.

Contents:
- audio/original.flac
- stems/vocals.aac
- stems/melody.aac
- stems/bass.aac
- stems/drums.aac
- track.stems
- artwork.png
- manifest.json

The four AAC files contain the separated stems from the
Native-Instruments Stemgen output.

The track.stems file is a native Engine DJ .stems file
encoded via the encode_stems.py script (AES-128 encrypted).

The current Engine DJ channel-order hypothesis is:

1. Vocals
2. Melody / Other
3. Bass
4. Drums

This file is an intermediate exchange format for testing.
"""
        readme_path = package_dir / "README.txt"
        readme_path.write_text(readme_text, encoding="utf-8")

        with zipfile.ZipFile(
            archive_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for file_path in package_dir.rglob("*"):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(package_dir))

        if not archive_path.exists():
            raise RuntimeError(f"DDJ-Datei wurde nicht erzeugt: {archive_path}")

        return manifest

    finally:
        shutil.rmtree(package_dir, ignore_errors=True)

def process_pipeline(
    youtube_url,
    cloud_folder,
    separator_model,
    output_format_label,
    normalize_audio,
    progress=gr.Progress(),
):
    if not youtube_url or not youtube_url.strip():
        return "Bitte gib einen gültigen YouTube-Link ein.", gr.update(visible=False)

    model_name = MODEL_NAMES.get(separator_model, "bs_roformer")
    output_format = OUTPUT_FORMATS.get(output_format_label, "aac")

    job_dir = None

    try:
        jobs_dir = os.path.join(WORK_DIR, "jobs")
        os.makedirs(jobs_dir, exist_ok=True)

        job_dir = tempfile.mkdtemp(prefix="stemgen_job_", dir=jobs_dir)
        download_dir = os.path.join(job_dir, "downloads")
        output_dir = os.path.join(job_dir, "stems_output")

        os.makedirs(download_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        progress(0.05, desc="Rufe YouTube-Metadaten ab ...")
        info_cmd = ["yt-dlp", "--dump-single-json", "--no-playlist", youtube_url.strip()]
        info_result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
        video_info = json.loads(info_result.stdout)

        title = video_info.get('title', 'Unknown Title')
        artist = video_info.get('uploader') or video_info.get('creator') or 'Unknown Artist'
        genre = video_info.get('genre', '')

        safe_artist = "".join(c for c in artist if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        base_filename = f"{safe_artist} - {safe_title}"

        metadata = {
            "title": title,
            "artist": artist,
            "genre": genre
        }

        progress(0.1, desc="Lade Audio von YouTube herunter ...")
        yt_cmd = [
            "yt-dlp", "--no-playlist", "--js-runtimes", "deno",
            "-x", "--audio-format", "flac",
            "--postprocessor-args", "ExtractAudio:-ar 44100 -ac 2",
            "--write-thumbnail",
            "-o", os.path.join(download_dir, f"{base_filename}.%(ext)s"),
            youtube_url.strip()
        ]
        run_command(yt_cmd, description="yt-dlp mit Thumbnail")

        downloaded_files = sorted(Path(download_dir).glob(f"{base_filename}*.flac"))
        if not downloaded_files:
            downloaded_files = sorted(Path(download_dir).glob("*.flac"))
        if not downloaded_files:
            return "Fehler: Keine FLAC-Datei nach Download gefunden.", gr.update(visible=False)
        input_flac_path = str(downloaded_files[0])

        thumbnail_path = None
        for file in Path(download_dir).glob(f"{base_filename}.*"):
            if file.suffix.lower() in ['.jpg', '.jpeg', '.webp', '.png']:
                thumbnail_path = str(file)
                break

        artwork_path = None
        if thumbnail_path:
            artwork_path = os.path.join(download_dir, "artwork.png")
            progress(0.12, desc="Konvertiere Artwork auf 600x600 ...")
            run_command([
                "ffmpeg", "-y", "-i", thumbnail_path,
                "-vf", "scale=600:600:force_original_aspect_ratio=decrease,pad=600:600:(ow-iw)/2:(oh-ih)/2",
                artwork_path
            ], description="Artwork konvertieren")

        if normalize_audio:
            progress(0.15, desc="Normalisiere Audio und bette Metadaten/Artwork ein ...")
            normalized_path = os.path.join(download_dir, "normalized.flac")
            normalize_audio_file(input_flac_path, normalized_path, metadata, artwork_path)
            input_flac_path = normalized_path

        stemgen_format = "aac" if output_format == "ddj" else output_format

        progress(0.3, desc=f"Erzeuge Stem-Datei mit {separator_model} im {stemgen_format.upper()}-Format ...")
        stem_cmd = [
            "python", "stemgen.py", "-i", input_flac_path, "-o", output_dir,
            "-f", stemgen_format, "-d", "cuda", "-n", model_name,
        ]
        run_command(stem_cmd, cwd=STEMGEN_DIR, description=f"Stemgen mit {separator_model} und {stemgen_format.upper()}")

        generated_m4a = find_stemgen_output(output_dir)
        if not generated_m4a:
            all_output_files = []
            for file_path in get_files_recursively(output_dir):
                all_output_files.append(os.path.relpath(file_path, output_dir))
            output_listing = "\n".join(all_output_files) if all_output_files else "(keine Dateien)"
            return (f"Stemgen wurde beendet, aber keine .stem.m4a-Datei gefunden.\n\n"
                    f"Modell: {separator_model}\nFormat: {stemgen_format.upper()}\n\n"
                    f"Gefundene Dateien:\n{output_listing}"), gr.update(visible=False)

        generated_filename = os.path.basename(generated_m4a)

        if output_format == "ddj":
            progress(0.65, desc="Erzeuge DDJ-Archiv ...")
            archive_basename = Path(generated_filename).name
            if archive_basename.endswith(".stem.m4a"):
                archive_basename = archive_basename[:-len(".stem.m4a")]
            final_filename = f"{base_filename}.ddj"
            ddj_path = os.path.join(job_dir, final_filename)

            create_dj_aac_container(
                original_flac_path=input_flac_path,
                generated_stem_m4a=generated_m4a,
                archive_path=ddj_path,
                model_label=separator_model,
                model_name=model_name,
                youtube_url=youtube_url.strip(),
                artwork_path=artwork_path
            )
            artifact_path = ddj_path
            artifact_filename = os.path.basename(artifact_path)
        else:
            artifact_path = generated_m4a
            artifact_filename = generated_filename

        if not os.path.exists(artifact_path):
            return "Fehler: Die finale Ausgabedatei wurde nicht gefunden.", gr.update(visible=False)

        artifact_size_mb = os.path.getsize(artifact_path) / 1024 / 1024

        progress(0.85, desc=f"Lade {artifact_filename} zur MagentaCloud hoch ...")
        if cloud_folder and cloud_folder.strip():
            remote_file_path = f"magentacloud:{cloud_folder.strip('/')}/{artifact_filename}"
        else:
            remote_file_path = f"magentacloud:{artifact_filename}"

        upload_cmd = [
            "rclone", "copyto", artifact_path, remote_file_path,
            "--verbose", "--progress", "--stats-one-line", "--stats", "5s",
        ]
        run_command(upload_cmd, description="rclone")

        progress(1.0, desc="Pipeline erfolgreich abgeschlossen.")
        
        # WICHTIG: Datei in ein permanentes Verzeichnis kopieren, BEVOR das temporäre Verzeichnis gelöscht wird!
        safe_download_name = "".join(c for c in artifact_filename if c.isalnum() or c in (' ', '-', '_', '.')).strip()
        permanent_path = os.path.join(DOWNLOAD_DIR, safe_download_name)
        shutil.copy2(artifact_path, permanent_path)
        
        return (f"Erfolg!\n\nDatei: {artifact_filename}\nGröße: {artifact_size_mb:.1f} MB\n"
                f"Modell: {separator_model}\nAusgabeformat: {output_format_label}\n"
                f"Ziel: {remote_file_path}"), gr.update(visible=True, value=permanent_path)

    except Exception as exc:
        return f"Fehler in der Pipeline:\n\n{exc}", gr.update(visible=False)

    finally:
        # Das temporäre Job-Verzeichnis kann jetzt gefahrlos gelöscht werden, 
        # da die Datei in DOWNLOAD_DIR gesichert wurde.
        if job_dir and os.path.exists(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)

with gr.Blocks(title="YouTube to Traktor / Denon Stem Pipeline") as demo:
    gr.Markdown("# 🎧 YouTube-to-Stems Pipeline 🎛️")
    gr.Markdown("Lädt Audio von YouTube herunter, erzeugt Stems und lädt das Ergebnis zur MagentaCloud hoch.")
    gr.Markdown(
        """
### Ausgabeformate

- **AAC**: Native-Instruments-Stem-Datei mit AAC-Streams
- **ALAC**: Native-Instruments-Stem-Datei mit verlustfreien Streams
- **DJ-AAC**: Experimenteller `.ddj`-Container mit Original-FLAC, vier separaten AAC-Stem-Dateien und nativer `.stems`-Datei
"""
    )

    with gr.Row():
        with gr.Column():
            yt_link = gr.Textbox(label="YouTube Video Link", placeholder="https://www.youtube.com/watch?v=...")
            separator_model = gr.Radio(
                choices=["BS RoFormer", "Demucs"],
                value="BS RoFormer",
                label="Separation-Modell",
                info="BS RoFormer liefert normalerweise die bessere Qualität. Demucs ist eine Alternative.",
            )
            output_format = gr.Radio(
                choices=["AAC – klein und kompatibel", "ALAC – verlustfrei und groß", "DJ-AAC – DDJ-Container"],
                value="DJ-AAC – DDJ-Container",
                label="Ausgabeformat",
                info="DJ-AAC erzeugt ein .ddj-ZIP-Archiv mit Original-FLAC, vier AAC-Stem-Dateien und nativer .stems-Datei.",
            )
            normalize_audio = gr.Checkbox(
                label="Audio normalisieren (loudnorm)",
                value=True,
                info="Aktiviert die Lautstärke-Normalisierung und bettet Titel, Artist, Genre und Cover ein.",
            )
            cloud_dir = gr.Textbox(label="MagentaCloud Zielordner", placeholder="Musik/TraktorStems", value="TraktorStems")
            start_btn = gr.Button("Pipeline starten", variant="primary")

        with gr.Column():
            status_output = gr.Textbox(label="Status & Log-Ausgabe", interactive=False, lines=20)
            
            # Download-Feld ist standardmäßig unsichtbar!
            download_output = gr.File(label="Download der erzeugten Datei", visible=False)

    start_btn.click(
        fn=process_pipeline,
        inputs=[yt_link, cloud_dir, separator_model, output_format, normalize_audio],
        outputs=[status_output, download_output],
    )

demo.launch(server_name="0.0.0.0", server_port=7860)