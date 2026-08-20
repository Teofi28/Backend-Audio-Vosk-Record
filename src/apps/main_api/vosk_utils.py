import asyncio
import json
import os
import wave
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from vosk import KaldiRecognizer, Model


VOSK_WORKERS = max(1, int(os.getenv("VOSK_WORKERS", "4")))
_vosk_executor = ThreadPoolExecutor(
    max_workers=VOSK_WORKERS,
    thread_name_prefix="vosk-worker",
)


@lru_cache(maxsize=2)
def get_vosk_model(model_path: str) -> Model:
    """Load a Vosk model once per backend process and reuse it."""
    return Model(model_path)


def _transcribe_wav_sync(audio_file: str, model_path: str) -> str:
    """Blocking Vosk transcription executed inside the dedicated pool."""
    model = get_vosk_model(model_path)

    with wave.open(audio_file, "rb") as wave_file:
        recognizer = KaldiRecognizer(model, wave_file.getframerate())
        parts: list[str] = []

        while True:
            data = wave_file.readframes(4000)
            if not data:
                break

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    parts.append(text)

        final_result = json.loads(recognizer.FinalResult())
        final_text = final_result.get("text", "").strip()
        if final_text:
            parts.append(final_text)

    return " ".join(parts).strip()


class VoskPool:
    """Bounded Vosk pool: shared model, separate recognizer per request."""

    def __init__(self, workers: int) -> None:
        self.workers = workers
        self._available: asyncio.Queue[int] | None = None
        self._init_lock = asyncio.Lock()
        self.active_transcriptions = 0
        self.waiting_transcriptions = 0

    async def _get_queue(self) -> asyncio.Queue[int]:
        if self._available is None:
            async with self._init_lock:
                if self._available is None:
                    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=self.workers)
                    for worker_id in range(self.workers):
                        queue.put_nowait(worker_id)
                    self._available = queue
        return self._available

    async def transcribe(self, audio_file: str, model_path: str) -> str:
        queue = await self._get_queue()
        self.waiting_transcriptions += 1
        worker_id = await queue.get()
        self.waiting_transcriptions -= 1
        self.active_transcriptions += 1

        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                _vosk_executor,
                _transcribe_wav_sync,
                audio_file,
                model_path,
            )
        finally:
            self.active_transcriptions -= 1
            queue.put_nowait(worker_id)

    def stats(self) -> dict[str, int]:
        return {
            "workers": self.workers,
            "active": self.active_transcriptions,
            "waiting": self.waiting_transcriptions,
        }


vosk_pool = VoskPool(VOSK_WORKERS)


async def transcribe_wav(audio_file: str, model_path: str) -> str:
    return await vosk_pool.transcribe(audio_file, model_path)


def get_vosk_stats() -> dict[str, int]:
    return vosk_pool.stats()
