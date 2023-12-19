'''
   Copyright (C) 2021-2022 Katelynn Cadwallader.

   This file is part of Gatekeeper, the AMP Minecraft Discord Bot.

   Gatekeeper is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 3, or (at your option)
   any later version.

   Gatekeeper is distributed in the hope that it will be useful, but WITHOUT
   ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
   or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public
   License for more details.

   You should have received a copy of the GNU General Public License
   along with Gatekeeper; see the file COPYING.  If not, write to the Free
   Software Foundation, 51 Franklin Street - Fifth Floor, Boston, MA
   02110-1301, USA. 

'''
from __future__ import annotations
import os
import logging
from datetime import datetime, timezone
import asyncio

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.app_commands import Choice
from numpy import isin

import AMP_Handler
import DB
import utils
import utils_ui
import utils_embeds
import modules.banner_creator as BC

# This is used to force cog order to prevent missing methods.
Dependencies = None


class AMP_Server(commands.Cog):
    def __init__(self, client: discord.Client):
        self._client = client
        self.name = os.path.basename(__file__)
        self.logger = logging.getLogger()

        self.AMPHandler = AMP_Handler.getAMPHandler()
        self.AMPInstances = self.AMPHandler.AMP_Instances
        self.AMPThreads = self.AMPHandler.AMP_Console_Threads

        self.DBHandler = DB.getDBHandler()
        self.DB = self.DBHandler.DB
        self.DBConfig = self.DBHandler.DBConfig

        self.uBot = utils.botUtils(client)
        self.dBot = utils.discordBot(client)
        self.uiBot = utils_ui
        self.eBot = utils_embeds.botEmbeds(client)
        self.BC = BC

        self.logger.info(f'**SUCCESS** Initializing {self.name.title().replace("Amp", "AMP")}')

    async def autocomplete_regex(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Autocomplete for Regex Pattern Names"""
        choice_list = []
        regex_patterns = self.DB.GetAllRegexPatterns()

        for regex in regex_patterns:
            choice_list.append(regex_patterns[regex]["Name"])
        return [app_commands.Choice(name=choice, value=choice) for choice in choice_list if current.lower() in choice.lower()][:25]

    async def autocomplete_server_regex(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Autocomplete for Regex Pattern Names"""
        choice_list = []

        if interaction.namespace.server != None:
            db_server = self.DB.GetServer(InstanceID=interaction.namespace.server)
            regex_patterns = db_server.GetServerRegexPatterns()

            if len(regex_patterns):
                for regex in regex_patterns:
                    choice_list.append(regex_patterns[regex]["Name"])
            else:
                choice_list.append('None')

        return [app_commands.Choice(name=choice, value=choice) for choice in choice_list if current.lower() in choice.lower()][:25]

    @commands.hybrid_group(name='server')
    @utils.role_check()
    async def server(self, context: commands.Context):
        if context.invoked_subcommand is None:
            await context.send('Please try your command again...', ephemeral=True, delete_after=self._client.Message_Timeout)

    @server.command(name='update')
    @utils.role_check()
    async def amp_server_update(self, context: commands.Context):
        """Updates the bot with any freshly created AMP Instances"""
        self.logger.command(f'{context.author.name} used AMP Server Update')
        new_server = self.AMPHandler._instanceValidation(AMP=self.AMPHandler.AMP)
        if new_server:
            await context.send(f'Found a new Server: {new_server}', ephemeral=True, delete_after=self._client.Message_Timeout)
        else:
            await context.send('Uhh.. No new instances were found. Hmmm...', ephemeral=True, delete_after=self._client.Message_Timeout)

    @server.command(name='broadcast')
    @utils.role_check()
    @app_commands.choices(prefix=[Choice(name=x, value=x) for x in ['Announcement', 'Broadcast', 'Maintenance', 'Info', 'Warning']])
    async def amp_server_broadcast(self, context: commands.Context, prefix: Choice[str], message: str):
        """This sends a message to every online AMP Server"""
        self.logger.command(f'{context.author.name} used AMP Server Broadcast')
        discord_message = await context.send('Sending Broadcast...', ephemeral=True)
        for amp_server in self.AMPInstances:
            if self.AMPInstances[amp_server].Running:
                if self.AMPInstances[amp_server]._ADScheck():
                    self.AMPInstances[amp_server].Broadcast_Message(message, prefix=prefix.value)

        await discord_message.edit(content=f'{prefix.value} Sent!')
        await discord_message.delete(delay=self._client.Message_Timeout)


# This section is AMP Server Commands ----------------------------------------------------------------------------------------------------------------------------------------------------------------


    @server.command(name='start')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_start(self, context: commands.Context, server):
        """Starts the AMP Instance"""
        self.logger.command(f'{context.author.name} used AMP Server Started...')
        await context.defer(ephemeral=True)

        amp_server = self.uBot.serverparse(server, context, context.guild.id)

        if not amp_server._ADScheck():
            amp_server.StartInstance()
            amp_server.ADS_Running = True
            await context.send(f'Starting the AMP Dedicated Server **{amp_server.InstanceName}**', ephemeral=True, delete_after=self._client.Message_Timeout)
        else:
            return await context.send(f'Hmm it appears the server is already `Running..`', ephemeral=True, delete_after=self._client.Message_Timeout)

    @server.command(name='stop')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_stop(self, context: commands.Context, server):
        """Stops the AMP Instance"""
        self.logger.command(f'{context.author.name} used AMP Server Stopped...')
        await context.defer(ephemeral=True)

        amp_server = await self.uBot._serverCheck(context, server)
        if amp_server:
            amp_server.StopInstance()
            amp_server.ADS_Running = False
            await context.send(f'Stopping the AMP Dedicated Server **{amp_server.InstanceName}**', ephemeral=True, delete_after=self._client.Message_Timeout)

    @server.command(name='restart')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_restart(self, context: commands.Context, server):
        """Restarts the AMP Instance"""
        self.logger.command(f'{context.author.name} used AMP Server Restart...')
        await context.defer(ephemeral=True)

        amp_server = await self.uBot._serverCheck(context, server)
        if amp_server:
            amp_server.RestartInstance()
            amp_server.ADS_Running = True
            await context.send(f'Restarting the AMP Dedicated Server **{amp_server.InstanceName}**', ephemeral=True, delete_after=self._client.Message_Timeout)

    @server.command(name='kill')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_kill(self, context: commands.Context, server):
        """Kills the AMP Instance"""
        self.logger.command(f'{context.author.name} used AMP Server Kill...')
        await context.defer(ephemeral=True)

        amp_server = await self.uBot._serverCheck(context, server)
        if amp_server:
            amp_server.KillInstance()
            amp_server.ADS_Running = False
            await context.send(f'Killing the AMP Dedicated Server **{amp_server.InstanceName}**', ephemeral=True, delete_after=self._client.Message_Timeout)

    @server.command(name='msg')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_message(self, context: commands.Context, server, message: str):
        """Sends a message to the Console, can be anything the Server Console supports.(Commands/Messages)"""
        self.logger.command(f'{context.author.name} used AMP Server Message...')

        amp_server = await self.uBot._serverCheck(context, server)
        if amp_server:
            amp_server.ConsoleMessage(message)
        await context.send(f'Sent {message} to {amp_server.InstanceName}', ephemeral=True, delete_after=self._client.Message_Timeout)

    @server.command(name='backup')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_backup(self, context: commands.Context, server):
        """Creates a Backup of the Server in its current state, setting the title to the Users display name."""
        self.logger.command(f'{context.author.name} used AMP Server Backup...')

        amp_server = await self.uBot._serverCheck(context, server)
        if amp_server:
            title = f"Backup by {context.author.display_name}"
            time = str(datetime.now(tz=timezone.utc))
            description = f"Created at {time} by {context.author.display_name}"
            display_description = f'Created at **{str(datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M"))}**(utc) by **{context.author.display_name}**'
            await context.send(f'Creating a backup of **{server.InstanceName}**  // **Description**: {display_description}', ephemeral=True, delete_after=self._client.Message_Timeout)
            amp_server.takeBackup(title, description)

    @server.command(name='status')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_status(self, context: commands.Context, server):
        """AMP Instance Status(TPS, Player Count, CPU Usage, Memory Usage and Online Players)"""
        self.logger.command(f'{context.author.name} used AMP Server Status...')
        await context.defer(ephemeral=True)

        amp_server = self.uBot.serverparse(server, context, context.guild.id)
        if amp_server == None:
            return await context.send(f"Hey, we uhh can't find the server **{amp_server.InstanceName}**. Please try your command again <3.", ephemeral=True, delete_after=self._client.Message_Timeout)

        if amp_server.Running == False:
            await context.send(f'Well this is awkward, it appears the **{amp_server.InstanceName}** is `Offline`.', ephemeral=True, delete_after=self._client.Message_Timeout)

        if amp_server._ADScheck():
            tps, Users, cpu, Memory, Uptime = amp_server.getMetrics()
            Users_online = ', '.join(amp_server.getUserList())
            if len(Users_online) == 0:
                Users_online = 'None'
            server_embed = await self.eBot.server_status_embed(context, amp_server, tps, Users, cpu, Memory, Uptime, Users_online)
            view = self.uiBot.StatusView(context=context, amp_server=amp_server)
            self.uiBot.ServerButton(amp_server, view, amp_server.StartInstance, 'Start', callback_label='Starting...', callback_disabled=True)
            self.uiBot.StopButton(amp_server, view, amp_server.StopInstance)
            self.uiBot.RestartButton(server, view, amp_server.RestartInstance)
            self.uiBot.KillButton(server, view, amp_server.KillInstance)
            await context.send(embed=server_embed, view=view, ephemeral=True)

        else:
            server_embed = await self.eBot.server_status_embed(context, amp_server)
            view = self.uiBot.StatusView()
            self.uiBot.StartButton(amp_server, view, amp_server.StartInstance)
            self.uiBot.StopButton(amp_server, view, amp_server.StopInstance).disabled = True
            self.uiBot.RestartButton(amp_server, view, amp_server.RestartInstance).disabled = True
            self.uiBot.KillButton(amp_server, view, amp_server.KillInstance).disabled = True
            await context.send(embed=server_embed, view=view, ephemeral=True)

    @server.command(name='users')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_users_list(self, context: commands.Context, server):
        """Shows a list of the currently connected Users to the Server."""
        self.logger.command(f'{context.author.name} used AMP Server Connected Users...')

        amp_server = await self.uBot._serverCheck(context, server)
        if amp_server:
            cur_users = (', ').join(amp_server.getUserList())
            if len(cur_users) != 0:
                await context.send("**Server Users**" + '\n' + cur_users, ephemeral=True, delete_after=self._client.Message_Timeout)
            else:
                await context.send('The Server currently has no online players.', ephemeral=True, delete_after=self._client.Message_Timeout)

# This Section is AMP/DB Server Settings -----------------------------------------------------------------------------------------------------
    @server.group(name='settings')
    @utils.role_check()
    async def amp_server_settings(self, context: commands.Context):
        if context.invoked_subcommand is None:
            await context.send('Please try your command again...', ephemeral=True, delete_after=self._client.Message_Timeout)

    @amp_server_settings.command(name='info')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_settings_info(self, context: commands.Context, server):
        """Displays Specific Server Information."""
        self.logger.command(f'{context.author.name} used AMP Server Info')
        await context.defer(ephemeral=True)

        amp_server = await self.uBot._serverCheck(context, server, False)
        if amp_server:
            embed = await self.eBot.server_info_embed(amp_server, context)
            await context.send(embed=embed, ephemeral=True, delete_after=self._client.Message_Timeout)

    @amp_server_settings.command(name='avatar')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_avatar(self, context: commands.Context, server, url: str):
        """Sets the Servers Avatar via url. Supports `webp`, `jpeg`, `jpg`, `png`, or `gif` if it's animated."""
        self.logger.command(f'{context.author.name} used Database Server Avatar Set')
        await context.defer()

        if not url.startswith('http://') and not url.startswith('https://'):
            return await context.send('Ooops, please provide a valid url. It must start with either `http://` or `https://`', ephemeral=True, delete_after=self._client.Message_Timeout)

        amp_server = await self.uBot._serverCheck(context, server, False)
        if amp_server:
            db_server = self.DB.GetServer(InstanceID=amp_server.InstanceID)
            db_server.Avatar_url = url
            if url == 'None':
                await context.send(f"Removed **{amp_server.InstanceName}** Avatar Icon.", ephemeral=True, delete_after=self._client.Message_Timeout)
                amp_server._setDBattr()
                return
            if await self.uBot.validate_avatar(db_server) != None:
                amp_server._setDBattr()  # This will update the AMPInstance Attributes
                await context.send(f"Set **{amp_server.InstanceName}** Avatar Icon. {url}", ephemeral=True, delete_after=self._client.Message_Timeout)
            else:
                await context.send(f'I encountered an issue using that url, please try again. Heres your url: {url}', ephemeral=True, delete_after=self._client.Message_Timeout)

    @amp_server_settings.command(name='displayname')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_displayname(self, context: commands.Context, server, name: str):
        """Sets the Display Name for the provided Server"""
        self.logger.command(f'{context.author.name} used Database Server Display Name')

        amp_server = await self.uBot._serverCheck(context, server, False)
        if amp_server:
            db_server = self.DB.GetServer(InstanceID=amp_server.InstanceID)
            if db_server.setDisplayName(name) != False:
                amp_server._setDBattr()  # This will update the AMPInstance Attributes
                await context.send(f"Set **{amp_server.InstanceName}** Display Name to `{name}`", ephemeral=True, delete_after=self._client.Message_Timeout)
            else:
                await context.send(f'The Display Name provided is not unique, this server or another server already has this name.', ephemeral=True, delete_after=self._client.Message_Timeout)

    @amp_server_settings.command(name='host')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_host(self, context: commands.Context, server, hostname: str):
        """Sets the host for the provided Server"""
        self.logger.command(f'{context.author.name} used Database Server Host')

        amp_server = await self.uBot._serverCheck(context, server, False)
        if amp_server:
            db_server = self.DB.GetServer(InstanceID=amp_server.InstanceID)
            db_server.Host = hostname
            amp_server._setDBattr()  # This will update the AMPInstance Attributes
            await context.send(f"Set **{amp_server.InstanceName}** Host to `{hostname}`", ephemeral=True, delete_after=self._client.Message_Timeout)

    @amp_server_settings.command(name='donator')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    @app_commands.choices(flag=[Choice(name='True', value=1), Choice(name='False', value=0)])
    async def amp_server_donator(self, context: commands.Context, server, flag: Choice[int] = 0):
        """Sets the Donator Only flag for the provided server."""
        self.logger.command(f'{context.author.name} used Database Donator Flag')

        amp_server = await self.uBot._serverCheck(context, server, False)
        if amp_server:
            self.DB.GetServer(InstanceID=amp_server.InstanceID).Donator = flag.value
            amp_server._setDBattr()  # This will update the AMPConsole Attributes
            return await context.send(f"Set **{amp_server.InstanceName}** Donator Only to `{flag.name if type(flag) == Choice else bool(flag)}`", ephemeral=True, delete_after=self._client.Message_Timeout)

    @amp_server_settings.command(name='role')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_discord_role_set(self, context: commands.Context, server, role: discord.Role):
        """Sets the Discord Role for the provided Server"""
        self.logger.command(f'{context.author.name} used Database Server Discord Role')

        amp_server = await self.uBot._serverCheck(context, server, False)
        if amp_server:
            self.DB.GetServer(amp_server.InstanceID).Discord_Role = role.id
            amp_server._setDBattr()  # This will update the AMPInstance Attributes
            await context.send(f'Set **{amp_server.InstanceName}** Discord Role to `{role.name}`', ephemeral=True, delete_after=self._client.Message_Timeout)

    @amp_server_settings.command(name='prefix')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_discord_prefix_set(self, context: commands.Context, server, server_prefix: str):
        """Sets the Discord Chat Prefix for the provided Server"""
        self.logger.command(f'{context.author.name} used Database Server Discord Chat Prefix')

        amp_server = await self.uBot._serverCheck(context, server, False)
        if amp_server:
            self.DB.GetServer(amp_server.InstanceID).Discord_Chat_prefix = server_prefix
            amp_server._setDBattr()  # This will update the AMPInstance Attributes
            await context.send(f'Set **{amp_server.InstanceName}** Discord Chat Prefix to `{server_prefix}`', ephemeral=True, delete_after=self._client.Message_Timeout)

    @amp_server_settings.command(name='hidden')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    @app_commands.choices(flag=[Choice(name='True', value=1), Choice(name='False', value=0)])
    async def amp_server_hidden(self, context: commands.Context, server, flag: Choice[int]):
        """Hides or Shows the Server from Autocomplete lists when *NON-Moderators* are using slash commands."""
        self.logger.command(f'{context.author.name} used Database Server Hidden')

        amp_server = await self.uBot._serverCheck(context, server, False)
        if amp_server:
            self.DB.GetServer(InstanceID=amp_server.InstanceID).Hidden = flag.value
            amp_server._setDBattr()  # This will update the AMPConsole Attributes
            return await context.send(f"The **{amp_server.InstanceName}** will now be {'Hidden' if flag.value == 1 else 'Shown'}", ephemeral=True, delete_after=self._client.Message_Timeout)

# This section is AMP Server Console Specific Settings -------------------------------------------------------------------------------------------------------------------------------------------------
    @server.group(name='console')
    @utils.role_check()
    async def amp_server_console_settings(self, context: commands.Context):
        if context.invoked_subcommand is None:
            await context.send('Invalid command passed...', ephemeral=True, delete_after=self._client.Message_Timeout)

    @amp_server_console_settings.command(name='channel')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_console_channel(self, context: commands.Context, server, channel: discord.abc.GuildChannel | None):
        """Sets the Console Channel for the provided Server"""
        self.logger.command(f'{context.author.name} used Database Server Console Channel')

        amp_server = await self.uBot._serverCheck(context, server, False)
        if amp_server:
            if isinstance(channel, discord.abc.GuildChannel):
                self.DB.GetServer(InstanceID=amp_server.InstanceID).Discord_Console_Channel = channel.id
            else:
                self.DB.GetServer(InstanceID=amp_server.InstanceID).Discord_Console_Channel = channel

            amp_server._setDBattr()  # This will update the AMPConsole Attribute
            await context.send(f'Set **{amp_server.InstanceName}** Console channel to {channel.mention if channel is not None else "None"}', ephemeral=True, delete_after=self._client.Message_Timeout)

    @amp_server_console_settings.command(name='filter')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    @app_commands.choices(flag=[Choice(name='True', value=1), Choice(name='False', value=0)])
    @app_commands.choices(filter_type=[Choice(name='Blacklist', value=0), Choice(name='Whitelist', value=1)])
    async def amp_server_console_filter(self, context: commands.Context, server, flag: Choice[int], filter_type: Choice[int]):
        """Sets the Console Filter type to either Blacklist or Whitelist"""
        self.logger.command(f'{context.author.name} used Database Server Console Filtered True...')

        amp_server = await self.uBot._serverCheck(context, server, False)
        if amp_server:
            db_server = self.DB.GetServer(InstanceID=amp_server.InstanceID)
            db_server.Console_Filtered = flag.value
            db_server.Console_Filtered_Type = filter_type.value
            amp_server._setDBattr()  # This will update the AMPConsole Attributes
            return await context.send(f'Set **{amp_server.InstanceName}** Console Filtering to `{flag.name}` using `{filter_type.name}` filtering.', ephemeral=True, delete_after=self._client.Message_Timeout)

# This section is AMP Server Chat Specific Settings -------------------------------------------------------------------------------------------------------------------------------------------------
    @server.group(name='chat')
    @utils.role_check()
    async def amp_server_chat_settings(self, context: commands.Context):
        if context.invoked_subcommand is None:
            await context.send('Invalid command passed...', ephemeral=True, delete_after=self._client.Message_Timeout)

    @amp_server_chat_settings.command(name='channel')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_chat_channel(self, context: commands.Context, server, channel: discord.abc.GuildChannel):
        """Sets the Chat Channel for the provided Server"""
        self.logger.command(f'{context.author.name} used Database Server Chat Channel')

        amp_server = await self.uBot._serverCheck(context, server, False)
        if amp_server:
            if isinstance(channel, discord.abc.GuildChannel):
                self.DB.GetServer(amp_server.InstanceID).Discord_Chat_Channel = channel.id
            else:
                self.DB.GetServer(amp_server.InstanceID).Discord_Chat_Channel = channel

            amp_server._setDBattr()  # This will update the AMPInstance Attributes
            await context.send(f'Set **{amp_server.InstanceName}** Chat channel to {channel.mention if channel is not None else "None"}', ephemeral=True, delete_after=self._client.Message_Timeout)

# This section is AMP Server Event Specific Settings -------------------------------------------------------------------------------------------------------------------------------------------------
    @server.group(name='event')
    @utils.role_check()
    async def amp_server_event_settings(self, context: commands.Context):
        if context.invoked_subcommand is None:
            await context.send('Invalid command passed...', ephemeral=True, delete_after=self._client.Message_Timeout)

    @amp_server_event_settings.command(name='channel')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def amp_server_event_channel_set(self, context: commands.Context, server, channel: discord.abc.GuildChannel):
        """Sets the Event Channel for the provided Server"""
        self.logger.command(f'{context.author.name} used Database Server Event Channel')

        amp_server = await self.uBot._serverCheck(context, server, False)
        if amp_server:
            if isinstance(channel, discord.abc.GuildChannel):
                self.DB.GetServer(amp_server.InstanceID).Discord_Event_Channel = channel.id
            else:
                self.DB.GetServer(amp_server.InstanceID).Discord_Event_Channel = channel

            amp_server._setDBattr()  # This will update the AMPInstance Attributes
            await context.send(f'Set **{amp_server.InstanceName}** Event channel to {channel.mention if channel is not None else "None"}', ephemeral=True, delete_after=self._client.Message_Timeout)

# This section is AMP Server Regex Specific Settings ------------------------------------------------------------------------------------------------------------------------------
    @server.group(name='regex')
    @utils.role_check()
    async def server_regex_settings(self, context: commands.Context):
        if context.invoked_subcommand is None:
            await context.send('Invalid command passed...', ephemeral=True, delete_after=self._client.Message_Timeout)

    @server_regex_settings.command(name='add')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    @app_commands.autocomplete(name=autocomplete_regex)
    async def server_regex_add(self, context: commands.Context, server, name: str):
        """Adds a Regex Pattern to the Server Regex List."""
        self.logger.command(f'{context.author.name} used Server Regex Pattern Add')

        amp_server = self.uBot.serverparse(server, context, context.guild.id)
        db_server = self.DB.GetServer(InstanceID=server)
        if db_server != None:
            if db_server.AddServerRegexPattern(Name=name):
                regex = self.DB.GetRegexPattern(Name=name)
                if regex:
                    if regex['Type'] == 0:
                        pattern_type = 'Console'
                    if regex['Type'] == 1:
                        pattern_type = 'Events'

                    await context.send(f'We added the Regex Pattern `{name}` to the `{amp_server.InstanceName}`. \n __**Name**__: {regex["Name"]} \n __**Type**__: {pattern_type} \n __**Pattern**__: {regex["Pattern"]}', ephemeral=True, delete_after=self._client.Message_Timeout)
            else:
                await context.send(f'Uhh, I ran into an issue adding the pattern `{name}` to `{amp_server.InstanceName}`. It looks like the Server already has this pattern.', ephemeral=True, delete_after=self._client.Message_Timeout)

    @server_regex_settings.command(name='delete')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    @app_commands.autocomplete(name=autocomplete_server_regex)
    async def server_regex_delete(self, context: commands.Context, server: str, name: str):
        """Deletes a Regex Pattern from the Server Regex List"""
        self.logger.command(f'{context.author.name} used Server Regex Pattern Delete.')

        amp_server = self.uBot.serverparse(server, context, context.guild.id)
        db_server = self.DB.GetServer(InstanceID=server)
        if db_server != None:
            if name != 'None':
                if db_server.DelServerRegexPattern(Name=name):
                    regex = self.DB.GetRegexPattern(Name=name)
                    if regex['Type'] == 0:
                        pattern_type = 'Console'
                    if regex['Type'] == 1:
                        pattern_type = 'Events'
                    await context.send(f'We Removed the Regex Pattern `{name}` from the `{amp_server.InstanceName}`. \n __**Name**__: {regex["Name"]} \n __**Type**__: {pattern_type} \n __**Pattern**__: {regex["Pattern"]}', ephemeral=True, delete_after=self._client.Message_Timeout)
            else:
                await context.send(f'Uhh, I ran into an issue removing the pattern `{name}` to `{amp_server.InstanceName}`. It looks like the Server already has this pattern.', ephemeral=True, delete_after=self._client.Message_Timeout)

    @server_regex_settings.command(name='list')
    @utils.role_check()
    @app_commands.autocomplete(server=utils.autocomplete_servers)
    async def server_regex_list(self, context: commands.Context, server: str):
        """Displays an Embed list of all the Server Regex patterns."""
        self.logger.command(f'{context.author.name} used Server Regex List')

        db_server = self.DB.GetServer(InstanceID=server)
        if db_server != None:
            regex_patterns = db_server.GetServerRegexPatterns()
        if not regex_patterns:
            return await context.send(content='Hmph.. trying to get a list of Regex Patterns, but you have none yet.. ', ephemeral=True, delete_after=self._client.Message_Timeout)

        embed_field = 0
        embed_list = []
        embed = discord.Embed(title='**Regex Patterns**')
        for pattern in regex_patterns:
            embed_field += 1
            if regex_patterns[pattern]['Type'] == 0:
                pattern_type = 'Console'
            if regex_patterns[pattern]['Type'] == 1:
                pattern_type = 'Events'

            embed.add_field(name=f"__**Name**:__ {regex_patterns[pattern]['Name']}\n__**Type**__: {pattern_type}", value=regex_patterns[pattern]['Pattern'], inline=False)

            if embed_field >= 25:
                embed_list.append(embed)
                embed = discord.Embed(title='**Regex Patterns**')
                embed_field = 1
                continue

            if embed_field >= len(regex_patterns):
                embed_list.append(embed)
                break

        await context.send(embeds=embed_list, ephemeral=True, delete_after=self._client.Message_Timeout)


async def setup(client):
    await client.add_cog(AMP_Server(client))
