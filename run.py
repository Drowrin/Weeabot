import os

from weeabot import Weeabot

bot = Weeabot(os.path.join('config', 'config.yml'), command_prefix='$')

if __name__ == '__main__':
    bot.run()
