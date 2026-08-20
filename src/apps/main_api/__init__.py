from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse

from src.templates import contact, index, opinion, tester, tutorial
from .setting import get_setting

from .controllers import (
    post_opinion,
    sentences,
    analyze_paragraph,
    analyze_audio,
    post_contact,
    audio,
    delete_song,
)
from .dtos import ResultItem

sub_app = FastAPI()
origins = get_setting().origins
sub_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


sub_app.add_api_route(
    "/sentences", sentences, methods=["GET"], response_model=list[str]
)
sub_app.add_api_route("/sentences/audios", audio, methods=["POST"], response_model=str)
sub_app.add_api_route("/sentences/audios", delete_song, methods=["DELETE"])
sub_app.add_api_route(
    "/analyzers", analyze_paragraph, methods=["POST"], response_model=list[ResultItem]
)
sub_app.add_api_route(
    "/analyzers/files",
    analyze_audio,
    methods=["POST"],
    response_model=list[ResultItem],
)
sub_app.add_api_route(
    "/contact", post_contact, methods=["POST"], response_class=RedirectResponse
)

sub_app.add_api_route(
    "/opinion", post_opinion, methods=["POST"], response_class=RedirectResponse
)

sub_app.add_api_route("/", index, methods=["GET"], response_class=HTMLResponse)
sub_app.add_api_route("/tester", tester, methods=["GET"], response_class=HTMLResponse)
sub_app.add_api_route(
    "/tutorial", tutorial, methods=["GET"], response_class=HTMLResponse
)
sub_app.add_api_route("/contact", contact, methods=["GET"], response_class=HTMLResponse)
sub_app.add_api_route("/opinion", opinion, methods=["GET"], response_class=HTMLResponse)
