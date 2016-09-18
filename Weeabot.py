# noinspection PyUnresolvedReferences
import discord
# noinspection PyUnresolvedReferences
from discord.ext import commands

# noinspection PyUnresolvedReferences
import random
import traceback
import asyncio

from collections import defaultdict

from utils import *
import os


class TagItem:
    """Data class containing a response to a tag."""

    async def none(self, ctx):
        if self.image is not None:
            await ctx.bot.send_file(ctx.message.channel, self.image, content=self.str(ctx))
        else:
            await ctx.bot.send_message(ctx.message.channel, self.str(ctx))

    async def simple(self, ctx):
        if self.image is not None:
            await ctx.bot.send_file(ctx.message.channel, self.image, content=self.text)
        else:
            await ctx.bot.send_message(ctx.message.channel, self.text)

    methods = {None: none, "simple": simple}

    def __init__(self, author: str, timestamp: str, tags: list, item_id: int = None, method: str = None,
                 text: str = None, image: str = None, location: str = None):
        self.id = item_id
        self.author = author
        self.timestamp = timestamp
        self.tags = tags
        self.text = text
        self.image = image
        self.location = location
        self.method = method

    def as_json(self):
        """json safe value."""
        return {
            "item_id": self.id,
            "author": self.author,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "text": self.text,
            "image": self.image,
            "location": self.location,
            "method": self.method
        }

    def str(self, ctx):
        if ctx.message.channel.is_private:
            name = discord.utils.get(ctx.bot.get(ctx.bot.get_all_members(), id=self.author)).name
        else:
            name = ctx.message.server.get_member(self.author).display_name
        return "{}(id:{}) by {} at {}{}".format(', '.join(self.tags), self.id, name, self.timestamp,
                                                ('\n' + self.text) if self.text is not None else '')

    async def run(self, ctx):
        """Perform the action specific to this tag."""
        await self.methods[self.method](self, ctx)


class TagMap:
    """Data structure similar to a map, but items can have multiple keys.
    Unlike a map, the structure is intended for getting 'an item, any item' matching a description.
    Since it is sometimes necessary to remove or edit items, they can still be accessed by unique indexes."""

    def __init__(self, json_path: str):
        """Construct a TagMap from a json file specified by path."""
        self.path = json_path
        json_data = open_json(self.path) or {"tags": {}, "items": []}
        self._tags = defaultdict(list)
        self._tags.update(json_data["tags"])
        self._items = [TagItem(**v) for v in json_data["items"]]
        self.dump()

    def dump(self):
        """Save the TagMap to the path given originally as a json file."""
        with open(self.path, 'w') as f:
            json.dump({"tags": dict(self._tags), "items": [i.as_json() for i in self._items]}, f, ensure_ascii=True)

    def __getitem__(self, item):
        """Get an item that has the specified tag. Not unique."""
        if item not in self._tags:
            raise KeyError
        return self._items[random.choice(self._tags[item])]

    def __setitem__(self, key, value):
        """Add a new item and assign it a tag."""
        index = len(self._items)
        value.id = index
        self._items.append(value)
        self._tags[key].append(index)
        self.dump()

    @property
    def taglist(self):
        """List of all tags."""
        return self._tags.keys()

    def add_tag(self, item_id: int, name: str):
        """Add a tag to an already existing item. If an item already has that tag, it will not be duplicated."""
        if name in self._items[item_id].tags:
            return
        self._items[item_id].tags.append(name)
        self._tags[name].append(item_id)
        self.dump()

    def remove_tag(self, name: str):
        """remove a tag from the database. does not remove the items tagged with it unless they have 0 tags left."""
        items = self._tags.pop(name)
        for item in items:
            self._items[item].tags.remove(name)
            if len(self._items[item].tags) == 0:
                del self._items[item]
        self.dump()

    def get_all_tag(self, name: str):
        """Get all items with a specific tag."""
        return self._tags[name]

    def get_by_id(self, item_id: int):
        """Get an item by its unique id."""
        return self._items[item_id]

    def set_by_id(self, item_id: int, item):
        """Set an item by its unique id."""
        self._items[item_id] = item
        self.dump()


class Config:
    def __init__(self, config_path):
        self.path = config_path
        self._db = open_json(config_path)
        self.__dict__.update(self._db)

    def __getattr__(self, name):
        return self.__dict__.get(name, None)

    def _dump(self):
        for k in self._db:
            self._db[k] = self.__dict__[k]
        with open(self.path, 'w') as f:
            json.dump(self._db, f, ensure_ascii=True)

    async def save(self):
        await asyncio.get_event_loop().run_in_executor(None, self._dump)


