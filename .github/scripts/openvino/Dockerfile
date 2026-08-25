# docker build context: repository root
#   docker build -f .github/scripts/openvino/Dockerfile -t sherpa-onnx-openvino .
#
# Multi-stage build:
#   - builder:  compile sherpa-onnx against an onnxruntime that ships the
#               OpenVINO Execution Provider (onnxruntime-openvino wheel),
#               which bundles the OpenVINO 2025.4 runtime.
#   - runtime:  copy only the built sherpa-onnx binaries/libraries and the
#               OpenVINO runtime .so files. No compiling at runtime, no
#               network access at runtime.
#
# Note on the requested "-DSHERPA_ONNX_ENABLE_OPENVINO=ON":
#   sherpa-onnx 1.13.6 has no such CMake option. The OpenVINO backend is
#   provided by linking sherpa-onnx against the onnxruntime-openvino package
#   (the official Intel OpenVINO EP build of onnxruntime), and the OpenVINO
#   runtime itself is downloaded (as part of that wheel) inside the builder.

FROM ubuntu:24.04 AS builder

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
# ubuntu:24.04 ships python3.12, matching the cp312 wheel. The explicit
# --python-version/--platform flags keep the download deterministic.
ARG ORT_OV_VERSION=1.24.1
RUN pip3 download --no-deps --only-binary=:all: \
        --python-version 3.12 \
        --platform manylinux_2_28_x86_64 \
        --implementation cp \
        --abi cp312 \
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
    # the wheel's libonnxruntime SONAME is libonnxruntime.so.1 (see "readelf -d"):
    # the runtime image needs that name for the dynamic loader.
    && ln -sv libonnxruntime.so.${ORT_OV_VERSION} /opt/openvino-runtime/libonnxruntime.so.1 \
    && rm -rf /opt/orv /tmp/orv

# ---- build sherpa-onnx against the OpenVINO-enabled onnxruntime ----
COPY . /opt/sherpa-onnx-src
WORKDIR /opt/sherpa-onnx-src

ENV SHERPA_ONNXRUNTIME_LIB_DIR=/opt/onnxruntime/lib
ENV SHERPA_ONNXRUNTIME_INCLUDE_DIR=/opt/onnxruntime/include

RUN mkdir -p build && cd build \
    && cmake \
       -DCMAKE_BUILD_TYPE=Release \
       -DCMAKE_INSTALL_PREFIX=/opt/sherpa-onnx-src/build/install \
       -DBUILD_SHARED_LIBS=ON \
       -DSHERPA_ONNX_ENABLE_TTS=ON \
       -DSHERPA_ONNX_ENABLE_PORTAUDIO=OFF \
       -DSHERPA_ONNX_ENABLE_TESTS=OFF \
       -DSHERPA_ONNX_USE_PRE_INSTALLED_ONNXRUNTIME_IF_AVAILABLE=ON \
       .. \
    && make -j"$(nproc)" install \
    && rm -rf build/_deps

# Smoke test: the built sherpa libs must resolve libonnxruntime and the
# OpenVINO provider library must have been staged for the runtime image.
RUN set -eux; \
    ls /opt/sherpa-onnx-src/build/install/bin | head -20; \
    echo "--- linked onnxruntime ---"; \
    ldd /opt/sherpa-onnx-src/build/install/lib/*.so* 2>/dev/null | grep -Eo "libonnxruntime\.so\.[0-9.]+" | sort -u; \
    echo "--- openvino runtime ---"; \
    ls /opt/openvino-runtime/; \
    test -f /opt/openvino-runtime/libonnxruntime.so.1; \
    test -f /opt/openvino-runtime/libonnxruntime_providers_openvino.so; \
    echo "OpenVINO provider lib present"

# ============================================================================
FROM ubuntu:24.04 AS runtime

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
LABEL org.opencontainers.image.description="sherpa-onnx 1.13.6 built with the OpenVINO Execution Provider (OpenVINO 2025.4.1 runtime bundled). Use --provider=openvino"

ENV PATH=/opt/sherpa/bin:$PATH
WORKDIR /workspace

CMD ["/bin/bash"]