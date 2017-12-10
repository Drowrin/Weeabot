import random
import asyncio
import re
import requests

from chatterbot import ChatBot
from chatterbot import logic
from chatterbot.conversation import Statement
from chatterbot import trainers
from pymongo.errors import ServerSelectionTimeoutError

from discord.ext import commands

import checks
import utils


class ThanksLogicAdapter(logic.LogicAdapter):
    def can_process(self, statement):
        return 'thank' in statement.text.lower() or 'thx' in statement.text.lower()

    def process(self, statement):
        s = Statement(f"You're welcome {random.choice(utils.content.emoji)}")
        s.confidence = 1
        return s


class TagLogicAdapter(logic.LogicAdapter):
    def can_process(self, statement):
        return any(x in statement.text.lower() for x in sum(utils.content.tag_responses.values(), []))

    def process(self, statement):
        for k, v in utils.content.tag_responses.items():
            if any(p in statement.text.lower() for p in v):
                s = Statement(statement.text, extra_data={'command': f'tag {k}'})
                s.confidence = 1
                return s
        statement.confidence = 0
        return statement


class CleverCacheLogicAdapter(logic.LowConfidenceAdapter):
    """Similar to LowConfidenceAdapter, but gets response from Cleverbot if needed."""

    def __init__(self, **kwargs):
        super(CleverCacheLogicAdapter, self).__init__(**kwargs)

        self.api_key = kwargs.get('api_key', "")
        self.sessions = {}

    def can_process(self, statement):
        """Only able to process if an API key was passed."""
        return bool(self.api_key)

    def process(self, input_statement):
        """Ask Cleverbot if best response is below the threshold."""
        url = 'https://www.cleverbot.com/getreply'
        params = {
            'key': self.api_key,
            'input': input_statement.text
        }

        # attempt to get session cs
        session = input_statement.session if hasattr(input_statement, 'session') else None
        cs = self.sessions.get(session, None)
        if cs:
            params['cs'] = cs

        if self.get(input_statement).confidence < self.confidence_threshold:
            try:
                # get data from cleverbot
                r = requests.get(url, params=params)
                data = r.json()
            except requests.HTTPError:
                pass  # In the case of HTTP Errors, abandon getting data from cleverbot and return low confidence
            else:
                if session:
                    # save cs info if applicable
                    self.sessions[session] = data['cs']

                # construct high confidence response
                s = Statement(data['output'], in_response_to=[input_statement])
                s.confidence = 1
                return s

        # return dummy with 0 confidence
        return Statement("")


class AsyncChatBot(ChatBot):
    def __init__(self, loop: asyncio.BaseEventLoop, *args, **kwargs):
        super(AsyncChatBot, self).__init__(*args, **kwargs)
        self.loop = loop

    async def async_get_response(self, statement: str, session_id: str=None):
        return await self.loop.run_in_executor(None, lambda: self.get_response(statement, session_id))

    def generate_response(self, input_statement, session_id):
        input_statement.session = session_id
        return super(AsyncChatBot, self).generate_response(input_statement, session_id)


class Conversation:
    """Handles natural conversation with users."""

    services = {
        "Conversation": "Tag the bot at the beginning of a message to have a conversation with it."
    }

    def __init__(self, bot):
        self.bot = bot

        self.sessions = {}

        self.chatname = 'Weeabot'
        self.chatbot = None

        def make_chatterbot():
            try:
                self.chatbot = AsyncChatBot(
                    bot.loop,
                    self.chatname,

                    storage_adapter=self.bot.config.chatterbot,

                    logic_adapters=[
                        "cogs.conversation.ThanksLogicAdapter",
                        "cogs.conversation.TagLogicAdapter",
                        "chatterbot.logic.BestMatch",
                        "chatterbot.logic.MathematicalEvaluation",
                        {
                            "import_path": "cogs.conversation.CleverCacheLogicAdapter",
                            "api_key": utils.tokens["cleverbot_api_key"],
                            "threshold": .7
                        }
                    ]
                )
            except ServerSelectionTimeoutError:
                print('Could not connect to mongodb. Conversation is disabled.')
            else:
                print('Mongodb connected. Conversation is enabled.')
        self.bot.loop.run_in_executor(None, make_chatterbot)

    async def on_message(self, message):
        if self.chatbot:
            if message.author.bot or utils.is_command_of(self.bot, message) or message.channel.is_private:
                return

            if message.server.me in message.mentions:
                await self.bot.send_typing(message.channel)

                # clean the contents for best results
                s = message.clean_content.replace('@', '').replace(message.server.me.display_name, self.chatname)
                if s.startswith(self.chatname):  # remove name at start
                    s = s[len(self.chatname)+1:]
                for r in re.findall(r"(<:(.+):\d+>)", s):  # replace emoji with names
                    s = s.replace(*r)

                if message.author.id not in self.sessions:
                    self.sessions[message.author.id] = self.chatbot.conversation_sessions.new()

                c = await self.chatbot.async_get_response(s, self.sessions[message.author.id].id_string)

                if 'command' in c.extra_data:
                    message.content = f'{self.bot.command_prefix}{c.extra_data["command"]}'
                    await self.bot.process_commands(message)
                else:
                    response = c.text.replace(self.chatname, message.server.me.display_name)
                    await self.bot.send_message(message.channel, f"{message.author.mention} {response}")

    @commands.group(pass_context=True, invoke_without_command=True)
    @checks.is_owner()
    async def train(self, ctx):
        """Train the knowledge graphs with corps data."""
        self.chatbot.set_trainer(trainers.ChatterBotCorpusTrainer)

        scopes = ['ai', 'botprofile', 'conversations', 'drugs', 'emotion', 'food', 'greetings', 'humor', 'money']
        response = True

        def trainer():
            for s in scopes:
                try:
                    self.chatbot.train(f'chatterbot.corpus.english.{s}')
                except FileNotFoundError:
                    self.bot.loop.create_task(self.bot.send_message(ctx.message.channel, f'failed to find {s}'))
                    response = False

        await self.bot.loop.run_in_executor(None, trainer)
        await (self.bot.affirmative() if response else self.bot.negative())


def setup(bot):
    bot.add_cog(Conversation(bot))