class Weeabot(commands.Bot):
    """Simple additions to commands.Bot"""
    def __init__(self, *args, **kwargs):
        super(Weeabot, self).__init__(*args, **kwargs)
        self.owner = None  # set in on_ready
        self.config = Config('config.json')
        self.content = Config('content.json')
        self.server_configs = open_json('servers.json')
        self.status = open_json('status.json')
        self.tag_map = TagMap('tag_database.json')
        self.services = {}
        self.formatters = {}
        self.verbose_formatters = {}
        self.defaults = {}
        self.load_extension('cogs.profiles')
        self.load_extension('cogs.tools')
        self.loop.create_task(self.load_extensions())

    def dump_server_configs(self):
        with open('servers.json', 'w') as f:
            json.dump(self.server_configs, f, ensure_ascii=True)

    def dump_status(self):
        with open('status.json', 'w') as f:
            json.dump(self.status, f, ensure_ascii=True)
    
    @property
    def profiles(self):
        return self.get_cog('Profile')
    
    @property
    def tools(self):
        return self.get_cog('Tools')

    async def load_extensions(self):
        """Load extensions and handle errors."""
        await self.wait_until_ready()
        for ext in self.config.base_extensions:
            try:
                self.load_extension(ext)
            except Exception as e:
                await self.send_message(self.owner, 'Failure loading {}\n{}: {}\n'.format(ext, type(e).__name__, e))

    async def update_owner(self):
        await self.wait_until_ready()
        self.owner = (await self.application_info()).owner

    def add_cog(self, cog):
        super(Weeabot, self).add_cog(cog)
        self.services.update(getattr(cog, 'services', {}))
        self.formatters.update(getattr(cog, 'formatters', {}))
        self.verbose_formatters.update(getattr(cog, 'verbose_formatters', {}))
        self.defaults.update(getattr(cog, 'defaults', {}))

    def remove_cog(self, name):
        cog = self.get_cog(name)
        if hasattr(cog, 'formatters'):
            for f in cog.formatters:
                del self.formatters[f]
        if hasattr(cog, 'verbose_formatters'):
            for f in cog.verbose_formatters:
                del self.verbose_formatters[f]
        if hasattr(cog, 'defaults'):
            for d in cog.defaults:
                del self.defaults[d]
        super(Weeabot, self).remove_cog(name)

    async def notify(self, message: str):
        await self.say(message)
        await self.send_message(self.owner, message)

desc = """
Weeabot
I have a lot of (mostly) useless commands. Enjoy!
"""
bot = Weeabot(command_prefix='~', description=desc)


@bot.command(name='services')
async def service_command():
    """Show how to use non-command features of the bot."""
    fmt = '```\n{}:\n\n{}\n```'
    await bot.say('\n'.join([fmt.format(k, v) for k, v in bot.services.items()]))


@bot.group(aliases=('e',), invoke_without_command=True)
@is_owner()
async def extensions():
    """Extension related commands.

    Invoke without a subcommand to list extensions."""
    await bot.say('Loaded: {}\nAll: {}'.format(' '.join(bot.cogs.keys()),
                                               ' '.join([x for x in os.listdir('cogs') if '.py' in x])))


@extensions.command(name='load', alises=('l',))
@is_owner()
async def load_extension(ext):
    """Load an extension."""
    # noinspection PyBroadException
    try:
        if not ext.startswith('cogs.'):
            ext = 'cogs.{}'.format(ext)
        bot.load_extension(ext)
    except Exception:
        await bot.say('```py\n{}\n```'.format(traceback.format_exc()))
    else:
        await bot.say('{} loaded.'.format(ext))


@extensions.command(name='unload', aliases=('u',))
@is_owner()
async def unload_extension(ext):
    """Unload an extension."""
    if ext in bot.config.required_extensions:
        await bot.say("{} is a required extension.".format(ext))
        return
    # noinspection PyBroadException
    try:
        bot.unload_extension(ext)
    except Exception:
        await bot.say('```py\n{}\n```'.format(traceback.format_exc()))
    else:
        await bot.say('{} unloaded.'.format(ext))


@extensions.command(name='reload', aliases=('r',))
@is_owner()
async def reload_extension(ext):
    """Reload an extension."""
    # noinspection PyBroadException
    try:
        if not ext.startswith('cogs.'):
            ext = 'cogs.{}'.format(ext)
        bot.unload_extension(ext)
        bot.load_extension(ext)
    except Exception:
        await bot.say('```py\n{}\n```'.format(traceback.format_exc()))
    else:
        await bot.say('{} reloaded.'.format(ext))


@bot.command(pass_context=True)
@is_server_owner()
async def autorole(ctx, role: str):
    """Automatically assign a role to new members."""
    try:
        role = commands.RoleConverter(ctx, role).convert()
    except commands.BadArgument:
        await bot.say("Can't find {}".format(role))
        return
    bot.server_configs.get(role.server.id, {})['autorole'] = role.id
    bot.dump_server_configs()
    await bot.say("New members will now be given the {} role.".format(role.name))


