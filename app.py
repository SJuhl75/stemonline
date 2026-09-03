import os
os.environ["MKL_THREADING_LAYER"] = "GNU"
import subprocess
import gradio as gr
import shutil

def process_pipeline(youtube_url, cloud_folder, progress=gr.Progress()):
    if not youtube_url:
        return "Bitte gib einen gültigen YouTube-Link ein."
    
    # 1. Pfade initialisieren
    download_dir = "/workspace/downloads"
    output_dir = "/workspace/stems_output"
    os.makedirs(download_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    # 2. Schritt: YouTube Download (Dein exakter exzellenter Audiophile-Befehl)
    progress(0.1, desc="Lade Audio von YouTube via yt-dlp (FLAC)...")
    yt_cmd = [
        "yt-dlp", 
        "--js-runtimes", "node", 
        "-x", 
        "--audio-format", "flac", 
        "--postprocessor-args", "ExtractAudio:-ar 44100 -ac 2",
        "-o", f"{download_dir}/%(title)s.%(ext)s",
        youtube_url
    ]
    subprocess.run(yt_cmd, check=True)
    
    # Heruntergeladene FLAC-Datei ausfindig machen
    downloaded_files = [f for f in os.listdir(download_dir) if f.endswith(".flac")]
    if not downloaded_files:
        return "Fehler beim Download: Keine FLAC-Datei gefunden."
    
    input_flac_path = os.path.join(download_dir, downloaded_files[0])
    
    # 3. Schritt: Stem-Generierung im FLAC-Modus via stemgen
    progress(0.4, desc="Zerlege Audio und erstelle Traktor M4A-Stemcontainer (stemgen)...")
    # stemgen benötigt den Wechsel ins eigene Verzeichnis oder korrekte Pfade
    stem_cmd = [
        "python3", "/opt/stemgen/stemgen.py", 
        "-f", "flac", 
        "-o", output_dir, 
        input_flac_path
    ]
    subprocess.run(stem_cmd, check=True)
    
    # Generierte .m4a-Datei lokalisieren
    generated_files = [f for f in os.listdir(output_dir) if f.endswith(".stem.m4a")]
    if not generated_files:
        return "Fehler bei Stem-Erstellung: Keine .stem.m4a-Datei generiert."
    
    generated_m4a = os.path.join(output_dir, generated_files[0])
    
    # 4. Schritt: Upload auf die MagentaCloud via rclone
    progress(0.8, desc="Lade gemuxte Datei hoch zu MagentaCloud...")
    # Cloud-Zielordner definieren (Standard: Root, sonst Unterordner)
    target_path = f"magentacloud:{cloud_folder.strip('/')}" if cloud_folder else "magentacloud:"
    
    upload_cmd = ["rclone", "copy", generated_m4a, target_path]
    subprocess.run(upload_cmd, check=True)
    
    # 5. Aufräumen (Da wir im flüchtigen Container-Speicher ohne Volume arbeiten)
    shutil.rmtree(download_dir)
    shutil.rmtree(output_dir)
    
    return f"🚀 Erfolg! Datei '{generated_files[0]}' wurde generiert und in die MagentaCloud hochgeladen."

# Gradio Web UI erstellen
with gr.Blocks(title="YouTube to Traktor Stems Cloud Pipeline") as demo:
    gr.Markdown("# 🎧 YouTube-to-Traktor Stems Pipeline 🎛️")
    gr.Markdown("Lädt Musik von YouTube in Studio-FLAC, generiert Native Instruments .stem.m4a-Dateien und sendet sie direkt in deine MagentaCloud.")
    
    with gr.Row():
        with gr.Column():
            yt_link = gr.Textbox(label="YouTube Video Link", placeholder="https://www.youtube.com/watch?v=...")
            cloud_dir = gr.Textbox(label="MagentaCloud Zielordner (Optional)", placeholder="Musik/TraktorStems", value="TraktorStems")
            start_btn = gr.Button("Pipeline starten", variant="primary")
            
        with gr.Column():
            status_output = gr.Textbox(label="Status & Log-Ausgabe", interactive=False)
            
    start_btn.click(fn=process_pipeline, inputs=[yt_link, cloud_dir], outputs=status_output)

demo.launch(server_name="0.0.0.0", server_port=7860)
