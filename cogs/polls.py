# noinspection PyUnresolvedReferences
import discord
# noinspection PyUnresolvedReferences
from discord.ext import commands
from utils import *


def polls_channel(bot: discord.ext.commands.Bot, server: discord.Server):
    return bot.server_configs.get(server.id, {}).get('polls_channel', None)


def has_polls_channel():
    return commands.check(lambda ctx: polls_channel(ctx.bot, ctx.message.server) is not None)


class Polls:
    """Add and vote in polls."""

    def __init__(self, bot):
        self.bot = bot
        self.polls = open_json('polls.json')

    def dump(self):
        with open('polls.json', 'w') as f:
            json.dump(self.polls, f, ensure_ascii=True)

    async def update_polls(self, server: discord.Server):
        """Update the polls message for a server."""
        channel = server.get_channel(polls_channel(self.bot, server))
        message = self.bot.server_configs.get(server.id, {}).get('polls_message', None)
        if message is None:
            message = await self.bot.send_message(channel, "Polls")
            self.bot.server_configs.get(server.id, {})['polls_message'] = message.id
            self.bot.dump_server_configs()
        else:
            message = await self.bot.get_message(server.get_channel(polls_channel(self.bot, server)), message)
        sep = '-----------------------'
        polls_text = ["Polls"]
        server_polls = {k: self.polls[k] for k in self.polls if self.polls[k]['server'] == server.id}
        for pk in server_polls:
            p = server_polls[pk]
            pt = ['id: {}'.format(pk), '***{}***'.format(p['question']),
                  'by {} at {}'.format(server.get_member(p['author']).display_name, p['start']), sep]
            for i in range(0, len(p['answers'])):
                pt.append('**{}**: {}'.format(i, p['answers'][i]))
            polls_text.append('\n'.join(pt))
        await self.bot.edit_message(message, '\n{0}{0}\n\n'.format(sep).join(polls_text))

    @commands.command()
    @is_server_owner()
    async def set_polls_channel(self, channel: discord.Channel):
        """Set the channel polls will be displayed in. It is recommended that only the bot and moderators can speak."""
        self.bot.server_configs.get(channel.server.id, {})['polls_channel'] = channel.id
        await self.bot.say('Polls will be displayed in {}. Only allow me and moderators to speak there.'.format(channel.mention))
        self.bot.dump_server_configs()

    @commands.group(invoke_without_command=True, pass_context=True)
    @has_polls_channel()
    async def poll(self, ctx, poll_id: str, answer_index: int):
        """Respond to a poll."""
        if poll_id not in self.polls or ((not ctx.message.channel.is_private) and 
                                         ctx.message.server.id != self.polls[poll_id]['server']):
            await self.bot.say('Poll not found.')
            return
        try:
            if ctx.message.author.id in self.polls[poll_id]['users']:
                self.polls[poll_id]['results'][self.polls[poll_id]['users'][ctx.message.author.id]] -= 1
            self.polls[poll_id]['results'][answer_index] += 1
            self.polls[poll_id]['users'][ctx.message.author.id] = answer_index
            self.dump()
            await self.bot.say("Vote recorded.")
        except IndexError:
            await self.bot.say("Invalid answer index.")

    @poll.command(name='add', pass_context=True)
    @has_polls_channel()
    async def _add(self, ctx, *, question: str):
        """Add a poll."""
        await self.bot.say("What answers do you want to set? Separate them by semicolons.")
        msg = await self.bot.wait_for_message(author=ctx.message.author)
        answers = msg.content.split(';')
        if len(answers) < 1:
            await self.bot.say("Poll creation cancelled.")
        try:
            poll_id = str(int(max(self.polls)) + 1)
        except ValueError:
            poll_id = '0'
        self.polls[poll_id] = {
            'server': ctx.message.server.id,
            'author': ctx.message.author.id,
            'question': question,
            'answers': answers,
            'start': str(ctx.message.timestamp),
            'results': [0] * len(answers),
            'users': {}
        }
        self.dump()
        await self.update_polls(ctx.message.server)

    @poll.command(name='close', pass_context=True)
    @has_polls_channel()
    async def _close(self, ctx, poll_id: str):
        """Close a poll from further entries and display results."""
        author = ctx.message.author
        try:
            p = self.polls[poll_id]
        except KeyError:
            await self.bot.say("Poll not found.")
            return
        if author.id in [self.bot.owner.id, ctx.message.server.owner.id, p['author']]:
            t = ([p['question'], 'by {} at {}'.format(ctx.message.server.get_member(p['author']).display_name, p['start']),
                 'Poll results:'] +
                 ["**{}**: {}".format(p['answers'][ind], p['results'][ind]) for ind in range(0, len(p['results']))])

            await self.bot.say('\n'.join(t))
            del self.polls[poll_id]
            self.dump()
            await self.update_polls(ctx.message.server)
        else:
            await self.bot.say("You do not have permission to do that.")

    @poll.command(name='refresh', pass_context=True)
    @has_polls_channel()
    async def _refresh(self, ctx):
        """Refresh the polls."""
        await self.update_polls(ctx.message.server)


def setup(bot):
    bot.add_cog(Polls(bot))
