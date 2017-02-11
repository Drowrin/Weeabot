import random
import asyncio
import re

from chatterbot import ChatBot
from chatterbot.logic import LogicAdapter
from chatterbot.conversation import Statement

import utils


class ThanksLogicAdapter(LogicAdapter):
    def can_process(self, statement):
        return 'thank' in statement.text.lower() or 'thx' in statement.text.lower()

    def process(self, statement):
        return 1, Statement(f"You're welcome {random.choice(utils.content.emoji)}")


class TagLogicAdapter(LogicAdapter):
    def can_process(self, statement):
        return any(x in statement.text.lower() for x in sum(utils.content.tag_responses.values(), []))

    def process(self, statement):
        for k, v in utils.content.tag_responses.items():
            if any(p in statement.text.lower() for p in v):
                return 1, Statement(statement.text, extra_data={'command': f'tag {k}'})
        return 0, statement


class AsyncChatBot(ChatBot):
    def __init__(self, loop: asyncio.BaseEventLoop, *args, **kwargs):
        super(AsyncChatBot, self).__init__(*args, **kwargs)
        self.loop = loop

    async def async_get_response(self, statement: str, session_id: str=None):
        return await self.loop.run_in_executor(None, lambda: self.get_response(statement, session_id))


class Conversation:
    """Handles natural conversation with users."""

    services = {
        "Conversation": "Tag the bot at the beginning of a message to have a conversation with it."
    }

    def __init__(self, bot):
        self.bot = bot

        self.chatname = 'Weeabot'
        self.chatbot = AsyncChatBot(
            bot.loop,
            self.chatname,
            trainer='chatterbot.trainers.ChatterBotCorpusTrainer',

            storage_adapter="chatterbot.storage.JsonFileStorageAdapter",
            silence_performance_warning=True,
            database="./chatterbot_database.json",

            logic_adapters=[
                "cogs.conversation.ThanksLogicAdapter",
                "cogs.conversation.TagLogicAdapter",
                "chatterbot.logic.BestMatch",
                "chatterbot.logic.MathematicalEvaluation",
                {
                    "import_path": "chatterbot.logic.LowConfidenceAdapter",
                    "threshhold": 0.1,
                    "default_response": "I don't understand."
                }
            ]
        )
        self.chatbot.train("chatterbot.corpus.english")

    async def on_message(self, message):
        if message.author.bot or utils.is_command_of(self.bot, message) or message.channel.is_private:
            return

        if message.server.me in message.mentions:
            # clean the contents for best results
            s = message.clean_content.replace('@', '').replace(message.server.me.display_name, self.chatname)
            if s.startswith(self.chatname):  # remove name at start
                s = s[len(self.chatname)+1:]
            for r in re.findall(r"(<:(.+):\d+>)", s):  # replace emoji with names
                s = s.replace(*r)

            c = await self.chatbot.async_get_response(s)

            if 'command' in c.extra_data:
                message.content = f'{self.bot.command_prefix}{c.extra_data["command"]}'
                await self.bot.process_commands(message)
            else:
                response = c.text.replace(self.chatname, message.server.me.display_name)
                await self.bot.send_message(message.channel, f"{message.author.mention} {response}")


def setup(bot):
    bot.add_cog(Conversation(bot))
