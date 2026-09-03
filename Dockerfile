FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

# System-Abhängigkeiten, rclone, sox und gpac (für das Traktor m4a Muxen) installieren
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    curl \
    unzip \
    gnupg \
    rclone \
    sox \
    gpac \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Offiziellen Deno-Runtime-Installer für yt-dlp ausführen
RUN curl -fsSL https://deno.land | sh
ENV DENO_INSTALL="/root/.local"
ENV PATH="$DENO_INSTALL/bin:$PATH"

# Die von Stemgen benötigten Python-Pakete direkt installieren
RUN pip install --no-cache-dir demucs gradio yt-dlp mutagen

# Stemgen-Repository klonen (Jetzt ohne den fehlerhaften Anforderungen-Aufruf!)
RUN git clone https://github.com/axeldelafosse/stemgen.git /opt/stemgen

# Port für das Gradio WebUI freigeben
EXPOSE 7860

WORKDIR /workspace

# Pipeline-Dateien in den Container kopieren
COPY app.py /workspace/app.py
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
