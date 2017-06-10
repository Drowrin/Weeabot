from os import path
from kyoukai import Blueprint
from . import templates

base = Blueprint('base')


@base.route('/')
async def root(ctx):
    return await templates.render('index.html', ctx), 200, {"Content-Type": "text/html; charset=utf-8"}

img = Blueprint('img', prefix='/img')
base.add_child(img)


@img.route('/d/<name>')
async def image_direct(_, name):
    with open(path.join('images', name), 'rb') as f:
        return f.read()
