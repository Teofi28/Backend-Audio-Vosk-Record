crear entorno virtual con : uv sync --frozen
uv run --env-file .env --no-sync -- uvicorn main:app

ngrok http --domain=ixtream.ngrok.app 8000

## PENDIENTES

- Actualmente el poryecto detecta el silencio con el objetivo de finalizar la grabación para cada proceso, esto se hace en el servidor mediante webrtc y socketio.

  La intención es cambiar esto y que la detección del silencio se haga desde el frontend y quitar webrtc y socketio complementamente del poryecto

  ¡Claro, solo si no se usa en algo más, que hasta el momento no lo hacen!

- Actualmente se usa un método para listar los dispositivos disponible solo en chrome, se debe cambiar esto para que sea multiplataforma

env:
openai_key=pegatuclaveaqui

speaking_filename=cuento.txt

listening_filename=cuento.txt

reading_filename=reading.txt

model_name=vosk-model-small-en-us-0.15

## Multi-user speech processing

The backend uses separate concurrency paths for the two recognition engines:

- **Speaking / Listening (Vosk):** one cached Vosk `Model` per process plus a dedicated `ThreadPoolExecutor`. `VOSK_WORKERS` controls the maximum simultaneous Vosk recognitions; additional jobs wait in the executor queue instead of blocking FastAPI's event loop.
- **Reading (Whisper):** an `asyncio.Queue` of independent Whisper workers. Each worker owns its own model instance and processes only one recording at a time. `WHISPER_WORKERS` controls the number of simultaneous Reading transcriptions and `WHISPER_MODEL` selects the model.
- `ffmpeg`, `edge-tts`, Whisper/PyTorch, and the synchronous OpenAI SDK are kept off the FastAPI event loop.

Recommended starting values for the current workstation are in `.env`:

```env
VOSK_WORKERS=4
WHISPER_WORKERS=2
WHISPER_MODEL=base
```

Tune these values after load testing. Use `test_concurrent_audio.py` with a real browser recording to validate simultaneous requests.
