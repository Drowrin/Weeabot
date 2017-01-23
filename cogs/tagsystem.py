import os
import json
import random
import aiohttp
import re
import copy
from collections import defaultdict

import discord
from discord.ext import commands

import utils
from cogs.requestsystem import request

import checks


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

    async def baka(self, ctx):
        await ctx.bot.get_cog("Images").baka_image(ctx, ctx.message.author.display_name)

    async def embed(self, ctx):
        constructors = ["title", "description", "url", "timestamp", "colour"]
        content = json.loads(self.text)
        if "colour" in content and isinstance(content["colour"], str):
            try:
                content["colour"] = commands.MemberConverter(ctx, content["colour"].split(":")[1]).convert().colour.value
            except commands.BadArgument:
                await ctx.bot.say("Note: Could not find color member.")

        e = discord.Embed(**{k: v for k, v in content.items() if k in constructors})
        e.timestamp = discord.utils.parse_time(self.timestamp)
        try:
            e.set_footer(text=self.detail(ctx), icon_url=ctx.bot.content.icons['tag'])
        except KeyError:
            e.set_footer(text=self.detail(ctx))

        if "image" in content:
            try:
                e.set_image(**content['image'])
            except TypeError:
                try:
                    m = commands.MemberConverter(ctx, content['image']).convert()
                    e.set_image(url=m.avatar_url)
                except commands.BadArgument:
                    await ctx.bot.say("Note: Could not find member for image.")
        if "thumbnail" in content:
            try:
                e.set_thumbnail(**content['thumbnail'])
            except TypeError:
                try:
                    m = commands.MemberConverter(ctx, content['thumbnail']).convert()
                    e.set_thumbnail(url=m.avatar_url)
                except commands.BadArgument:
                    await ctx.bot.say("Note: Could not find member for thumbnail.")
        if "author" in content:
            try:
                e.set_author(**content['author'])
            except TypeError:
                try:
                    m = commands.MemberConverter(ctx, content['author']).convert()
                    e.set_author(name=m.display_name, icon_url=m.avatar_url)
                except commands.BadArgument:
                    await ctx.bot.say("Note: Could not find author.")
        if "fields" in content:
            for f in content['fields']:
                e.add_field(**f)

        await ctx.bot.send_message(ctx.message.channel, embed=e)

    async def alias(self, ctx):
        m = copy.copy(ctx.message)
        if m.content.startswith(f'{ctx.bot.command_prefix}tag '):
            args = ' ' + ' '.join(m.content.split(' ')[2:])
        else:
            args = ' ' + ' '.join(m.content.split(' ')[1:])
        m.content = self.text + args
        await ctx.bot.process_commands(m)

    methods = defaultdict(lambda: TagItem.none)
    methods.update({None: none, "simple": simple, "baka": baka, "embed": embed, "alias": alias})

    def __init__(self, author: str, timestamp: str, tags: iter, item_id: int = None, method: str = None,
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

    def detail(self, ctx):
        if ctx.message.channel.is_private:
            name = discord.utils.get(ctx.bot.get_all_members(), id=self.author).name
        else:
            try:
                name = ctx.message.server.get_member(self.author).display_name
            except AttributeError:
                name = discord.utils.get(ctx.bot.get_all_members(), id=self.author).name
        return "{}(id:{}) by {}".format(', '.join(self.tags), self.id, name)

    def str(self, ctx):
        return "{} at {}{}".format(self.detail(ctx), self.timestamp, '' if self.text is None else ('\n' + self.text))

    async def run(self, ctx):
        """Perform the action specific to this tag."""
        await self.methods[self.method](self, ctx)


class TagMap:
    """Data structure similar to a map, but items can have multiple keys.
    Unlike a map, the structure is intended for getting 'an item, any item' matching a description.
    Since it is sometimes necessary to remove or edit items, they can still be accessed by unique indexes."""

    def __init__(self, bot: commands.Bot, json_path: str='tag_database.json'):
        """Construct a TagMap from a json file specified by path."""
        self.bot = bot
        self.path = json_path
        json_data = utils.open_json(self.path) or {"tags": {}, "items": []}
        self._tags = defaultdict(list)
        self._tags.update(json_data["tags"])
        self._items = [None if v is None else TagItem(**v) for v in json_data["items"]]
        self.dump()

    def dump(self):
        """Save the TagMap to the path given originally as a json file."""
        with open(self.path, 'w') as f:
            json.dump({"tags": dict(self._tags),
                       "items": [None if i is None else i.as_json() for i in self._items]}, f, ensure_ascii=True)

    def get(self, message, item, predicate=None):
        if item not in self._tags:
            raise KeyError
        if predicate is not None:
            items = [x for x in self._tags[item] if predicate(self._items[x])]
        else:
            items = self._tags[item]
        if len(items) == 0:
            return None
        self.bot.inc_use(message.author.id, "tag " + item)
        return self._items[random.choice(items)]

    def __setitem__(self, key, value):
        """Add a new item and assign it a tag."""
        try:
            index = next((i for i, x in enumerate(self._items) if x is None))
            value.id = index
            self._items[index] = value
        except StopIteration:
            index = len(self._items)
            value.id = index
            self._items.append(value)
            self._items.append(None)
        self._tags[key.lower()].append(index)
        self.dump()

    def __len__(self):
        return len(self._items)

    @property
    def taglist(self):
        """List of all tags."""
        return self._tags.keys()

    def add_tag(self, item_id: int, name: str):
        """Add a tag to an already existing item. If an item already has that tag, it will not be duplicated."""
        if name in self.get_by_id(item_id).tags:
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
                self.delete(item)
        self.dump()

    def delete(self, item: int):
        for t in self.get_by_id(item).tags:
            self._tags[t] = [x for x in self._tags[t] if x != item]
        self._items[item] = None
        d = defaultdict(list)
        d.update({t: self._tags[t] for t in self._tags if len(self._tags[t]) > 0})
        self._tags = d
        self.dump()

    def get_all_tag(self, name: str):
        """Get all items with a specific tag."""
        return self._tags[name]

    def get_by_id(self, item_id: int):
        """Get an item by its unique id."""
        t = self._items[item_id]
        if t is None:
            raise IndexError
        return t

    def set_by_id(self, item_id: int, item):
        """Set an item by its unique id."""
        self._items[item_id] = item
        self.dump()

    @commands.group(pass_context=True, invoke_without_command=True)
    async def tag(self, ctx, name):
        """Get a random tag matching the name."""
        try:
            t = self.get(ctx.message, name)
            if t is not None:
                self.bot.inc_use(ctx.message.author.id, "tag " + name)
                await t.run(ctx)
        except KeyError:
            await self.bot.say('Tag "{}" not found.'.format(name))

    @tag.command(pass_context=True, name='id')
    async def _tag_id(self, ctx, item_id: int):
        """Get a tag by id."""
        try:
            await self.get_by_id(item_id).run(ctx)
        except IndexError:
            await self.bot.say("id not found.")

    @tag.command(name='list')
    async def _tag_list(self):
        """List the available tags."""
        await self.bot.say("Tags: " + ", ".join(self.taglist))

    @tag.command(pass_context=True, name='add')
    @request(bypasses=(lambda ctx: len(ctx.message.attachments) == 0,))
    @checks.is_owner()
    @checks.is_moderator()
    async def _tag_add(self, ctx, name: str, *, text: str=''):
        """Add a tag to the database.

        Tag names must be alphanumeric, and must contain at least one letter to differentiate from tag IDs."""
        if not name.isalnum():
            await self.bot.say("Tag names must be alphanumeric.")
            return
        if name.isdigit():
            await self.bot.say("Tags can not be only numbers.")
            return
        i_path = None
        if len(ctx.message.attachments) > 0:
            async with aiohttp.ClientSession() as session:
                link = ctx.message.attachments[0]['url']
                n = "{}.{}".format(str(hash(link[-10:])), link.split('.')[-1])
                await utils.download(session, link, os.path.join('images', n))
                i_path = os.path.join('images', n)
        if text == '' and i_path is None:
            await self.bot.say("Can not create empty tag.")
            return
        t = TagItem(ctx.message.author.id, str(ctx.message.timestamp), [name], text=text or None, image=i_path)
        self[name] = t
        await self.bot.say(f'{ctx.message.author.mention} added a new tag to "{name}"')
        await t.run(ctx)

    @tag.command(pass_context=True, name='embed')
    @request(bypasses=(lambda ctx: len(ctx.message.attachments) == 0,))
    @checks.is_owner()
    @checks.is_moderator()
    async def _tag_embed(self, ctx, name: str, *, values):
        """Add an embed tag to the database.

        More complicated than regular tags, but also fancier.
        It is important to note that no files are saved. If images linked to are deleted, they will no longer display.
        Use the ~embed tag to see what fields can be set and what they do.

        To set a field:
            ~tag embed <name> <field> = <content>
        You can set multiple fields:
            ~tag embed <name> <field> = <content> <field2> = <content2>
        If a value has multiple words, you can put the content in quotes:
            ~tag embed <name> <field> = "<content> <with spaces>" <field2>=<content2>

        Fields and possible values:
            title: text
            description: text
            url: url
            color/colour: hex code, usertag (will take that user's color)
            image/thumbnail: url, usertag (will take that user's avatar)
            author: usertag, comma seperated name and avatar url (avatar url and comma can be left out)
        Anything else will become a custome field.
        """
        if not name.isalnum():
            await self.bot.say("Tag names must be alphanumeric.")
            return
        if name.isdigit():
            await self.bot.say("Tags can not be only numbers.")
            return
        if len(values) == 0:
            await self.bot.say("Can not create empty tag.")
            return

        reg = re.compile(r'(\S+\s*=\s*("?)[^"]+?[^"\s]+\2)')
        fields = [r[0] for r in reg.findall(values)]
        if len(fields) == 0:
            await self.bot.say("No valid values found.")
            return

        data = {}

        for f in fields:
            try:
                ftype, content = f.split('=')
            except ValueError:
                await self.bot.say("Invalid formatting: `{}`".format(f))
                return

            ftype = ftype.strip()
            content = content.strip('" ')

            if ftype in ("title", "description", "url"):
                data[ftype] = content
            elif ftype in ("color", "colour"):
                try:
                    data["colour"] = "member:" + commands.MemberConverter(ctx, content).convert().id
                except commands.BadArgument:
                    try:
                        data["colour"] = int(content, 16)
                    except ValueError:
                        await self.bot.say("Not a valid hex code: {}".format(content))
                        return
            elif ftype in ("image", "thumbnail"):
                try:
                    data[ftype] = commands.MemberConverter(ctx, content).convert().id
                except commands.BadArgument:
                    data[ftype] = {"url": content}
            elif ftype == "author":
                try:
                    data[ftype] = commands.MemberConverter(ctx, content).convert().id
                except commands.BadArgument:
                    if ',' in content:
                        d = content.split(',')
                        data[ftype] = {"name": d[0].strip(' '), "icon_url": d[1].strip(' ')}
                    else:
                        data[ftype] = {"name": content}
            else:
                if "fields" not in data:
                    data["fields"] = []
                data["fields"].append({"name": ftype, "value": content, "inline": True})

        datastring = json.dumps(data)
        t = TagItem(ctx.message.author.id, str(ctx.message.timestamp), [name], text=datastring, image=None)
        t.method = "embed"
        self[name] = t
        await t.run(ctx)

    @tag.command(pass_context=True, name='alias')
    @request(delete_source=False)
    async def _tag_alias(self, ctx, name: str, *, text: str):
        """Add an alias for a command."""
        if not name.isalnum():
            await self.bot.say("Tag names must be alphanumeric.")
            return
        if name.isdigit():
            await self.bot.say("Tags can not be only numbers.")
            return
        if text == '':
            await self.bot.say("Can not create empty tag.")
        if not text.startswith(self.bot.command_prefix):
            text = self.bot.command_prefix + text
        t = TagItem(ctx.message.author.id, str(ctx.message.timestamp), [name], text=text, method='alias')
        self[name] = t
        await self.bot.say(f'{ctx.message.author.mention} added a new alias: `{name}` → `{text}`')
        await t.run(ctx)

    @tag.command(pass_context=True, name='addtags')
    @request()
    async def _addtags(self, ctx, item_id: int, *names):
        """Add tags to a response."""
        try:
            for n in names:
                if n.isdigit():
                    await self.bot.say("{}: tags can not be numbers".format(n))
                else:
                    self.add_tag(item_id, n)
        except IndexError:
            await self.bot.say("Response id not found.")
            return
        await self.get_by_id(item_id).run(ctx)

    @tag.command(pass_context=True, alias=('author',))
    @request()
    async def credit(self, ctx, item_id: int, user: discord.Member):
        """credit a tag to a user."""
        try:
            self.get_by_id(item_id).author = user.id
            self.dump()
            await self.get_by_id(item_id).run(ctx)
        except IndexError:
            await self.bot.say("id not found.")

    @tag.command(pass_context=True)
    @request()
    async def claim(self, ctx, item_id: int):
        """Claim a tag. Useful for tags imported from before author was tracked, or tags readded by others."""
        try:
            self.get_by_id(item_id).author = ctx.message.author.id
            self.dump()
            await self.get_by_id(item_id).run(ctx)
        except IndexError:
            await self.bot.say("id not found.")

    @tag.command(name='remove')
    @request()
    async def _tag_remove(self, target: str, *tags):
        """Remove items or remove tags from an item.

        Input just an id to remove an item.
        Input an id and one or more tag names to remove those tags from the item. items with 0 tags are removed.
        Input a tag name to remove a tag."""
        if target in self.taglist:
            self.remove_tag(target)
        else:
            try:
                t = self.get_by_id(int(target))
            except (IndexError, ValueError):
                await self.bot.say("{} not found.".format(target))
                return
            if len(tags) > 0:
                for name in tags:
                    if name in t.tags:
                        t.tags.remove(name)
                    else:
                        await self.bot.say("id {} does not have {}.".format(target, name))
                if len(t.tags) == 0:
                    self.delete(int(target))
            else:
                self.delete(int(target))
        self.dump()

    @tag.command(pass_context=True, name='edit')
    @request()
    @checks.is_owner()
    @checks.is_moderator()
    async def _tagedit(self, ctx, item_id: int, *, content: str):
        """edit the contents of a tag."""
        try:
            self.get_by_id(item_id).text = content
            if len(ctx.message.attachments) > 0:
                async with aiohttp.ClientSession() as session:
                    link = ctx.message.attachments[0]['url']
                    n = "{}.{}".format(str(hash(link[-10:])), link.split('.')[-1])
                    await utils.download(session, link, os.path.join('images', n))
                    self.get_by_id(item_id).image = os.path.join('images', n)
            else:
                self.get_by_id(item_id).image = None
            self.dump()
        except IndexError:
            await self.bot.say("Response id not found.")
            return
        await self.get_by_id(item_id).run(ctx)

    @tag.command(pass_context=True, name='tagmethod')
    @request()
    async def _tagmethod(self, ctx, item_id: int, method: str):
        """Set the method a tag uses."""
        try:
            self.get_by_id(item_id).method = method
            self.dump()
        except IndexError:
            await self.bot.say("Response id not found.")
            return
        await self.get_by_id(item_id).run(ctx)


def setup(bot):
    bot.add_cog(TagMap(bot))
