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

# 1. Systemabhängigkeiten + Python 3.12 über deadsnakes installieren
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        software-properties-common \
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
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.12 \
        python3.12-venv \
        python3-pip && \
    ln -sf /usr/bin/python3.12 /usr/bin/python && \
    ln -sf /usr/bin/python3.12 /usr/bin/python3 && \
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
        software-properties-common \
        curl \
        unzip \
        git && \
    apt-get autoremove -y && \
    apt-get clean && \
    ldconfig && \
    rm -rf /var/lib/apt/lists/* /tmp/*

# 2. Stemgen cli.py patchen
RUN python3.12 - <<'PY'
from pathlib import Path
path = Path("/opt/stemgen/stemgen/cli.py")
text = path.read_text()
text = text.replace("subprocess.run(stem_args)", "subprocess.run(stem_args, check=True)")
text = text.replace("        subprocess.run(cmd)\n", "        subprocess.run(cmd, check=True)\n")
path.write_text(text)
print("Stemgen cli.py wurde gepatcht.")
PY

# 3. encode_stems.py auf Linux-Pfade anpassen
RUN python3.12 - <<'PY'
from pathlib import Path
path = Path("/opt/engine-dj-stems-research/encode_stems.py")
text = path.read_text()
text = text.replace('FFMPEG4 = "/opt/homebrew/opt/ffmpeg@4/bin/ffmpeg"', 'FFMPEG4 = "ffmpeg"')
text = text.replace("/opt/homebrew/opt/ffmpeg@4/bin/ffmpeg", "ffmpeg")
path.write_text(text)
print("encode_stems.py wurde auf Linux-Pfade angepasst.")
PY

# 4. PyTorch 2.7.1 für Blackwell installieren (CUDA 12.8)
# PEP 668: Entfernt die "externally-managed"-Sperre für Container-Builds
RUN rm -f /usr/lib/python3.12/EXTERNALLY-MANAGED && \
    ENV PIP_BREAK_SYSTEM_PACKAGES=1 && \
    python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir \
        torch==2.7.1 \
        torchaudio==2.7.1 \
        --index-url https://download.pytorch.org/whl/cu128

# 5. Weitere Abhängigkeiten installieren
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt pycryptodome

# 6. Verifikation, dass PyTorch und CUDA korrekt sind
RUN python - <<'PY'
import torch
print("PyTorch Version:", torch.__version__)
print("CUDA Version:", torch.version.cuda)
print("CUDA verfügbar:", torch.cuda.is_available())
print("Unterstützte Architekturen:", torch.cuda.get_arch_list())
PY

# 7. Verzeichnisse vorbereiten
RUN mkdir -p /opt/app-defaults /workspace/code /workspace/cache /workspace/cache/torch /workspace/jobs /workspace/rclone

# 8. App-Dateien kopieren
COPY app.py /opt/app-defaults/app.py
COPY start.sh /opt/app-defaults/start.sh
COPY start.sh /start.sh
RUN chmod +x /start.sh /opt/app-defaults/start.sh

EXPOSE 7860
CMD ["/start.sh"]