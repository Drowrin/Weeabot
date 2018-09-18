from os import path
from quart import Blueprint, Response, g, render_template, send_file


base = Blueprint('base', __name__)


@base.route('/')
async def root():
    return await render_template('index.html')


@base.route('/img/d/<name>')
async def image_direct(name: str):
    return send_file(path.join('images', name))


def register(bot):
    bot.web.register_blueprint(base)
