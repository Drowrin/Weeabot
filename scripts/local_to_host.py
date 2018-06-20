# upload existing local stub images to discord messages.
# future stub images will simply refer to discord hosted links.

import os
import asyncio
import json
import discord
from weeabot import Weeabot

DEBUG = False
GUILD_ID = 000000000000000000
CHANNEL_ID = 000000000000000000
path_to_tag_json = ''
root_image_folder = ''

bot = Weeabot(os.path.join('..', 'config', 'config.yml'), command_prefix='$')

async def local_to_host():
    await bot.init.wait()
    guild: discord.Guild = discord.utils.get(bot.guilds, id=GUILD_ID)
    channel: discord.TextChannel = discord.utils.get(guild.channels, id=CHANNEL_ID)

    with open(path_to_tag_json, 'r') as f:
        old_tags = json.load(f)

    # limit to only fist so many tags to test settings
    # remove the last index when ready for a real run
    stubs = old_tags['items'][:10]

    i = 0
    total = len(stubs)
    for stub in stubs:
        i += 1
        if stub is not None and stub['image'] is not None:
            image_path = os.path.join(root_image_folder, *stub['image'][1:])
            image_file = discord.File(image_path)
            message: discord.Message = await channel.send(file=image_file)
            stub['image'] = message.attachments[0].url
            print(f'{i}/{total} ({i/float(total):.2%}): {stub["image"]}')
            await asyncio.sleep(1)

    with open('output.json', 'w') as f:
        json.dump(old_tags, f)

    print('complete!')
    if DEBUG:
        print(json.dumps(stubs, indent=2))
    await channel.send('upload completed and tag data saved.')

if __name__ == '__main__':
    bot.loop.create_task(local_to_host())
    bot.run()

