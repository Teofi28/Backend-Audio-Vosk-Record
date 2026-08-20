"""Concurrent load test for POST /api/sentences/audios.

Examples:
  uv run python test_concurrent_tts.py 10
  uv run python test_concurrent_tts.py 20
"""

import asyncio
import sys
import time

import httpx

URL = "http://127.0.0.1:8000/api/sentences/audios"
SENTENCE = "This is a listening concurrency test."


async def send_one(client: httpx.AsyncClient, index: int):
    started = time.perf_counter()
    try:
        # The FastAPI endpoint expects a raw JSON string body.
        response = await client.post(URL, json=SENTENCE, timeout=180.0)
        elapsed = time.perf_counter() - started
        print(f"Request {index:02d}: status={response.status_code} time={elapsed:.2f}s")
        if response.status_code != 200:
            print(f"  detail: {response.text[:300]}")
        return response.status_code
    except Exception as exc:
        elapsed = time.perf_counter() - started
        print(f"Request {index:02d}: ERROR time={elapsed:.2f}s {exc}")
        return 0


async def main():
    count = int(sys.argv[1]) if len(sys.argv) >= 2 else 10
    if count < 1:
        raise SystemExit("COUNT must be >= 1")

    print(f"Sending {count} simultaneous TTS requests...\n")
    started = time.perf_counter()

    limits = httpx.Limits(
        max_connections=count + 5,
        max_keepalive_connections=count + 5,
    )
    async with httpx.AsyncClient(limits=limits) as client:
        statuses = await asyncio.gather(
            *(send_one(client, i) for i in range(1, count + 1))
        )

    total = time.perf_counter() - started
    ok = sum(status == 200 for status in statuses)
    print(f"\nFinished in {total:.2f}s — {ok}/{count} requests returned HTTP 200")
    print("Generated MP3 files remain under static/; the normal frontend deletes them after playback.")


if __name__ == "__main__":
    asyncio.run(main())
