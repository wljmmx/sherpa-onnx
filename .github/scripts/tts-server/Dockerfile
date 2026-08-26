# sherpa-onnx TTS server image (Python + FastAPI, CPU backend)
#
# Standalone HTTP service exposing POST /tts. Intentionally separate from the
# C++/OpenVINO ASR image so the two do not share runtime dependencies and do
# not compete for CPU resources.
#
# Model files are mounted at runtime or baked in by the caller; configure via
# the SHERPA_TTS_* env vars (see tts_server.py).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# CPU-only stack: standard onnxruntime + sherpa_onnx Python binding + FastAPI.
RUN pip install --upgrade pip && \
    pip install \
        sherpa-onnx \
        onnxruntime \
        numpy \
        fastapi \
        "uvicorn[standard]" \
        pydantic

COPY tts_server.py /opt/tts-server/tts_server.py
WORKDIR /opt/tts-server

# Sanity check that the bindings and web framework import cleanly.
RUN python -c "import sherpa_onnx, fastapi, uvicorn, numpy; print('imports OK')"

ENV SHERPA_TTS_PORT=9100
EXPOSE 9100

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9100/health')" || exit 1

CMD ["python", "-m", "uvicorn", "tts_server:app", "--host", "0.0.0.0", "--port", "9100"]