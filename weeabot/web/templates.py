from vibora import Request
from jinja2 import Environment, PackageLoader
from weeabot.core.bot import Weeabot


environment = Environment(loader=PackageLoader('weeabot', 'web'), enable_async=True)

async def render(template: str, bot: Weeabot, request: Request, **kwargs):
    return await environment.get_template(template).render_async({
        "request": request,
        "navpages": bot.config['web']['site']['navpages'],
        **kwargs
    })
