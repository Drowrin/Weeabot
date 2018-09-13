from vibora import Request
from jinja2 import Environment, PackageLoader
from weeabot.core.bot import Weeabot


environment = Environment(loader=PackageLoader('weeabot', 'web'), enable_async=True)

async def render(template: str, bot: Weeabot, request: Request, **kwargs):
    # read cookies for extra data
    _kwargs = {**kwargs}
    id_cookie = request.cookies.get('weeabot-user-id', None)
    if id_cookie is not None:
        user_id = bot.oauth.signer.loads(id_cookie)
        _kwargs['user'] = await bot.get_user(user_id)
    
    # render using collected data
    return await environment.get_template(template).render_async({
        "request": request,
        "navpages": bot.config['web']['site']['navpages'],
        "bot": bot,
        **_kwargs
    })
