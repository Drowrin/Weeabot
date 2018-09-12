from os import path
from vibora.blueprints import Blueprint
from vibora import Response, Request
from . import templates


base = Blueprint('base')


@base.route('/')
async def root(request: Request):
    return Response(
        await templates.render('index.html', request),
        headers={"content-type": "text/html; charset=utf-8"}
    )


@base.route('/d/<name>')
async def image_direct(_, name):
    with open(path.join('images', name), 'rb') as f:
        return Response(f.read())
