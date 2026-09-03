FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

# System-Abhängigkeiten und sudo installieren (wichtig für den rclone installer)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    curl \
    unzip \
    gnupg \
    sudo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 1. Aktueller Node.js 20 Installationsweg für Ubuntu/Debian
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://nodesource.com | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://nodesource.com nodistro main" | tee /etc/apt/keyrings/nodesource.list \
    && apt-get update && apt-get install nodejs -y

# 2. Rclone über das offizielle Skript installieren (nutzt jetzt das installierte sudo)
RUN curl https://rclone.org | bash

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