@bot.group(pass_context=True, invoke_without_command=True)
async def tag(ctx, name):
    """Get a random tag matching the name."""
    try:
        await bot.tag_map[name].run(ctx)
    except KeyError:
        await bot.say('Tag "{}" not found.'.format(name))


@tag.command(pass_context=True, name='id')
async def _tag_id(ctx, item_id: int):
    """Get a tag by id."""
    try:
        await bot.tag_map.get_by_id(item_id).run(ctx)
    except IndexError:
        await bot.say("id not found.")


@tag.command(name='list')
async def _tag_list():
    """List the available tags."""
    await bot.say(", ".join(bot.tag_map.taglist))


@tag.command(pass_context=True, name='add')
@request()
async def _tag_add(ctx, name: str, *, text: str=''):
    """Add a tag to the database."""
    i_path = None
    if len(ctx.message.attachments) > 0:
        async with aiohttp.ClientSession() as session:
            link = ctx.message.attachments[0]['url']
            n = "{}.{}".format(str(hash(link[-10:])), link.split('.')[-1])
            await download(session, link, os.path.join('images', n))
            i_path = os.path.join('images', n)
    t = TagItem(ctx.message.author.id, str(ctx.message.timestamp), [name], text=text or None, image=i_path)
    bot.tag_map[name] = t
    await t.run(ctx)


@tag.command(pass_context=True, name='addtags')
@request()
async def _addtags(ctx, item_id: int, *names):
    """Add tags to a response."""
    try:
        for n in names:
            bot.tag_map.add_tag(item_id, n)
    except IndexError:
        await bot.say("Response id not found.")
        return
    await bot.tag_map.get_by_id(item_id).run(ctx)


@tag.command(name='remove')
@request()
async def _removetags(*names):
    """Remove tags. The items will remain unless they reach 0 tags."""
    for name in names:
        if name in bot.tag_map.taglist:
            bot.tag_map.remove_tag(name)
        else:
            await bot.say('Tag "{}" not found.'.format(name))
    await bot.say("\N{OK HAND SIGN}")


@tag.command(pass_context=True, name='tagmethod')
@request()
async def _tagmethod(ctx, item_id: int, method: str):
    """Set the method a tag uses."""
    try:
        bot.tag_map.get_by_id(item_id).method = method
        bot.tag_map.dump()
    except IndexError:
        await bot.say("Response id not found.")
        return
    await bot.tag_map.get_by_id(item_id).run(ctx)


@bot.event
async def on_command_error(err, ctx):
    d = ctx.message.channel
    if type(err) is commands.NoPrivateMessage:
        await bot.send_message(d, '{} can not be used in private messages.'.format(ctx.command.name))
    elif type(err) is commands.DisabledCommand:
        await bot.send_message(d, 'This command is disabled.')
    elif type(err) in (commands.BadArgument, commands.errors.MissingRequiredArgument):
        await bot.send_message(d, 'Invalid usage. Use {}help {}'.format(bot.command_prefix, ctx.command.name))
    elif type(err) is commands.CheckFailure:
        if not str(err).startswith('The check functions'):
            await bot.send_message(d, err)
    elif type(err) is commands.CommandNotFound:
        if ctx.invoked_with in ctx.bot.tag_map.taglist:
            await ctx.bot.tag_map[ctx.invoked_with].run(ctx)
    else:
        raise err


@bot.event
async def on_server_join(server):
    """Called when the bot joins a server or creates one."""
    await bot.send_message(bot.owner, "Joined Server: {}".format(server))
    await bot.send_message(server.default_channel, "Hello! use ~help and ~services to see what I can do.")


@bot.event
async def on_member_join(member):
    """Called whenever a new member joins a server."""
    try:
        ar = bot.server_configs[member.server.id]['autorole']
        role = discord.utils.get(member.server.roles, id=ar)
        await bot.add_roles(member, role)
    except KeyError:
        pass


@bot.event
async def on_ready():
    await bot.update_owner()
    print('Bot: {0.name}:{0.id}'.format(bot.user))
    print('Owner: {0.name}:{0.id}'.format(bot.owner))
    print('------------------')


async def random_status():
    """Rotating statuses."""
    await bot.wait_until_ready()
    while not bot.is_closed:
        n = random.choice(bot.content.statuses)
        g = discord.Game(name=n, url='', type=0)
        await bot.change_status(game=g, idle=False)
        await asyncio.sleep(60)


if __name__ == '__main__':
    bot.loop.create_task(random_status())
    bot.run(tokens['discord_token'])
