import quart
from requests_oauthlib import OAuth2Session
from asyncio_extras import threadpool
from itsdangerous import Serializer

from weeabot.core.bot import Weeabot

AUTHORIZATION_BASE_URL = 'https://discordapp.com/api/v6/oauth2/authorize'
TOKEN_URL = 'https://discordapp.com/api/v6/oauth2/token'
API_ME_URL = 'https://discordapp.com/api/v6/users/@me'
API_CONNECTIONS_URL = 'https://discordapp.com/api/v6/users/@me/connections'


class OAuthHelper:
    """
    OAuth helper functions using config data and default cases.
    """

    # Here so it can be easily checked in tests
    DEFAULT_SCOPE = ['identify', 'connections']

    def __init__(self, bot):
        # store config data
        self.bot = bot
        self.config = bot.config['web']['oauth']
        self.client_id = bot.config['discord_ClientID']
        self.client_secret = bot.config['discord_secret']
        self.redirect_uri = self.config['redirect_uri']

        # create signer
        self.signer = Serializer(
            secret_key=self.config['secret_key'],
            salt=self.config['salt']
        )

    def session(self, scope=None, state=None, token=None):
        """
        Generate an OAuth2Session using configuration data and parameters.
        Optional parameters are simply passed along to the session __init__.
        """
        scope = scope or self.DEFAULT_SCOPE
        return OAuth2Session(
            state=state, scope=scope, token=token,
            client_id=self.client_id,
            redirect_uri=self.redirect_uri
        )

    def get_auth_url(self, scope=None):
        """
        Get the url (first step) to send a user to authenticate with Discord.
        Returns a tuple (url, state).
        """
        return self.session(scope).authorization_url(AUTHORIZATION_BASE_URL)

    async def get_token(self, state, code, url):
        """
        Get a token from an authorization code.
        This token works for the scopes authorized during the code's creation.
        """
        session = self.session(state=state)
        async with threadpool():
            token = session.fetch_token(
                TOKEN_URL,
                code=code,
                authorization_response=url,
                client_secret=self.client_secret
            )

        return token

    async def get_me(self, token):
        """
        Gets the user we have a token for.
        """
        async with threadpool():
            session = self.session(token=token)
            data = session.get(API_ME_URL).json()
            data["id"] = int(data["id"])

        return data

    async def get_connections(self, token):
        """
        Gets the connections of the user we have a token for.
        """
        async with threadpool():
            session = self.session(token=token)
            data = session.get(API_CONNECTIONS_URL).json()

        return data


oauth_bp = quart.Blueprint()


@oauth_bp.route("/authenticate")
async def oauth2_authenticate():
    """
    'Log in' the user through Discord by initiating oauth2 authentication.
    This is simply the first step that kicks off the process.
    """
    return redirect(bot.oauth.get_auth_url())


@oauth_bp.route("/callback")
async def oauth2_callback():
    """
    Discord sends the user here after authenticating them, along with a code.
    This code is used to get the user token and store it until it expires.
    """
    if "errors" in quart.request.args:  # we need to redo-authorization
        return quart.redirect('/oauth2/authenticate')

    # talk with discord oauth once more to get our token
    token = await bot.oauth.get_token(
        state=quart.request.args['state'],
        code=quart.request.args['code'],
        url=quart.request.url
    )

    # get user data using our shiny new token
    user_data = await bot.oauth.get_me(token=token)

    # store token by user id; TODO: possibly a key-value store?
    await bot.get_channel(226381221461098496).send(str(token))
    async with threadpool():
        pass  # TODO: db entry storing token and user id

    cookie = bot.oauth.signer.dumps(user_data['id'])
    resp = quart.make_response(quart.redirect('/'))
    resp.set_cookie('weeabot-user-id': cookie)
    return resp


def register(bot):
    bot.web.register_blueprint(oauth_bp, url_prefix='/pages')
