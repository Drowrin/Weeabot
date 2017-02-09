import random

import discord
from discord.ext import commands

import checks


class RNG:
    """Commands based on a randomly selected value."""

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

    @commands.command(pass_context=True, aliases=('a', 'shoot', 'kill',))
    @checks.profiles()
    async def attack(self, ctx, target: str=None):
        """Attempt to attack some users."""
        
        if target is None:
            await self.bot.say(random.choice(self.atk['miss']))
            return
        
        author = ctx.message.author
        selves = [author.mention, author.name, author.display_name] + self.atk['self']
        immune = [self.bot.user.mention, self.bot.user.name, self.bot.user.display_name]

        if target in immune:
            await self.bot.say(random.choice(self.atk['immune']).format(author.display_name, target))
        elif target in selves:
            await self.bot.say(random.choice(self.atk['kys']).format(author.display_name))
        else:
            if random.randint(0, 1):
                await self.bot.say(random.choice(self.atk['el']).format(target))
            else:
                await self.bot.say(random.choice(self.atk['esc']).format(target))

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
