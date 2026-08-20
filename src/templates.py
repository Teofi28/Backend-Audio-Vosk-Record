from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


async def tester(request: Request):
    return templates.TemplateResponse(request, "tester.html")


async def tutorial(request: Request):
    return templates.TemplateResponse(request, "tutorial.html")


async def contact(request: Request):
    return templates.TemplateResponse(request, "contact.html")


async def opinion(request: Request):
    return templates.TemplateResponse(request, "opinion.html")
