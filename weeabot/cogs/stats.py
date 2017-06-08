from weeabot import utils
from . import base_cog


class Stats(base_cog(shortcut=True)):
    """
    Track usage.
    """

    filter = ['debug', 'exec', 'help', 'req', 'profile']

    def __init__(self, bot):
        super(Stats, self).__init__(bot)
        self.data = utils.Storage('config', 'trusted.json')

    async def inc_use(self, uid, fcn):
        if any([x in fcn for x in self.filter]):
            return
        if fcn not in self.data.command_use:
            self.data.command_use[fcn] = 0
        self.data.command_use[fcn] += 1
        await self.data.save()
        if self.bot.profiles is not None:
            c = await self.bot.profiles.get_field_by_id(uid, 'command_count')
            if fcn not in c:
                c[fcn] = 0
            c[fcn] += 1
            await self.bot.profiles.save()

    async def on_command_completion(self, ctx):
        fcn = utils.full_command_name(ctx.command)
        await self.inc_use(ctx.message.author.id, fcn)


def setup(bot):
    bot.add_cog(Stats(bot))
