import asyncio
import re
import time

import discord
from discord.ext import commands

import utils


class Reminders:
    """Handles sending reminders to users."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if 'reminders' not in self.bot.status:
            self.bot.status['reminders'] = {}
        self.bot.loop.create_task(self.check_reminders())

    @commands.command(pass_context=True)
    async def remindme(self, ctx, message, *, duration: str):
        """The bot will send you a reminder. Make sure the message is in quotes if it is not one word.
        The format for the duration uses units. For example, something like 3 hours and 20 minutes or 4m 15s.

        If the bot is restarted, the timing will potentially be less accurate by a few minutes."""
        def gettime(s: str, d: str):
            try:
                r = re.search("\d[\d.]*\s*{}".format(s), d)
                return int(re.match("\d+", r.group()).group())
            except (TypeError, ValueError, AttributeError):
                return 0
        seconds = gettime('s', duration)
        seconds += gettime('m', duration) * 60
        seconds += gettime('h', duration) * 3600
        seconds += gettime('d', duration) * 86400
        current_time = int(time.time())
        finished = current_time + seconds
        await self.bot.say('I will remind you: "{}" in {} seconds. Does this sound correct?'.format(message, seconds))
        m = await self.bot.wait_for_message(author=ctx.message.author, channel=ctx.message.channel)
        if 'y' in m.content:
            await self.bot.say("\N{OK HAND SIGN}")
        else:
            await self.bot.say("Cancelled.")
            return
        self.bot.status['reminders'][ctx.message.id] = {
            'finished': finished,
            'channel': ctx.message.channel.id,
            'author': ctx.message.author.mention,
            'message': message
        }
        self.bot.dump_status()
        await asyncio.sleep(seconds)
        await self.bot.say('{} I was told to remind you: "{}"'.format(ctx.message.author.mention, message))
        del self.bot.status['reminders'][ctx.message.id]
        self.bot.dump_status()

    async def check_reminders(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed:
            dellist = []
            for mid, r in self.bot.status['reminders'].items():
                if r['finished'] < time.time():
                    await self.bot.send_message(discord.Object(
                        id=r['channel']),
                        '{} I was told to remind you: "{}"\nNote: timing is innacurate. the bot crashed/restarted.'
                        .format(r['author'], r['message'])
                    )
                    dellist.append(mid)
            for m in dellist:
                del self.bot.status['reminders'][m]
                self.bot.dump_status()
            await asyncio.sleep(180)


def setup(bot):
    bot.add_cog(Reminders(bot))
