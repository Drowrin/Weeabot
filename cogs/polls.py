# noinspection PyUnresolvedReferences
import discord
# noinspection PyUnresolvedReferences
from discord.ext import commands
from utils import *


def polls_channel(bot: discord.ext.commands.Bot, server: discord.Server):
    return bot.server_configs.get(server.id, {}).get('polls_channel', None)


def has_polls_channel():
    return commands.check(lambda ctx: True if ctx.message.channel.is_private else polls_channel(ctx.bot, ctx.message.server) is not None)


class Poll:
    """Data class for poll variables. Includes a few helper methods."""

    def __init__(self, question: str, answers: str, poll_id: str, ctx=None, **kwargs):
        """Stores poll data."""
        sid = None
        aid = None
        ts = None
        if ctx is not None:
            sid = ctx.message.server.id
            aid = ctx.message.author.id
            ts = str(ctx.message.timestamp)
        self.id = poll_id
        self.question = question
        self.answers = answers
        self.server = kwargs.pop('server', sid)
        self.author = kwargs.pop('author', aid)
        self.type = kwargs.pop('type', [t[0] for t in Polls.types])
        self.start = kwargs.pop('start', ts)
        self.results = kwargs.pop('results', [0] * len(answers))
        self.users = kwargs.pop('users', {})

    def dump(self):
        """get information in dictionary form."""
        return {
            'server': self.server,
            'author': self.author,
            'type': self.type,
            'question': self.question,
            'answers': self.answers,
            'start': self.start,
            'results': self.results,
            'users': self.users
        }

    def poll_string(self, server):
        """Convert to a str."""
        pt = ['id: {}'.format(self.id), '**{}**'.format(self.question),
              'by {} at {}'.format(server.get_member(self.author).display_name, self.start),
              'Type: ' + ', '.join(self.type), Polls.sep]
        users = {x: [] for x in range(0, len(self.answers))}
        if 'multiple' in self.type:
            for user in self.users:
                for i in range(0, len(self.answers)):
                    if self.users[user][i]:
                        users[i].append(server.get_member(user).display_name)
        else:
            for user in self.users:
                users[self.users[user]].append(server.get_member(user).display_name)
        for i in range(0, len(self.answers)):
            extras = [' -- ']
            if 'live' in self.type:
                extras.append('({} votes)'.format(self.results[i]))
            if 'identified' in self.type and len(users[i]) > 0:
                extras.append('({})'.format(','.join(users[i])))
            pt.append('**{}**: {}{}'.format(i, self.answers[i], ''.join(extras) if len(extras) > 1 else ''))
        if 'open' in self.type:
            i = len(self.answers)
            pt.append('**{}**: {}'.format(i, 'submit new response.'))
        return '\n'.join(pt)

    def final_results(self, server):
        """the results formatted as a str."""
        s = '\n'.join(self.poll_string(server).splitlines()[1:])  # strip the id
        w_indexes = [i for i, j in enumerate(self.results) if j == max(self.results)]
        winners = ['{} -- ({} votes)'.format(self.answers[w], self.results[w]) for w in w_indexes]
        return '__Results__\n{}\n\nWinner{}:\n{}'.format(s, 's' if len(winners) > 1 else '', '\n'.join(winners))


