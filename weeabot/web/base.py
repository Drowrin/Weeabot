from kyoukai import Blueprint
from . import templates

base = Blueprint('base')


@base.route('/')
async def root(ctx):
    return await templates.render('index.html', ctx), 200, {"Content-Type": "text/html; charset=utf-8"}
