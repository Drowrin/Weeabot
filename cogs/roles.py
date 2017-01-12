from collections import defaultdict

import discord
from discord.ext import commands

import checks
from cogs.requestsystem import request, RequestLevel
from Weeabot import Weeabot

class Roles:

    def __init__(self, bot: Weeabot):
         self.bot = bot

    async def check_config( self, ctx ):
        if ctx.message.server.id not in self.bot.server_configs:
            self.bot.server_configs[ctx.message.server.id] = {}
        if 'hidden_channels' not in self.bot.server_configs[ctx.message.server.id]:
            self.bot.server_configs[ctx.message.server.id]['hidden_channels'] = {}

    async def get_roles_list( self, ctx ):
        await self.update_roles(ctx)
        roles_list = defaultdict(list)
        await self.check_config( ctx )
        for chan, r in self.bot.server_configs[ ctx.message.server.id ][ "hidden_channels" ].items():
            chann = ctx.message.server.get_channel( chan )
            for role in r:
                roles_list[ role ].append( chann )
        return roles_list

    async def update_roles( self, ctx ):
        for chan_id, r in self.bot.server_configs[ ctx.message.server ][ 'hidden_channels' ].items():
            rs = [ t[0].id for t in ctx.message.server.get_channel(id).overwrites if t[1].read_messages ]
            self.bot.server_configs[ ctx.message.server ][ 'hidden_channels' ][chan_id] = rs

    @commands.command(pass_context=True)
    @checks.is_server_owner()
    async def hide( self, ctx ):
        await self.check_config( ctx )
        await self.bot.edit_channel_permissions(
            channel=ctx.message.channel,
            target=ctx.message.server.default_role,
            overwrite=discord.PermissionOverwrite(read_messages=False)
        )
        await self.update_roles( ctx )

    @commands.command(pass_context=True)
    @request(level=RequestLevel.server, owner_bypass=False)
    async def make_channel( self, ctx, channel_name, role_name ):
        await self.check_config( ctx )
        try:
            everyone_perms = discord.PermissionOverwrite(read_messages=False)
            everyone = discord.ChannelPermissions(target=ctx.message.server.default_role, overwrite=everyone_perms)
            can_read = discord.PermissionOverwrite(read_messages=True)
            new_role = await self.bot.create_role( ctx.message.server, name=role_name )
            channel = await self.bot.create_channel(ctx.message.server, channel_name, everyone, ( new_role , can_read ))
            await self.bot.add_roles( ctx.message.author, new_role )
            self.bot.server_configs[ctx.message.server]['hidden_channels'][channel.id] = [new_role.id]

        except discord.errors.HTTPException:
            await self.bot.say("Invalid name or that name is taken. Names must be alphanumeric.")
    
    @commands.command(pass_context=True)
    async def roles( self, ctx ):
        roles = await self.get_roles_list(ctx)
        e: discord.Embed = discord.Embed(
            title="Opt-in Roles"
        )
        message = ""
        for role, channels in roles.items():
            role_name = commands.RoleConverter( ctx, role ).convert().name
            for channel in channels:
                message += f'__{channel.name}__\n\t{channel.topic}\n'
            e.add_field(name=role_name, value=message, inline=False)
        await self.bot.say( embed = e )
    
    @commands.command(pass_context=True)
    async def makeme(self, ctx, role : discord.Role):
        roles = await self.get_roles_list( ctx )
        if role.id not in roles:
            await self.bot.say( "Sorry, that role isn't an opt-in role.")
            return       
        await self.bot.add_roles( ctx.message.author, role )

def setup(bot):
    bot.add_cog(Roles(bot))
