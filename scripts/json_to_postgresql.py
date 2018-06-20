# imports legacy json data (with image links, not local paths. see local_to_host.py)
# into current postgresql db (may eventually convert to edgedb and will need new script)

import os
import json
import asyncio
import discord
from tqdm import tqdm
from datetime import datetime
from weeabot import Weeabot

path_to_tag_json = 'output.json'  # to directly take output of local_to_host.py

bot = Weeabot(os.path.join('..', 'config', 'config.yml'), command_prefix='$')


async def json_to_postgresql():
    await bot.init.wait()
    await asyncio.sleep(1)  # wait for other initialization prints

    with open(path_to_tag_json, 'r') as f:
        old_tags = json.load(f)

    # limit to only fist so many tags to test settings
    # remove the last index when ready for a real run
    # could also filter to specific indices here
    stubs = old_tags['items']

    skipped_inds = []

    for i, item in enumerate(tqdm(stubs)):
        try:
            await bot.db.create_stub(
                author=discord.Object(id=int(item['author'])),
                tags=item['tags'],
                timestamp=datetime.strptime(
                    item['timestamp'].split('.')[0],
                    "%Y-%m-%d %X"
                ),
                guild=discord.Object(id=000000000000000000),  # server to own imports
                text=item['text'],
                method=item['method'],
                is_global=True,  # set to false if you want above server to only have access
                image=item['image']
            )
        except ValueError as e:
            print(f'On: {item["item_id"]}')
            raise e
        except TypeError:
            skipped_inds.append(str(i))

    await asyncio.sleep(.5)
    print(f'Completed. Skipped: {", ".join(skipped_inds)}')


if __name__ == '__main__':
    bot.loop.create_task(json_to_postgresql())
    bot.run()
