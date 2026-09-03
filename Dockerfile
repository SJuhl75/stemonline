FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    DENO_INSTALL=/opt/deno \
    PATH="/opt/deno/bin:${PATH}" \
    TORCH_HOME=/workspace/cache/torch \
    XDG_CACHE_HOME=/workspace/cache \
    APP_CODE_DIR=/workspace/code

WORKDIR /workspace

# Systemabhängigkeiten installieren
#
# git, curl und unzip werden nur während des Builds benötigt.
# Sie werden am Ende dieses RUN-Schritts wieder entfernt.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.10 \
        python3-pip \
        python3.10-venv \
        ca-certificates \
        ffmpeg \
        sox \
        libsox-fmt-all \
        gpac \
        rclone \
        curl \
        unzip \
        git \
        procps \
        inotify-tools && \
    ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip && \
    git clone --depth 1 \
        https://github.com/axeldelafosse/stemgen.git \
        /opt/stemgen && \
    mkdir -p /opt/deno/bin && \
    curl -fsSL \
        "https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip" \
        -o /tmp/deno.zip && \
    unzip -q /tmp/deno.zip -d /opt/deno/bin && \
    chmod +x /opt/deno/bin/deno && \
    /opt/deno/bin/deno --version && \
    rm -f /tmp/deno.zip && \
    apt-get purge -y \
        curl \
        unzip \
        git && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf \
        /var/lib/apt/lists/* \
        /tmp/*# Deno installieren
#
# Deno wird von yt-dlp für bestimmte YouTube-JavaScript-Szenarien benötigt.
#ARG DENO_VERSION=2.9.6

# Pip aktualisieren
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel

# PyTorch für CUDA 12.4 installieren
RUN python -m pip install --no-cache-dir \
        torch==2.4.0 \
        torchaudio==2.4.0 \
        --index-url https://download.pytorch.org/whl/cu124

# Python-Anwendungsabhängigkeiten installieren
COPY requirements.txt /tmp/requirements.txt

RUN python -m pip install --no-cache-dir \
        -r /tmp/requirements.txt

# Installation überprüfen
#
# CUDA ist während eines normalen Docker-Builds normalerweise nicht verfügbar.
# Daher ist "CUDA verfügbar: False" an dieser Stelle normal.
RUN python - <<'PY'
import torch
import demucs
import gradio
import yt_dlp
import bs_roformer
import torchaudio
import watchfiles

print("Torch:", torch.__version__)
print("TorchAudio:", torchaudio.__version__)
print("CUDA-Build:", torch.version.cuda)
print("CUDA während Build verfügbar:", torch.cuda.is_available())
print("Demucs:", demucs.__file__)
print("Gradio:", gradio.__version__)
print("yt-dlp:", yt_dlp.version.__version__)
print("BS-RoFormer:", bs_roformer.__file__)
print("watchfiles:", watchfiles.__file__)
PY

RUN deno --version && \
    yt-dlp --version && \
    ffmpeg -version | head -n 1 && \
    sox --version && \
    rclone version | head -n 1

# Standardcode an einem Ort außerhalb des Runtime-Codeverzeichnisses ablegen
#
# /workspace/code kann später per WebSSH oder Network Volume geändert werden.
RUN mkdir -p \
        /opt/app-defaults \
        /workspace/code \
        /workspace/cache/torch \
        /workspace/cache \
        /workspace/jobs

COPY app.py /opt/app-defaults/app.py
COPY start.sh /opt/app-defaults/start.sh

# Startskript im Image
COPY start.sh /start.sh

RUN chmod +x \
        /start.sh \
        /opt/app-defaults/start.sh

EXPOSE 7860

CMD ["/start.sh"]