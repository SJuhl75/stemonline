import os

# Muss vor Importen gesetzt werden, die MKL verwenden
os.environ.setdefault("MKL_THREADING_LAYER", "GNU")

import glob
import shutil
import subprocess
import tempfile
from pathlib import Path

import gradio as gr


STEMGEN_DIR = "/opt/stemgen"
WORK_DIR = "/workspace"

MODEL_NAMES = {
    "BS RoFormer": "bs_roformer",
    "Demucs": "htdemucs",
}

def run_command(command, cwd=None, description="Befehl"):
    """
    Führt einen Prozess aus und gibt bei Fehlern stdout/stderr aus.
    """
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
            f"{description} konnte nicht gestartet werden. "
            f"Programm nicht gefunden: {command[0]}"
        ) from exc

    if result.returncode != 0:
        details = (
            f"{description} fehlgeschlagen.\n\n"
            f"Exit-Code: {result.returncode}\n"
            f"Kommando: {' '.join(str(x) for x in command)}\n\n"
            f"STDOUT:\n{result.stdout[-5000:]}\n\n"
            f"STDERR:\n{result.stderr[-10000:]}"
        )
        raise RuntimeError(details)

    return result


def process_pipeline(
    youtube_url,
    cloud_folder,
    separator_model,
    progress=gr.Progress(),
):
    model_name = MODEL_NAMES.get(
        separator_model,
        "bs_roformer",
    )
    if not youtube_url or not youtube_url.strip():
        return "Bitte gib einen gültigen YouTube-Link ein."

    job_dir = None

    try:
        # Separates Verzeichnis pro Auftrag
        job_dir = tempfile.mkdtemp(
            prefix="stemgen_job_",
            dir=os.path.join(WORK_DIR, "jobs"),
        )

        download_dir = os.path.join(job_dir, "downloads")
        output_dir = os.path.join(job_dir, "stems_output")

        os.makedirs(download_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        # ------------------------------------------------------------
        # 1. Audio mit yt-dlp herunterladen
        # ------------------------------------------------------------
        progress(0.1, desc="Lade Audio von YouTube via yt-dlp herunter ...")

        yt_cmd = [
            "yt-dlp",

            # Keine Playlists herunterladen
            "--no-playlist",

            # Deno statt Node verwenden
            "--js-runtimes",
            "deno",

            # Audio extrahieren
            "-x",
            "--audio-format",
            "flac",

            # 44,1 kHz / Stereo
            "--postprocessor-args",
            "ExtractAudio:-ar 44100 -ac 2",

            # Dateiname anhand der Video-ID
            "-o",
            os.path.join(download_dir, "%(id)s.%(ext)s"),

            youtube_url.strip(),
        ]

        run_command(
            yt_cmd,
            description="yt-dlp",
        )

        downloaded_files = sorted(
            Path(download_dir).glob("*.flac")
        )

        if not downloaded_files:
            return (
                "Fehler beim Download: "
                "yt-dlp hat keine FLAC-Datei erzeugt."
            )

        input_flac_path = str(downloaded_files[0])

        # ------------------------------------------------------------
        # 2. Stemgen ausführen
        # ------------------------------------------------------------
        progress(
            0.4,
            desc="Erzeuge Native-Instruments-Stem-Datei ...",
        )

        stem_cmd = [
            "python",
            "stemgen.py",
            "-i",
            input_flac_path,
            "-o",
            output_dir,
            "-f",
            "alac",
            "-d",
            "cuda",
            "-n",
            model_name,
        ]

        run_command(
            stem_cmd,
            cwd=STEMGEN_DIR,
            description="Stemgen",
        )

        generated_files = glob.glob(
            os.path.join(output_dir, "**", "*.stem.m4a"),
            recursive=True,
        )

        if not generated_files:
            return (
                "Stemgen wurde zwar beendet, aber es wurde keine "
                ".stem.m4a-Datei gefunden."
            )

        generated_m4a = generated_files[0]
        generated_filename = os.path.basename(generated_m4a)

        # ------------------------------------------------------------
        # 3. rclone-Konfiguration prüfen
        # ------------------------------------------------------------
        progress(
            0.8,
            desc="Lade die fertige Stem-Datei zur MagentaCloud hoch ...",
        )

        target_path = (
            f"magentacloud:{cloud_folder.strip('/')}"
            if cloud_folder and cloud_folder.strip()
            else "magentacloud:"
        )

        upload_cmd = [
            "rclone",
            "copy",
            generated_m4a,
            target_path,
            "--verbose",
        ]

        run_command(
            upload_cmd,
            description="rclone",
        )

        return (
            f"Erfolg!\n\n"
            f"Datei: {generated_filename}\n"
            f"Ziel: {target_path}"
        )

    except Exception as exc:
        # Fehlermeldung wird im Gradio-Feld angezeigt
        return f"Fehler in der Pipeline:\n\n{exc}"

    finally:
        # Auch bei Fehlern temporäre Dateien entfernen
        if job_dir and os.path.exists(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)


with gr.Blocks(
    title="YouTube to Traktor Stems Cloud Pipeline"
) as demo:
    gr.Markdown(
        "# 🎧 YouTube-to-Traktor Stems Pipeline 🎛️"
    )

    gr.Markdown(
        "Lädt Audio von YouTube herunter, erzeugt eine "
        "Native-Instruments-.stem.m4a-Datei und lädt diese "
        "anschließend zur MagentaCloud hoch."
    )

    with gr.Row():
        with gr.Column():
            yt_link = gr.Textbox(
                label="YouTube Video Link",
                placeholder="https://www.youtube.com/watch?v=...",
            )

            separator_model = gr.Radio(
                choices=[
                    "BS RoFormer",
                    "Demucs",
                ],
                value="BS RoFormer",
                label="Separation-Modell",
                info=(
                    "BS RoFormer liefert normalerweise die bessere Qualität. "
                    "Demucs ist eine alternative Separation-Engine."
                ),
            )
            
            cloud_dir = gr.Textbox(
                label="MagentaCloud Zielordner",
                placeholder="Musik/TraktorStems",
                value="TraktorStems",
            )

            start_btn = gr.Button(
                "Pipeline starten",
                variant="primary",
            )

        with gr.Column():
            status_output = gr.Textbox(
                label="Status & Log-Ausgabe",
                interactive=False,
                lines=20,
            )

    start_btn.click(
        fn=process_pipeline,
        inputs=[
            yt_link,
            cloud_dir,
            separator_model,
        ],
        outputs=status_output,
    )

demo.launch(
    server_name="0.0.0.0",
    server_port=7860,
)