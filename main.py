import logging
import time
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.apps.main_api import sub_app
from src.apps.main_api.tts_utils import TTS_WORKERS
from src.apps.main_api.vosk_utils import VOSK_WORKERS
from src.apps.main_api.whisper_utils import (
    WHISPER_MODEL,
    WHISPER_WORKERS,
    custom_whisper,
)

app = FastAPI()


@app.on_event("startup")
async def log_worker_configuration() -> None:
    logging.info("TTS pool workers=%d", TTS_WORKERS)
    logging.info("VOSK pool workers=%d", VOSK_WORKERS)
    logging.info(
        "WHISPER pool workers=%d model=%s",
        WHISPER_WORKERS,
        WHISPER_MODEL,
    )

    await custom_whisper.warmup()

@app.get("/debug-whisper")
async def debug_whisper():
    audio = "377422cb-b41f-4f0b-ba6c-0a399675e8d9.wav"

    t = time.perf_counter()
    text = await custom_whisper.transcribe(audio)
    elapsed = time.perf_counter() - t

    return {
        "seconds": round(elapsed, 2),
        "text": text,
    }

# Listening TTS audio is generated under static/ and the existing frontend
# builds its playback URL from staticUrl + returned /static/... path.
app.mount("/static", StaticFiles(directory="static"), name="static")

# Preserve the API prefix used by local and Heroku configuration.
app.mount("/api", sub_app, name="sub_api")
