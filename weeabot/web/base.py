from os import path
from vibora.blueprints import Blueprint
from vibora import Response, Request
from weeabot.core.bot import Weeabot
from . import templates


base = Blueprint('base')


@base.route('/')
async def root(request: Request, bot: Weeabot):
    return Response(
        await templates.render('index.html', request, bot),
        headers={"content-type": "text/html; charset=utf-8"}
    )


@base.route('/d/<name>')
async def image_direct(name: str):
    with open(path.join('images', name), 'rb') as f:
        return Response(f.read())
