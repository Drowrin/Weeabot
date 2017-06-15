import discord
from discord.ext import commands
from . import augmenter


@augmenter.add(commands.Command)
class Command:
    """
    Added functionality to commands.Command
    """
