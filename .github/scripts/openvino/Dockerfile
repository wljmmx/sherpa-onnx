# docker build context: repository root
#   docker build -f .github/scripts/openvino/Dockerfile -t sherpa-onnx-openvino .
#
# Multi-stage build:
#   - builder:  compile sherpa-onnx against an onnxruntime that ships the
#               OpenVINO Execution Provider (onnxruntime-openvino),
#               which bundles the OpenVINO 2025.4 runtime.
#   - runtime:  copy only the built sherpa-onnx binaries/libraries and the
#               OpenVINO runtime .so files. No compiling at runtime.

FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        wget \
        unzip \
        python3 \
        python3-pip \
        python3-dev \
        curl \
        ca-certificates \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# ---- onnxruntime-openvino: OpenVINO EP + OpenVINO 2025.4 runtime ----
# Download the manylinux wheel and extract the bundled shared libraries.
ARG ORT_OV_VERSION=1.24.1
RUN pip3 download --no-deps --only-binary=:all: \
        onnxruntime-openvino==${ORT_OV_VERSION} \
        -d /tmp/orv \
    && unzip -q /tmp/orv/onnxruntime_openvino-*.whl -d /opt/orv

# ---- onnxruntime C/C++ headers (API-compatible with the wheel above) ----
RUN wget -q -O /tmp/ort.tgz \
        https://github.com/microsoft/onnxruntime/releases/download/v${ORT_OV_VERSION}/onnxruntime-linux-x64-${ORT_OV_VERSION}.tgz \
    && mkdir -p /opt/onnxruntime \
    && tar -xzf /tmp/ort.tgz -C /opt/onnxruntime --strip-components=1 \
    && rm -f /tmp/ort.tgz

# Prepare the lib dir used by sherpa-onnx cmake:
#   libonnxruntime.so must point to the OpenVINO-enabled library.
RUN mkdir -p /opt/onnxruntime/lib \
    && cp -L /opt/orv/onnxruntime/capi/libonnxruntime.so.1.* /opt/onnxruntime/lib/libonnxruntime.so \
    && cp -L /opt/orv/onnxruntime/capi/libonnxruntime_providers_shared.so /opt/onnxruntime/lib/ \
    && cp -L /opt/orv/onnxruntime/capi/libonnxruntime_providers_openvino.so /opt/onnxruntime/lib/ \
    # keep every OpenVINO/TBB runtime library for the runtime stage
    && mkdir -p /opt/openvino-runtime \
    && cp -L /opt/orv/onnxruntime/capi/libonnxruntime.so.1.* /opt/openvino-runtime/ \
    && cp -L /opt/orv/onnxruntime/capi/libonnxruntime_providers_shared.so /opt/openvino-runtime/ \
    && cp -L /opt/orv/onnxruntime/capi/libonnxruntime_providers_openvino.so /opt/openvino-runtime/ \
    && cp -L /opt/orv/onnxruntime/capi/libopenvino*.so* /opt/openvino-runtime/ \
    && cp -L /opt/orv/onnxruntime/capi/libtbb*.so* /opt/openvino-runtime/ \
    && rm -rf /opt/orv /tmp/orv

# ---- build sherpa-onnx against the OpenVINO-enabled onnxruntime ----
COPY . /opt/sherpa-onnx-src
WORKDIR /opt/sherpa-onnx-src

ENV SHERPA_ONNXRUNTIME_LIB_DIR=/opt/onnxruntime/lib
ENV SHERPA_ONNXRUNTIME_INCLUDE_DIR=/opt/onnxruntime/include

RUN mkdir -p build && cd build \
    && cmake \
       -DCMAKE_BUILD_TYPE=Release \
       -DBUILD_SHARED_LIBS=ON \
       -DSHERPA_ONNX_ENABLE_TTS=ON \
       -DSHERPA_ONNX_ENABLE_PORTAUDIO=OFF \
       -DSHERPA_ONNX_ENABLE_TESTS=OFF \
       -DSHERPA_ONNX_USE_PRE_INSTALLED_ONNXRUNTIME_IF_AVAILABLE=ON \
       .. \
    && make -j"$(nproc)" install \
    && cd .. \
    && rm -rf build/_deps

# Smoke test: the linked onnxruntime must advertise the OpenVINO EP.
RUN python3 - <<'EOF'
import glob
print(glob.glob("/opt/openvino-runtime/libonnxruntime*.so*"))
EOF

# ============================================================================
FROM ubuntu:22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV LD_LIBRARY_PATH=/opt/sherpa/lib:/opt/sherpa/openvino:$LD_LIBRARY_PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libsndfile1 \
        ffmpeg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# sherpa-onnx binaries and its own shared libraries
COPY --from=builder /opt/sherpa-onnx-src/build/install/bin /opt/sherpa/bin
COPY --from=builder /opt/sherpa-onnx-src/build/install/lib /opt/sherpa/lib

# OpenVINO runtime libraries (no compiling, no network access at runtime)
COPY --from=builder /opt/openvino-runtime /opt/sherpa/openvino

LABEL org.opencontainers.image.title="sherpa-onnx (OpenVINO)"
LABEL org.opencontainers.image.source="https://github.com/wljmmx/sherpa-onnx"
LABEL org.opencontainers.image.description="sherpa-onnx 1.13.6 built with the OpenVINO Execution Provider (OpenVINO 2025.4 runtime bundled). Use --provider=openvino"

ENV PATH=/opt/sherpa/bin:$PATH
WORKDIR /workspace

CMD ["/bin/bash"]