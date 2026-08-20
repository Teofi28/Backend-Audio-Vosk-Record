"""Concurrent load test for the /api/analyzers/files endpoint.

Examples:
  python test_concurrent_audio.py sample.webm speaking 20
  python test_concurrent_audio.py sample.webm listening 20
  python test_concurrent_audio.py sample.webm reading 10
"""

import asyncio
import sys
import time
from pathlib import Path

import httpx

URL = "http://127.0.0.1:8000/api/analyzers/files"


async def send_one(client: httpx.AsyncClient, audio_path: Path, method: str, index: int):
    started = time.perf_counter()
    audio_bytes = audio_path.read_bytes()
    files = {"audio": (audio_path.name, audio_bytes, "audio/webm")}
    data = {
        "expected": "This is a concurrency test sentence.",
        "method": method,
    }

    try:
        response = await client.post(URL, data=data, files=files, timeout=180.0)
        elapsed = time.perf_counter() - started
        print(f"Request {index:02d}: status={response.status_code} time={elapsed:.2f}s")
        return response.status_code
    except Exception as exc:
        elapsed = time.perf_counter() - started
        print(f"Request {index:02d}: ERROR time={elapsed:.2f}s {exc}")
        return 0


async def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python test_concurrent_audio.py AUDIO [speaking|listening|reading] [COUNT]")

    audio_path = Path(sys.argv[1])
    method = sys.argv[2] if len(sys.argv) >= 3 else "speaking"
    count = int(sys.argv[3]) if len(sys.argv) >= 4 else 10

    if method not in {"speaking", "listening", "reading"}:
        raise SystemExit("method must be speaking, listening, or reading")
    if not audio_path.exists():
        raise SystemExit(f"Audio file not found: {audio_path}")

    print(f"Sending {count} simultaneous {method} requests...\n")
    started = time.perf_counter()

    limits = httpx.Limits(max_connections=count + 5, max_keepalive_connections=count + 5)
    async with httpx.AsyncClient(limits=limits) as client:
        statuses = await asyncio.gather(
            *(send_one(client, audio_path, method, i) for i in range(1, count + 1))
        )

    total = time.perf_counter() - started
    ok = sum(status == 200 for status in statuses)
    print(f"\nFinished in {total:.2f}s — {ok}/{count} requests returned HTTP 200")


if __name__ == "__main__":
    asyncio.run(main())
