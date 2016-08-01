# noinspection PyUnresolvedReferences
import discord
import random
# noinspection PyUnresolvedReferences
from discord.ext import commands
from utils import *


def atk_formatter(ctx, field, fields):
    stats = {
        'KD': field['k'] / field['d'],
        'ACC': field['k'] / field['a'],
        'SUR': field['e'] / (field['e'] + field['d']),
        'SDEATH': field['s'] / field['a']
    }
    rank = {'KD': 'Tryhard', 'ACC': 'Lucky', 'SUR': 'Slippery', 'SDEATH': 'Sdeath'}[max(stats, key=stats.get)]
    rival = discord.utils.get(ctx.bot.get_all_members(), id=max(field['r'], key=field['r'].get))
    fields.append('{}\n\nRIVAL: {}\nRANK: {}'.format(
        '\n'.join(['{}: {}'.format(k, v) for k, v in stats.items()]), rival.display_name, rank))


class RNG:
    """Commands based on a randomly selected value."""

    formatters = {}
    verbose_formatters = {'atk': atk_formatter}

    def __init__(self, bot):
        self.bot = bot
        self.atk = bot.content.attack

    @commands.command(aliases=('pick', 'choice'))
    async def choose(self, *, choices):
        """Choose from a list of choices. Separate with semicolons."""
        await self.bot.reply(random.choice(choices.split(';')))

    @commands.group(invoke_without_command=True, pass_context=True)
    async def raffle(self, ctx):
        """Choose a user."""
        if ctx.invoked_subcommand is None:
            await self.bot.say(random.choice(list(ctx.message.server.members)).display_name)

    @raffle.command(pass_context=True, asliases=('a',))
    async def attribute(self, ctx, *attributes):
        """Raffle by attribute checks."""
        attr_dict = {c.split('=')[0]: c.split('=')[1] for c in attributes if '=' in c}

        def predicate(elem):
            for a, v in attr_dict.items():
                n = a.split('__')
                o = elem
                for att in n:
                    o = getattr(o, att)
                if o != v:
                    return False
            return True

        try:
            choices = list(filter(predicate, ctx.message.server.members))
            await self.bot.say(random.choice(choices).display_name)
        except IndexError:
            await self.bot.say("None")
        except KeyError as e:
            await self.bot.say(e)

    @raffle.command(pass_context=True, aliases=('c',))
    async def channel(self, ctx):
        """Raffle from users who are able to see this channel."""
        choices = filter(lambda e: ctx.message.channel.permissions_for(e).read_messages, ctx.message.server.members)
        await self.bot.say(random.choice(list(choices)).display_name)

    @commands.command()
    async def roll(self, sides: str='6'):
        """Roll a die.
        
        Defaults to d6.
        Can use DnD format: 2d6"""
        try:
            if 'd' in sides:
                sp = sides.split('d')
                n = int(sp[0])
                s = int(sp[1])
                await self.bot.say('```\n{}\n```'.format(
                    '\n'.join(['{}: {}/{}'.format(i, random.randint(1, s), s) for i in range(1, n)])))
            else:
                await self.bot.reply("You rolled a {} out of {}.".format(random.randint(1, int(sides)), sides))
        except ValueError:
            raise commands.BadArgument("Incorrect die formatting.")

    @commands.command(name='8ball')
    async def eight_ball(self, *, question: str):
        """8ball responses to your questions."""
        r = [
            'Yes, in due time.',
            'My sources say no.',
            'Definitely not.',
            'Yes.',
            'I have my doubts.',
            'Who knows?',
            'Probably.',
            'Only if you type "I am trash" in the next five seconds.'
        ]
        await self.bot.reply('{}\n{}'.format(question, random.choice(r)))

    @commands.command()
    async def rate(self, *, thing: str):
        """Rate something. Anything. Go nuts."""
        s = sum([hash(c) % 10 for c in list(thing)])
        await self.bot.say("I give it a {}/10.".format((s % 10) + 1))

    def get_atk(self, uid: str):
        up = self.bot.profiles.get_field_by_id(uid, 'atk')
        if not len(up):
            up['a'] = 0
            up['m'] = 0
            up['k'] = 0
            up['d'] = 0
            up['e'] = 0
            up['s'] = 0
            up['r'] = {}
        return up

    def inc(self, field: str, uid: str):
        up = self.get_atk(uid)
        up[field] += 1

    def inc_r(self, uid: str, tar: str):
        up = self.get_atk(uid)
        if tar not in up['r']:
            up['r'][tar] = 0
        up['r'][tar] += 1
        if tar != uid:
            up = self.get_atk(tar)
            if uid not in up['r']:
                up['r'][uid] = 0
            up['r'][uid] += 1

    @commands.command(pass_context=True, aliases=('a', 'shoot', 'kill',))
    @profiles()
    async def attack(self, ctx, *users: str):
        """Attempt to attack some users."""
        author = ctx.message.author
        uid = author.id
        selves = [author.mention, author.name, author.display_name] + self.atk['self']
        immune = [self.bot.user.mention, self.bot.user.name, self.bot.user.display_name]
        userlist = [u for u in users if u not in immune and u not in selves]
        immunelist = [u for u in users if u in immune]
        if '@everyone' in users:
            userlist = [*ctx.message.channel.server.members]
        else:
            try:
                userlist = [commands.MemberConverter(ctx, u).convert() for u in userlist]
            except commands.BadArgument as e:
                await self.bot.say(e)
                return
        userset = set(userlist)
        hitself = len(users) != len(immunelist) + len(userlist)
        userlist = list(userset)
        if len(users) >= 1:
            ulted = len(userlist) > 1 and random.choice([False, True])
            ult = random.choice(list(self.atk['ult'].keys()))
            killed = []
            escaped = []
            if ulted:
                await self.bot.say("\"{1}\" -- {0}".format(author.mention, ult))
            for u in userlist:
                self.inc('a', uid)
                self.inc_r(uid, u.id)
                if random.choice([True] * (self.atk['ult'][ult] if ulted else 1) + [False]):
                    self.inc('k', uid)
                    self.inc('d', u.id)
                    killed.append(u.mention)
                else:
                    self.inc('m', uid)
                    self.inc('e', u.id)
                    escaped.append(u.mention)
            if len(killed) > 0:
                await self.bot.say('\n'.join(
                    [(self.atk['el'][0] if ulted else random.choice(self.atk['el'])).format(u) for u in killed]))
            if len(escaped) > 0:
                await self.bot.say('\n'.join([random.choice(self.atk['esc']).format(u) for u in escaped]))
        else:
            await self.bot.say(random.choice(self.atk['miss']))
            return
        for u in immunelist:
            await self.bot.say(random.choice(self.atk['immune']).format(author.mention, u))
        if hitself:
            self.inc('s', uid)
            self.inc('a', uid)
            self.inc('d', uid)
            self.inc_r(uid, uid)
            await self.bot.say(random.choice(self.atk['kys']).format(author.mention))


def setup(bot):
    bot.add_cog(RNG(bot))
