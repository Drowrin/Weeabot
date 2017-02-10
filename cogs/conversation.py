import random

from chatterbot import ChatBot
from chatterbot.logic import LogicAdapter
from chatterbot.conversation import Statement

import utils


class ThanksLogicAdapter(LogicAdapter):
    def can_process(self, statement):
        return 'thank' in statement.text.lower() or 'thx' in statement.text.lower()

    def process(self, statement):
        return 1, Statement(f"You're welcome {random.choice(utils.content.emoji)}")


class Conversation:
    """Handles natural conversation with users."""

    services = {
        "Conversation": "Tag the bot at the beginning of a message to have a conversation with it."
    }

    def __init__(self, bot):
        self.bot = bot

        self.chatname = 'Weeabot'
        self.chatbot = ChatBot(
            self.chatname,
            trainer='chatterbot.trainers.ChatterBotCorpusTrainer',

            storage_adapter="chatterbot.storage.JsonFileStorageAdapter",
            silence_performance_warning=True,
            database="./chatterbot_database.json",

            logic_adapters=[
                "cogs.conversation.ThanksLogicAdapter",
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
            s = message.clean_content.replace('@', '').replace(message.server.me.display_name, self.chatname)
            if s.startswith(self.chatname):
                s = s[len(self.chatname)+1:]
            c = self.chatbot.get_response(s)
            await self.bot.send_message(message.channel, f"{message.author.mention} {c}")


def setup(bot):
    bot.add_cog(Conversation(bot))
