FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DENO_INSTALL=/opt/deno \
    PATH="/opt/deno/bin:${PATH}" \
    TORCH_HOME=/workspace/cache/torch \
    XDG_CACHE_HOME=/workspace/cache \
    APP_CODE_DIR=/workspace/code

ARG DENO_VERSION=2.9.6

WORKDIR /workspace

# Systemabhängigkeiten installieren
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
        libjpeg62 \
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
    git clone --depth 1 \
        https://github.com/danielkinahan/engine-dj-stems-research.git \
        /opt/engine-dj-stems-research && \
    mkdir -p /opt/deno/bin && \
    curl -fL \
        "https://dl.deno.land/release/v${DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip" \
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
    ldconfig && \
    rm -rf \
        /var/lib/apt/lists/* \
        /tmp/*

# Stemgen cli.py patchen
RUN python3.10 - <<'PY'
from pathlib import Path

path = Path("/opt/stemgen/stemgen/cli.py")
text = path.read_text()

text = text.replace(
    "subprocess.run(stem_args)",
    "subprocess.run(stem_args, check=True)",
)

text = text.replace(
    "        subprocess.run(cmd)\n",
    "        subprocess.run(cmd, check=True)\n",
)

path.write_text(text)
print("Stemgen cli.py wurde gepatcht.")
PY

# Pip aktualisieren
RUN python -m pip install \
        --no-cache-dir \
        --upgrade \
        pip \
        setuptools \
        wheel

# PyTorch und TorchAudio für CUDA 12.4 installieren
RUN python -m pip install \
        --no-cache-dir \
        torch==2.4.0 \
        torchaudio==2.4.0 \
        --index-url https://download.pytorch.org/whl/cu124

# Python-Anwendungsabhängigkeiten installieren
COPY requirements.txt /tmp/requirements.txt

RUN python -m pip install \
        --no-cache-dir \
        -r /tmp/requirements.txt \
        pycryptodome

# Installation überprüfen
RUN python - <<'PY'
import torch
import torchaudio
import demucs
import gradio
import yt_dlp
import bs_roformer
import watchfiles
from Crypto.Cipher import AES

print("Torch:", torch.__version__)
print("TorchAudio:", torchaudio.__version__)
print("CUDA-Build:", torch.version.cuda)
print("CUDA während Build verfügbar:", torch.cuda.is_available())
print("Demucs:", demucs.__file__)
print("Gradio:", gradio.__version__)
print("yt-dlp:", yt_dlp.version.__version__)
print("BS-RoFormer:", bs_roformer.__file__)
print("watchfiles:", watchfiles.__file__)
print("PyCryptodome: OK")
PY

# Systemprogramme überprüfen
RUN deno --version && \
    yt-dlp --version && \
    ffmpeg -version | head -n 1 && \
    sox --version && \
    rclone version | head -n 1 && \
    ls -la /opt/engine-dj-stems-research

# Verzeichnisse vorbereiten
RUN mkdir -p \
        /opt/app-defaults \
        /workspace/code \
        /workspace/cache \
        /workspace/cache/torch \
        /workspace/jobs \
        /workspace/rclone

# Standardcode außerhalb des Runtime-Codeverzeichnisses ablegen
COPY app.py /opt/app-defaults/app.py
COPY start.sh /opt/app-defaults/start.sh

# Startskript ins Image kopieren
COPY start.sh /start.sh

RUN chmod +x \
        /start.sh \
        /opt/app-defaults/start.sh

EXPOSE 7860

CMD ["/start.sh"]