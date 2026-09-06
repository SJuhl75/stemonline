# Wechsel auf das offizielle PyTorch Base-Image (spart Fehlerquellen!)
FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

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

# 1. Systemabhängigkeiten installieren (ohne Software-Properties-PPA, da Python bereits korrekt ist)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
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
    apt-get purge -y curl unzip git && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/*

# 2. Stemgen cli.py patchen
RUN python - <<'PY'
from pathlib import Path
path = Path("/opt/stemgen/stemgen/cli.py")
text = path.read_text()
text = text.replace("subprocess.run(stem_args)", "subprocess.run(stem_args, check=True)")
text = text.replace("        subprocess.run(cmd)\n", "        subprocess.run(cmd, check=True)\n")
path.write_text(text)
print("Stemgen cli.py wurde gepatcht.")
PY

# 3. encode_stems.py auf Linux-Pfade anpassen
RUN python - <<'PY'
from pathlib import Path
path = Path("/opt/engine-dj-stems-research/encode_stems.py")
text = path.read_text()
text = text.replace('FFMPEG4 = "/opt/homebrew/opt/ffmpeg@4/bin/ffmpeg"', 'FFMPEG4 = "ffmpeg"')
text = text.replace("/opt/homebrew/opt/ffmpeg@4/bin/ffmpeg", "ffmpeg")
path.write_text(text)
print("encode_stems.py wurde auf Linux-Pfade angepasst.")
PY

# 4. Weitere Abhängigkeiten installieren (OHNE torch/torchaudio!)
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt pycryptodome

# 5. Verifikation (PyTorch ist jetzt im Image enthalten)
RUN python - <<'PY'
import torch
print("PyTorch Version:", torch.__version__)
print("CUDA Version:", torch.version.cuda)
print("CUDA verfügbar:", torch.cuda.is_available())
print("Unterstützte Architekturen:", torch.cuda.get_arch_list())
PY

# 6. Verzeichnisse vorbereiten
RUN mkdir -p /opt/app-defaults /workspace/code /workspace/cache /workspace/cache/torch /workspace/jobs /workspace/rclone

# 7. App-Dateien kopieren
COPY app.py /opt/app-defaults/app.py
COPY start.sh /opt/app-defaults/start.sh
COPY start.sh /start.sh
RUN chmod +x /start.sh /opt/app-defaults/start.sh

EXPOSE 7860
CMD ["/start.sh"]