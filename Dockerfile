FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DENO_INSTALL=/opt/deno \
    PATH="/opt/deno/bin:${PATH}" \
    TORCH_HOME=/workspace/cache/torch \
    XDG_CACHE_HOME=/workspace/cache

# Runtime-Pakete installieren, Stemgen klonen und Deno installieren
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        rclone \
        sox \
        gpac \
        curl \
        unzip \
        git && \
    git clone --depth 1 \
        https://github.com/axeldelafosse/stemgen.git \
        /opt/stemgen && \
    curl -fsSL https://deno.land/install.sh | sh && \
    test -x /opt/deno/bin/deno && \
    /opt/deno/bin/deno --version && \
    apt-get purge -y \
        curl \
        unzip \
        git && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf \
        /var/lib/apt/lists/* \
        /tmp/*

# Python-Abhängigkeiten installieren
RUN python -m pip install --no-cache-dir \
        demucs \
        gradio \
        yt-dlp \
        mutagen \
        "Lossless-BS-RoFormer" 

# Python-Installation prüfen
RUN python - <<'PY'
import torch
import demucs
import gradio
import yt_dlp

print("Torch:", torch.__version__)
print("CUDA verfügbar:", torch.cuda.is_available())
print("Demucs:", demucs.__file__)
print("Gradio:", gradio.__version__)
print("yt-dlp:", yt_dlp.version.__version__)

try:
    import bs_roformer
    print("BS-RoFormer:", bs_roformer.__file__)
except ImportError as exc:
    print("BS-RoFormer nicht importierbar:", exc)
    raise
PY

# Deno und yt-dlp prüfen
RUN deno --version && \
    yt-dlp --version

WORKDIR /workspace

COPY app.py /workspace/app.py
COPY start.sh /start.sh

RUN chmod +x /start.sh && \
    mkdir -p \
        /workspace/cache/torch \
        /workspace/cache \
        /workspace/jobs

EXPOSE 7860

CMD ["/start.sh"]