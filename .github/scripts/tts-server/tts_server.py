#!/usr/bin/env python3
# sherpa-onnx TTS HTTP server (FastAPI)
#
# Exposes a POST /tts endpoint that synthesizes speech from text using
# sherpa_onnx.OfflineTts. The model is configured through environment
# variables (so the image stays model-agnostic and models are mounted in as
# a volume or baked-in by the caller).
#
# Request : {"text": "...", "sid": 3, "speed": 1.0}
# Response: audio/wav (PCM 16-bit mono)
#
# Env vars (all optional, sensible defaults):
#   SHERPA_TTS_MODEL        path to model.onnx
#   SHERPA_TTS_TOKENS       path to tokens.txt
#   SHERPA_TTS_LEXICON      path to lexicon.txt (optional)
#   SHERPA_TTS_DATA_DIR     path to VITS `data` dir (optional)
#   SHERPA_TTS_DICT_DIR     path to `dict` dir (optional)
#   SHERPA_TTS_RULE_FSTS    path to rule.fst (optional)
#   SHERPA_TTS_SID          default speaker id (default 0)
#   SHERPA_TTS_SPEED        default speed factor (default 1.0)
#   SHERPA_TTS_THREADS      intra-op threads (default 2)
#   SHERPA_TTS_MAX_SENTENCES  max sentences per request (default 1)

import io
import os
import wave

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import sherpa_onnx

# ---------------------------------------------------------------------------
# Build the TTS config from environment variables at import time (models are
# loaded once and shared across requests).
# ---------------------------------------------------------------------------


def _build_tts():
    model = os.environ.get("SHERPA_TTS_MODEL", "")
    tokens = os.environ.get("SHERPA_TTS_TOKENS", "")
    lexicon = os.environ.get("SHERPA_TTS_LEXICON", "")
    data_dir = os.environ.get("SHERPA_TTS_DATA_DIR", "")
    dict_dir = os.environ.get("SHERPA_TTS_DICT_DIR", "")
    rule_fsts = os.environ.get("SHERPA_TTS_RULE_FSTS", "")
    threads = int(os.environ.get("SHERPA_TTS_THREADS", "2"))
    max_sentences = int(os.environ.get("SHERPA_TTS_MAX_SENTENCES", "1"))
    default_sid = int(os.environ.get("SHERPA_TTS_SID", "0"))
    default_speed = float(os.environ.get("SHERPA_TTS_SPEED", "1.0"))

    if not model or not tokens:
        raise RuntimeError(
            "SHERPA_TTS_MODEL and SHERPA_TTS_TOKENS must be set "
            "(e.g. -e SHERPA_TTS_MODEL=/models/*.onnx)."
        )

    tts_config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=model,
                tokens=tokens,
                lexicon=lexicon,
                data_dir=data_dir,
                dict_dir=dict_dir,
            ),
            num_threads=threads,
            provider="cpu",
        ),
        rule_fsts=rule_fsts,
        max_num_sentences=max_sentences,
    )

    tts = sherpa_onnx.OfflineTts(tts_config)
    return tts, default_sid, default_speed


try:
    tts, DEFAULT_SID, DEFAULT_SPEED = _build_tts()
    print(
        "TTS server ready: model=%s sid=%d speed=%.2f"
        % (os.environ.get("SHERPA_TTS_MODEL", ""), DEFAULT_SID, DEFAULT_SPEED),
        flush=True,
    )
except Exception as exc:  # model not yet mounted / invalid -> fail on startup
    # Store the error so /health reports unhealthy instead of crashing forever.
    _startup_error = str(exc)
    tts = None
    print("TTS model init FAILED: %s" % _startup_error, flush=True)

app = FastAPI(title="sherpa-onnx TTS server", version="1.13.7")


class TTSRequest(BaseModel):
    text: str
    sid: int | None = None
    speed: float | None = None


@app.get("/health")
def health():
    if tts is None:
        raise HTTPException(status_code=503, detail="TTS model not initialized")
    return {"status": "ok"}


@app.post("/tts")
def synthesize(req: TTSRequest):
    if tts is None:
        raise HTTPException(status_code=503, detail="TTS model not initialized")
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is empty")

    sid = req.sid if req.sid is not None else DEFAULT_SID
    speed = req.speed if req.speed is not None else DEFAULT_SPEED

    try:
        # sherpa-onnx >= 1.9: tts.generate() returns a single GeneratedAudio
        # object (not a (samples, sample_rate) tuple).
        result = tts.generate(text, sid=sid, speed=speed)
        samples = result.samples
        sample_rate = result.sample_rate
    except Exception as exc:
        raise HTTPException(status_code=500, detail="synthesis failed: %s" % exc)

    if samples is None or len(samples) == 0:
        raise HTTPException(status_code=500, detail="synthesis returned no audio")

    samples = np.asarray(samples)
    if np.issubdtype(samples.dtype, np.floating):
        # GeneratedAudio.samples is float32 in [-1, 1]: scale to int16 range.
        samples = np.clip(samples, -1.0, 1.0)
        samples = (samples * 32767).astype(np.int16)
    pcm = samples

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(int(sample_rate))
        wav.writeframes(pcm.tobytes())
    buf.seek(0)

    from fastapi.responses import Response

    return Response(content=buf.read(), media_type="audio/wav")