class Polls:
    """Add and vote in polls."""

    types = [('anonymous', 'identified'), ('live', 'static'), ('strict', 'open'), ('single', 'multiple')]
    sep = '-----------------------'

    def __init__(self, bot):
        self.bot = bot
        raw_polls = open_json('polls.json')
        self.polls = {k: Poll(**raw_polls[k], bot=self.bot, poll_id=k) for k in raw_polls}

    def dump(self):
        with open('polls.json', 'w') as f:
            json.dump({k: self.polls[k].dump() for k in self.polls}, f, ensure_ascii=True)

    async def update_polls(self, poll_server: str):
        """Update the polls message for a server."""
        if poll_server == 'global':
            servers = [s for s in self.bot.servers if polls_channel(self.bot, s) is not None]
        else:
            servers = [self.bot.get_server(poll_server)]
        for server in servers:
            channel = server.get_channel(polls_channel(self.bot, server))
            message = self.bot.server_configs.get(server.id, {}).get('polls_message', None)
            if message is None:
                message = await self.bot.send_message(channel, "Polls")
                self.bot.server_configs[server.id]['polls_message'] = message.id
                self.bot.dump_server_configs()
            else:
                message = await self.bot.get_message(server.get_channel(polls_channel(self.bot, server)), message)

            polls_text = ["Polls"]
            global_polls = {k: self.polls[k] for k in self.polls if self.polls[k].server == 'global'}
            if len(global_polls):
                polls_text.append("Global Polls")
                for pk in global_polls:
                    polls_text.append(global_polls[pk].poll_string(server))
                polls_text.append('{0}{0}'.format(self.sep))
                polls_text.append("Local Polls")
            server_polls = {k: self.polls[k] for k in self.polls if self.polls[k].server == server.id}
            for pk in server_polls:
                polls_text.append(server_polls[pk].poll_string(server))
            await self.bot.edit_message(message, '\n{0}{0}\n\n'.format(self.sep).join(polls_text))

    @commands.command()
    @is_server_owner()
    async def set_polls_channel(self, channel: discord.Channel):
        """Set the channel polls will be displayed in. It is recommended that only the bot and moderators can speak."""
        if channel.server.id not in self.bot.server_configs:
            self.bot.server_configs[channel.server.id] = {}
        self.bot.server_configs[channel.server.id]['polls_channel'] = channel.id
        await self.bot.say('Polls will be displayed in {}.'.format(channel.mention))
        self.bot.dump_server_configs()

    @commands.group(invoke_without_command=True, pass_context=True)
    async def poll(self, ctx, poll_id: str, answer_index: int):
        """Respond to a poll.

        Poll ids are global. This means you can PM the bot this command for anonymous responses.
        (The bot will still know who made the vote, of course, but your fellow server members won't)"""
        if poll_id not in self.polls or ((not ctx.message.channel.is_private) and 
                                         self.polls[poll_id].server not in [ctx.message.server.id, 'global']):
            await self.bot.say('Poll not found.')
            return
        try:
            p = self.polls[poll_id]
        except IndexError:
            await self.bot.say("Invalid answer index.")
            return
        if answer_index == len(p.answers) and 'open' in p.type:
            await self.bot.say("What should the new entry say?")
            msg = await self.bot.wait_for_message(author=ctx.message.author)
            p.answers.append(msg.content)
            p.results.append(0)
            if 'multiple' in p.type:
                for user in p.users:
                    p.users[user].append(False)
        if 'multiple' in p.type:
            aid = ctx.message.author.id
            if aid not in p.users:
                p.users[aid] = [False] * len(p.answers)
            if not p.users[aid][answer_index]:
                p.results[answer_index] += 1
            p.users[aid][answer_index] = True
        else:
            if ctx.message.author.id in p.users:
                p.results[p.users[ctx.message.author.id]] -= 1
            p.results[answer_index] += 1
            p.users[ctx.message.author.id] = answer_index
        self.dump()
        await self.bot.say("Vote recorded.")
        if 'live' in p.type:
            await self.update_polls(p.server)

    @poll.command(name='add', pass_context=True)
    @has_polls_channel()
    async def _add(self, ctx, *, question: str):
        """Add a poll."""
        await self.bot.say("What answers do you want to set? Separate them by semicolons.")
        msg = await self.bot.wait_for_message(author=ctx.message.author)
        answers = msg.content.split(';')
        if len(answers) < 1:
            await self.bot.say("Poll creation cancelled.")
        await self.bot.say("What type of poll is this? Can be several. Possible types:\n{}"
                           .format(', '.join(['|'.join(t) for t in self.types])))
        msg = await self.bot.wait_for_message(author=ctx.message.author)
        poll_type = [t[0] for t in self.types]
        for it, t in enumerate(self.types):
            for st in t:
                if st in msg.content:
                    poll_type[it] = st
        server = ctx.message.server.id
        if ctx.message.author.id == self.bot.owner.id:
            await self.bot.say("Is this poll global?")
            msg = await self.bot.wait_for_message(author=ctx.message.author)
            if 'yes' in msg.content.lower():
                server = 'global'
        try:
            poll_id = str(int(max(self.polls)) + 1)
        except ValueError:
            poll_id = '0'
        self.polls[poll_id] = Poll(question, answers, poll_id, ctx, server=server, type=poll_type)
        self.dump()
        await self.update_polls(self.polls[poll_id].server)
        await self.bot.say("Added poll:\n{}".format(self.polls[poll_id].poll_string(ctx.message.server)))

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
        if author.id in [self.bot.owner.id, ctx.message.server.owner.id, p.author]:
            await self.bot.say(p.final_results(ctx.message.server))
            p = self.polls.pop(poll_id)
            self.dump()
            await self.update_polls(p.server)
        else:
            await self.bot.say("You do not have permission to do that.")

    @poll.command(name='refresh', pass_context=True)
    @has_polls_channel()
    async def _refresh(self, ctx):
        """Refresh the polls."""
        await self.update_polls(ctx.message.server.id)


def setup(bot):
    bot.add_cog(Polls(bot))
