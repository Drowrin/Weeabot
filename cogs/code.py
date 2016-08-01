import discord
from discord.ext import commands


class Code:
    """Code related commands."""

    def __init__(self, bot):
        self.bot = bot

    @command.command(aliases=('bf',))
    async def brainfuck(self, *, s: str):
        """Simple Brainfuck interpreter.

        If execution takes more than a few seconds it will be terminated.
        It is assumed that the code was in an infinite loop or the workload was unreasonably large."""
        args = s.split('```')
        inp = args[0]
        s = ''.join(filter(lambda x: x in ['.', ',', '[', ']', '<', '>', '+', '-'], args[1].strip('`')))
        await self.bot.say('cleaned bf:\n```\n{}\n```'.format(s))
        if "." not in s:
            await self.bot.say("There is no output, what does it even do?")
            return
        if s.count('[') != s.count(']'):
            await self.bot.say('Brace mismatch.')
            return
        temp_bracestack, bracemap = [], {}
        for position, command in enumerate(s):
            if command == "[":
                temp_bracestack.append(position)
            if command == "]":
                start = temp_bracestack.pop()
                bracemap[start] = position
                bracemap[position] = start
        ce = [0]
        cop = 0
        cep = 0
        printstr = ""
        t = time.time()
        while cop < len(s):
            if t + 5 < time.time():
                await self.bot.say("took too long, possible infinite loop.")
                return
            command = s[cop]

            if command == ">":
                cep += 1
                if cep == len(ce):
                    ce.append(0)
            if command == "<":
                cep = 0 if cep <= 0 else cep - 1
            if command == "+":
                ce[cep] = ce[cep] + 1 if ce[cep] < 255 else 0
            if command == "-":
                ce[cep] = ce[cep] - 1 if ce[cep] > 0 else 255
            if command == "[" and ce[cep] == 0:
                cop = bracemap[cop]
            if command == "]" and ce[cep] != 0:
                cop = bracemap[cop]
            if command == ".":
                printstr += chr(ce[cep])
            if command == ",":
                ce[cep] = -1 if inp is None or inp == '' else ord(inp[0])
                inp = inp[1:]
            cop += 1
        await self.bot.say("Output:\n {}".format(printstr))


def setup(bot):
    bot.add_cog(Code(bot))
