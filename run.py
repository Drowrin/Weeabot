import os
import re
import sys
import traceback
import textwrap

from weeabot import Weeabot
from weeabot.cogs.stats import do_not_track

import discord

bot = Weeabot(os.path.join('config', 'config.yml'), command_prefix='$')

if __name__ == '__main__':
    bot.run()
