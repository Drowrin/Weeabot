import random

import discord
from discord.ext import commands

import checks


def atk_formatter(field):
    stats = {
        'KD': field['k'] / field['d'],
        'ACC': field['k'] / field['a'],
        'SUR': field['e'] / (field['e'] + field['d']),
        'SDEATH': field['s'] / field['a']
    }
    rank = {'KD': 'Tryhard', 'ACC': 'Lucky', 'SUR': 'Slippery', 'SDEATH': 'Sdeath'}[max(stats, key=stats.get)]
    return {
        'name': 'Attack',
        'content': '{}\n\nRANK: {}'.format('\n'.join(['{}: {}'.format(k, v) for k, v in stats.items()]), rank)
    }


def atk_default():
    return {'a': 0, 'm': 0, 'k': 0, 'd': 0, 'e': 0, 's': 0, 'r': {}}


class RNG:
    """Commands based on a randomly selected value."""

    formatters = {}
    verbose_formatters = {'atk': atk_formatter}
    defaults = {'atk': atk_default}

    def __init__(self, bot):
        self.bot = bot
        self.atk = bot.content.attack
        self.gun = {}

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
                    '\n'.join(['{}: {}/{}'.format(i, random.randint(1, s), s) for i in range(0, n)])))
            else:
                await self.bot.reply("You rolled a {} out of {}.".format(random.randint(1, int(sides)), sides))
        except ValueError:
            await self.bot.say("Incorrect die formatting.")

    @commands.command(name='8ball', rest_is_raw=True)
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
        await self.bot.say("I give it a {}/10.".format((s if "&knuckles" in thing else s % 10) + 1))

    def get_atk(self, uid: str):
        return self.bot.profiles.get_field_by_id(uid, 'atk')

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
    @checks.profiles()
    async def attack(self, ctx, *targets: str):
        """Attempt to attack some users."""
        
        if len(targets) == 0:
            await self.bot.say(random.choice(self.atk['miss']))
            return
        
        author = ctx.message.author
        uid = author.id
        selves = [author.mention, author.name, author.display_name] + self.atk['self']
        immune = [self.bot.user.mention, self.bot.user.name, self.bot.user.display_name]
        
        tars = []
        for u in targets:
            try:
                tars.append(commands.MemberConverter(ctx, u).convert())
            except commands.BadArgument:
                tars.append(u)
        
        result = []
        ulted = len(tars) > 1 and random.choice([False, True])
        ult = random.choice(list(self.atk['ult'].keys()))
        if ulted:
            result.append("\"{1}\" -- {0}".format(author.display_name, ult))
        for u in tars:
            dis_name = u if isinstance(u, str) else u.display_name
            if dis_name in immune:
                result.append(random.choice(self.atk['immune']).format(author.display_name, dis_name))
            elif dis_name in selves:
                result.append(random.choice(self.atk['kys']).format(author.display_name))
                self.inc('s', uid)
                self.inc('a', uid)
                self.inc('d', uid)
                self.inc_r(uid, uid)
                if u != tars[-1]:
                    result.append('{} is dead. The remaining targets escaped.'.format(author.display_name))
                    break
            else:
                try:
                    if random.choice([True] * (self.atk['ult'][ult] if ulted else 1) + [False]):
                        result.append((self.atk['el'][0] if ulted else random.choice(self.atk['el'])).format(dis_name))
                        self.inc('k', uid)
                        self.inc('d', u.id)
                    else:
                        result.append(random.choice(self.atk['esc']).format(dis_name))
                        self.inc('m', uid)
                        self.inc('e', u.id)
                    self.inc('a', uid)
                    self.inc_r(uid, u.id)
                except AttributeError:
                    pass
        await self.bot.say('\n'.join(result))

    @commands.group(pass_context=True, aliases=('rr',), invoke_without_command=True)
    async def russian_roulette(self, ctx):
        """A game of russian roulette."""
        if any(self.gun.get(ctx.message.server.id, [])):
            if self.gun[ctx.message.server.id][0]:
                self.gun[ctx.message.server.id][0] = 0
                await self.bot.say(":boom: :gun:")
            else:
                await self.bot.say(":gun:")
            self.gun[ctx.message.server.id] = self.gun[ctx.message.server.id][1:] + self.gun[ctx.message.server.id][:1]
        else:
            await self.bot.say("The gun is empty.")

    @russian_roulette.command(pass_context=True)
    async def spin(self, ctx):
        """Spin the cylinder."""
        if self.gun.get(ctx.message.server.id, None):
            s = random.randint(1, 5)
            self.gun[ctx.message.server.id] = self.gun[ctx.message.server.id][s:] + self.gun[ctx.message.server.id][:s]
        await self.bot.say(":gun: :arrows_counterclockwise:")

    @russian_roulette.command(pass_context=True)
    async def reload(self, ctx, bullets: int):
        """Reload the gun with a certain number of bullets."""
        if bullets not in range(0, 7):
            await self.bot.say("Slow down there partner.")
            return
        self.gun[ctx.message.server.id] = [0, 0, 0, 0, 0, 0]
        while sum(self.gun[ctx.message.server.id]) < bullets:
            self.gun[ctx.message.server.id][random.randint(0, 5)] = 1
        await self.bot.say("There are now {} bullets in the gun.".format(bullets))


def setup(bot):
    bot.add_cog(RNG(bot))
