import asyncio
import logging
import os
from pathlib import Path


TTS_WORKERS = max(1, int(os.getenv("TTS_WORKERS", "4")))


class TTSPool:
    """Limit concurrent edge-tts subprocesses.

    edge-tts is network-bound, so an asyncio.Semaphore is enough here: it
    prevents a burst of users from opening an unlimited number of simultaneous
    WebSocket sessions to Microsoft's service while keeping FastAPI's event
    loop free for other requests.
    """

    def __init__(self, workers: int) -> None:
        self.workers = workers
        self._semaphore: asyncio.Semaphore | None = None
        self._init_lock = asyncio.Lock()
        self.active_generations = 0
        self.waiting_generations = 0

    async def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            async with self._init_lock:
                if self._semaphore is None:
                    self._semaphore = asyncio.Semaphore(self.workers)
        return self._semaphore

    def stats(self) -> dict[str, int]:
        return {
            "workers": self.workers,
            "active": self.active_generations,
            "waiting": self.waiting_generations,
        }


async def _generate_with_counters(
    pool: TTSPool, text: str, output_path: str, voice: str | None = None
) -> None:
    semaphore = await pool._get_semaphore()
    pool.waiting_generations += 1
    acquired = False
    try:
        await semaphore.acquire()
        acquired = True
        pool.waiting_generations -= 1
        pool.active_generations += 1
        logging.info(
            "TTS active=%d/%d waiting=%d",
            pool.active_generations,
            pool.workers,
            pool.waiting_generations,
        )

        command = ["edge-tts", "--text", text]
        if voice:
            command.extend(["--voice", voice])
        command.extend(["--write-media", output_path])

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(
                "edge-tts failed: " + stderr.decode(errors="replace")[-1000:]
            )

        output = Path(output_path)
        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError("edge-tts finished without creating a valid MP3")
    finally:
        if acquired:
            pool.active_generations -= 1
            semaphore.release()
            logging.info(
                "TTS finished active=%d/%d waiting=%d",
                pool.active_generations,
                pool.workers,
                pool.waiting_generations,
            )
        else:
            pool.waiting_generations -= 1


tts_pool = TTSPool(TTS_WORKERS)


async def generate_tts(text: str, output_path: str, voice: str | None = None) -> None:
    await _generate_with_counters(tts_pool, text, output_path, voice)


def get_tts_stats() -> dict[str, int]:
    return tts_pool.stats()
