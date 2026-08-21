import asyncio
import os
from dataclasses import dataclass
from typing import cast
import logging
import whisper


WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_WORKERS = max(1, int(os.getenv("WHISPER_WORKERS", "2")))


@dataclass
class WhisperWorker:
    """One independent Whisper model instance reserved by one request at a time."""

    worker_id: int
    model_name: str
    model: whisper.model.Whisper | None = None

    def _ensure_model(self) -> whisper.model.Whisper:
        if self.model is None:
            logging.warning(
                "WHISPER worker=%d loading model=%s",
                self.worker_id,
                self.model_name,
            )

            self.model = whisper.load_model(self.model_name)

            logging.warning(
                "WHISPER worker=%d model ready",
                self.worker_id,
            )

        return self.model

    def _transcribe_sync(self, audio_file: str) -> str:
        model = self._ensure_model()
        result = model.transcribe(
            audio_file,
            language="en",
            temperature=0.0,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            logprob_threshold=-1.0,
            word_timestamps=False,
        )
        return cast(str, result["text"]).strip()

    async def transcribe(self, audio_file: str) -> str:
        # Whisper/PyTorch is blocking. Move it away from FastAPI's event loop.
        return await asyncio.to_thread(self._transcribe_sync, audio_file)


class CustomWhisper:
    """Pool of independent Whisper workers with an asyncio waiting queue."""

    def __init__(self, workers: int, model_name: str) -> None:
        self.workers = workers
        self.model_name = model_name
        self._available: asyncio.Queue[WhisperWorker] | None = None
        self._init_lock = asyncio.Lock()
        self.active_transcriptions = 0
        self.waiting_transcriptions = 0

    async def _get_queue(self) -> asyncio.Queue[WhisperWorker]:
        # asyncio objects are initialized lazily inside the running event loop.
        if self._available is None:
            async with self._init_lock:
                if self._available is None:
                    queue: asyncio.Queue[WhisperWorker] = asyncio.Queue(
                        maxsize=self.workers
                    )
                    for worker_id in range(self.workers):
                        queue.put_nowait(
                            WhisperWorker(worker_id, self.model_name)
                        )
                    self._available = queue
        return self._available

    async def transcribe(self, audio_file: str) -> str:
        queue = await self._get_queue()
        self.waiting_transcriptions += 1
        worker = await queue.get()
        self.waiting_transcriptions -= 1
        self.active_transcriptions += 1

        try:
            return await worker.transcribe(audio_file)
        finally:
            self.active_transcriptions -= 1
            queue.put_nowait(worker)

    async def warmup(self) -> None:
        """Load every Whisper model before accepting Reading requests."""

        queue = await self._get_queue()

        logging.warning(
            "WHISPER warmup starting workers=%d model=%s",
            self.workers,
            self.model_name,
        )

        loaded_workers = []

        while not queue.empty():
            worker = queue.get_nowait()
            loaded_workers.append(worker)

        try:
            # Load sequentially to avoid concurrent model downloads/initialization.
            for worker in loaded_workers:
                await asyncio.to_thread(worker._ensure_model)
        finally:
            for worker in loaded_workers:
                queue.put_nowait(worker)

        logging.warning(
            "WHISPER warmup complete workers=%d model=%s",
            self.workers,
            self.model_name,
        )

    def stats(self) -> dict[str, int | str]:
        return {
            "workers": self.workers,
            "model": self.model_name,
            "active": self.active_transcriptions,
            "waiting": self.waiting_transcriptions,
        }


custom_whisper = CustomWhisper(WHISPER_WORKERS, WHISPER_MODEL)
