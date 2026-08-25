# sherpa-onnx runtime image (Linux x64)
#
# The image is built on GitHub Actions (ubuntu-latest, linux/amd64)
# and published to GHCR as ghcr.io/<owner>/sherpa-onnx:1.13.6
#
# It provides both the Python API (sherpa-onnx==1.13.6) and the
# core runtime dependencies (ffmpeg, libsndfile) plus the prebuilt
# onnxruntime binaries shipped inside the pip wheel.

FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# ffmpeg is required by some examples (e.g. non_streaming_server.py)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        wget \
    && rm -rf /var/lib/apt/lists/*

# Pin to sherpa-onnx 1.13.6
RUN pip install --no-cache-dir sherpa-onnx==1.13.6

WORKDIR /workspace

# Smoke test: verify the exact version is importable
RUN python -c "import sherpa_onnx; print('sherpa-onnx', sherpa_onnx.__version__)"

CMD ["python", "-c", "import sherpa_onnx; print('sherpa-onnx', sherpa_onnx.__version__)"]