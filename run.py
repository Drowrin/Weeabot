import os

from weeabot import Weeabot

bot = Weeabot(os.path.join('config', 'config.yml'))

if __name__ == '__main__':
    bot.run()
