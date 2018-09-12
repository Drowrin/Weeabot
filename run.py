#!/usr/bin/env python3
import os
import sys

# workaround
import socket
socket.SO_REUSEPORT = 15

from weeabot import Weeabot


if len(sys.argv) > 1:
    config_path = sys.argv[1]
else:
    config_path = os.path.join('config', 'config.yml')

bot = Weeabot(config_path)

if __name__ == '__main__':
    bot.run()
