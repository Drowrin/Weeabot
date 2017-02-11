import random
import asyncio

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
        return any(x in statement.text for x in sum(utils.content.tag_responses.values(), []))

    def process(self, statement):
        for k, v in utils.content.tag_responses.items():
            if any(p in statement.text for p in v):
                return 1, Statement(statement.text, extra_data={'command': f'tag {k}'})
        return 0, statement


class AsyncChatBot:
    def __init__(self, name: str, loop: asyncio.BaseEventLoop):
        self.loop = loop
        self.chatbot = ChatBot(
            name,
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

    def train(self, *args, **kwargs):
        return self.chatbot.train(*args, **kwargs)

    async def get_response(self, statement: str):
        return await self.loop.run_in_executor(None, lambda: self.chatbot.get_response(statement))


class Conversation:
    """Handles natural conversation with users."""

    services = {
        "Conversation": "Tag the bot at the beginning of a message to have a conversation with it."
    }

    def __init__(self, bot):
        self.bot = bot

        self.chatname = 'Weeabot'
        self.chatbot = AsyncChatBot(self.chatname, bot.loop)
        self.chatbot.train("chatterbot.corpus.english")

    async def on_message(self, message):
        if message.author.bot or utils.is_command_of(self.bot, message) or message.channel.is_private:
            return

        if message.server.me in message.mentions:
            s = message.clean_content.replace('@', '').replace(message.server.me.display_name, self.chatname)
            if s.startswith(self.chatname):
                s = s[len(self.chatname)+1:]
            c = await self.chatbot.get_response(s)

            if 'command' in c.extra_data:
                message.content = f'{self.bot.command_prefix}{c.extra_data["command"]}'
                await self.bot.process_commands(message)
            else:
                await self.bot.send_message(message.channel, f"{message.author.mention} {c}")


def setup(bot):
    bot.add_cog(Conversation(bot))
