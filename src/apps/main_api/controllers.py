import time
import logging
import asyncio
from os import remove
from typing import Annotated
from uuid import uuid4

from fastapi import BackgroundTasks, Body, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse
from openai import OpenAI
from pydantic_extra_types.color import Color

from .analyzer import Analyzer
from .information import Sender
from .setting import SettingDepends
from .whisper_utils import custom_whisper
from .vosk_utils import transcribe_wav
from .tts_utils import generate_tts

from .dtos import (
    AnalyzeBody,
    ContactBody,
    OpinionForm,
    ResultItem,
)
from .files import MethodType


async def sentences(method: MethodType, setting: SettingDepends):
    if method == "listening":
        filename = setting.listening_filename
    elif method == "speaking":
        filename = setting.speaking_filename
    elif method == "reading":
        filename = setting.reading_filename

    with open(filename, "r") as f:
        return f.readlines()


async def audio(sentence: Annotated[str, Body()]):
    name_song = "static/" + str(uuid4()) + ".mp3"

    # edge-tts is protected by its own bounded semaphore. If many Listening
    # users request audio at once, only TTS_WORKERS generations run
    # simultaneously and the remaining requests wait asynchronously.
    try:
        await generate_tts(sentence, name_song)
    except Exception as exc:
        try:
            remove(name_song)
        except FileNotFoundError:
            pass
        raise HTTPException(
            status_code=502,
            detail=f"TTS generation failed: {str(exc)[-500:]}",
        ) from exc

    return "/" + name_song


async def delete_song(filename: Annotated[str, Body()]):
    remove("static/" + filename)
    return {}


async def analyze_audio(
    expected: Annotated[str, Form()],
    method: Annotated[MethodType, Form()],
    audio: Annotated[UploadFile, Form()],
    settings: SettingDepends,
):
    name = str(uuid4()) + ".webm"
    output = str(uuid4()) + ".wav"
    
    try:
        with open(name, "wb") as f:
            f.write(await audio.read())
        t0 = time.perf_counter()
        # Normalize every browser recording to the WAV format expected by the
        # speech-recognition engines. Mono/16 kHz is a good Vosk input format
        # and Whisper can read it without any special handling.
        ffmpeg = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            name,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-af",
            (
                "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.3"
                ":stop_periods=-1:stop_threshold=-45dB:stop_silence=0.5"
            ),
            output,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await ffmpeg.communicate()
        logging.warning(
            "TIMING FFMPEG %.2fs",
            time.perf_counter() - t0,
        )
        if ffmpeg.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"Audio conversion failed: {stderr.decode(errors='replace')[-500:]}",
            )

        # Medir duración real del WAV que recibirá Whisper
        probe = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            output,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        stdout, _ = await probe.communicate()

        logging.warning(
            "TIMING AUDIO DURATION %ss",
            stdout.decode().strip(),
        )

        # Reading keeps the existing Whisper path. Listening and Speaking use
        # Vosk, but the response format remains identical for the frontend.
        if method == "reading":
            t0 = time.perf_counter()
            logging.warning("TIMING WHISPER START")
            actual = await custom_whisper.transcribe(output)
            logging.warning(
                "TIMING WHISPER END %.2fs",
                time.perf_counter() - t0,
            )
        else:
            actual = await transcribe_wav(output, settings.model_name)

        t0 = time.perf_counter()

        logging.warning("TIMING ANALYZE/OPENAI START")

        result = await analyze_paragraph(
            AnalyzeBody(expected=expected, actual=actual, method=method),
            settings,
        )

        logging.warning(
            "TIMING ANALYZE/OPENAI END %.2fs",
            time.perf_counter() - t0,
        )

        return result

    finally:
        # Never leave user recordings behind, even if ffmpeg or recognition
        # raises an exception.
        for filename in (name, output):
            try:
                remove(filename)
            except FileNotFoundError:
                pass


async def analyze_paragraph(body: AnalyzeBody, setting: SettingDepends):
    if body.method == "reading":
        def evaluate_reading() -> str:
            client = OpenAI(api_key=setting.openai_key)
            return client.responses.create(
                model="gpt-4o",
                instructions="developer",
                input=setting.input_openai.format(body.actual, body.expected),
            ).output_text

        # The OpenAI SDK call is synchronous; keep it off the FastAPI event loop.
        result = await asyncio.to_thread(evaluate_reading)
        return [ResultItem(text=result, color=Color("#FF0000"))]
    response = []
    response.append(ResultItem(text="\nEvaluating phrase:", color=Color("white")))
    response.append(
        ResultItem(text=f"\nPronounced phrase: {body.actual}", color=Color("white"))
    )
    response.append(
        ResultItem(text=f"\nExpected phrase: {body.expected}", color=Color("white"))
    )
    analyzer = Analyzer()
    expected_phonemes = analyzer.get_phonemes_from_speak(body.expected)
    actual_phonemes = analyzer.get_phonemes_from_speak(body.actual)
    response.append(
        ResultItem(
            text=f"\nExpected phonemes: {'.'.join(expected_phonemes)}",
            color=Color("white"),
        )
    )
    response.append(
        ResultItem(
            text=f"\nDetected phonemes: {'.'.join(actual_phonemes)}\n",
            color=Color("white"),
        )
    )

    results, phonetic_score = analyzer.compare_phonemes(
        expected_phonemes, actual_phonemes
    )
    response.extend(results)
    response.append(
        ResultItem(
            text=f"\n\nPronunciation accuracy: {phonetic_score:.2f}\n",
            color=Color("white"),
        )
    )
    response.append(
        ResultItem(
            text=f"{phonetic_score:.2f}",
            color=Color("#000000"),
        )
    )

    return response


def post_contact(
    body: Annotated[ContactBody, Form()],
    sender: Annotated[Sender, Depends()],
    background_tasks: BackgroundTasks,
):
    message_as_list = ["<html>"]
    message_as_list.append("<body>")
    message_as_list.append("<table>")
    message_as_list.append("<thead>")
    message_as_list.append("<th>Name</th>")
    message_as_list.append("<th>LastName</th>")
    message_as_list.append("<th>Email</th>")
    message_as_list.append("<th>Observation</th>")
    message_as_list.append("</thead>")
    message_as_list.append("</tbody><tr>")

    for value in body.model_dump().values():
        message_as_list.append(f"<td>{value}</td>")

    message_as_list.append("</tr></tbody>")

    background_tasks.add_task(sender.send, "".join(message_as_list))
    return RedirectResponse("/", status.HTTP_302_FOUND)


def post_opinion(
    body: Annotated[OpinionForm, Form()],
    sender: Annotated[Sender, Depends()],
    background_tasks: BackgroundTasks,
):
    body_as_dict = body.model_dump()

    message_as_list = ["<html>"]
    message_as_list.append("<body>")
    message_as_list.append("<table>")
    message_as_list.append("<thead>")
    for key in body_as_dict.keys():
        message_as_list.append(f"<th>{key}</th>")
    message_as_list.append("</thead>")
    message_as_list.append("</tbody><tr>")

    for value in body_as_dict.values():
        message_as_list.append(f"<td>{value}</td>")

    message_as_list.append("</tr></tbody>")

    background_tasks.add_task(sender.send, "".join(message_as_list), "OPINION")
    return RedirectResponse("/", status.HTTP_302_FOUND)
