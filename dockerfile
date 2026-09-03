FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

# System-Abhängigkeiten installieren (inkl. Node.js und rclone)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    curl \
    unzip \
    gnupg \
    && curl -fsSL https://nodesource.com | bash - \
    && apt-get install -y nodejs \
    && curl https://rclone.org | bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Demucs, Gradio und das offizielle stemgen-Repository installieren
RUN pip install --no-cache-dir demucs gradio yt-dlp
RUN git clone https://github.com /opt/stemgen \
    && cd /opt/stemgen && pip install -r requirements.txt

# Ports freigeben
EXPOSE 7860

WORKDIR /workspace

# Dateien kopieren
COPY app.py /workspace/app.py
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
