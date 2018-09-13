from vibora import Request
from jinja2 import Environment, PackageLoader
from ..core.bot import Weeabot


environment = Environment(loader=PackageLoader('weeabot', 'web'), enable_async=True)

async def render(template: str, request: Request, **kwargs):
    bot = request.get_component(Weeabot)
    return await environment.get_template(template).render_async({
        "request": request,
        "navpages": bot.config['web']['site']['navpages'],
        **kwargs
    })
