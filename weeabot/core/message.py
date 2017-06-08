import discord

from weeabot import utils


class Message(utils.wrapper(discord.Message)):
    """
    discord.Message with some additions.
    """

    async def safe_react(self, emoji):
        """
        Respond to a message with an emoji.

        Will use a method based on permissions.
        In order of priority: react, send message, PM
        """
        perms = self.channel.permissions_for(self.channel.guild.me)

        if perms.add_reactions:
            await self.add_reaction(emoji)
        elif perms.send_messages:
            await self.channel.send(emoji)
        else:
            await self.author.send(emoji)

    async def affirmative(self):
        """
        Respond with an affirmative emoji.

        Will use a method based on permissions.
        In order of priority: react, send message, PM
        """
        await self.safe_react('\N{OK HAND SIGN}')

    async def negative(self):
        """
        Respond with a negative emoji.

        Will use a method based on permissions.
        In order of priority: react, send message, PM
        """
        await self.safe_react('\N{CROSS MARK}')

    async def confirm(self, user=None):
        """
        Use reactions to get a Yes/No response from the user.
        """
        reactions = ('\N{THUMBS UP SIGN}', '\N{THUMBS DOWN SIGN}')
        user = user or self.author

        await self.add_reaction(reactions[0])
        await self.add_reaction(reactions[1])

        def check(r, u):
            return r.message.id == self.id and r.emoji in reactions and u == user

        reaction = await self.__client.wait_for('reaction_add', check=check)
        return reaction[0].emoji == reactions[0]
