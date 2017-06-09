from kyoukai import HTTPRequestContext
from jinja2 import Environment, PackageLoader


environment = Environment(loader=PackageLoader('weeabot', 'web'), enable_async=True)

async def render(template: str, ctx: HTTPRequestContext, **kwargs):
    return await environment.get_template(template).render_async({
        "ctx": ctx,
        "navpages": ctx.bot.config['web']['site']['navpages'],
        **kwargs
    })
