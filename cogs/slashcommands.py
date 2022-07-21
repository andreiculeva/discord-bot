
import datetime
import re
import sqlite3
import typing
from PIL import Image, ImageFont, ImageDraw
import aiohttp
import asqlite
from discord.ext import commands
from discord import Embed, Forbidden, HTTPException, NotFound, app_commands
import discord
from discord.ext.commands.converter import UserConverter, RoleConverter, GuildConverter
import googletrans
import pytube
from io import BytesIO

import botconfig


testguild_id = 831556458398089217
mushroom_id = 749670809110315019
allowed_guilds = (testguild_id, mushroom_id)


class birthday(app_commands.Group):
    def __init__(self, bot: botconfig.AndreiBot):
        super().__init__()
        self.bot = bot

    async def update_users(self):
        self.bot.birthdayusers = []
        async with self.bot.db.cursor() as cur:
            await cur.execute("SELECT user FROM birthdays")
            userids = await cur.fetchall()
        userids = [user[0] for user in userids]
        for user_id in userids:
            user = self.bot.get_user(user_id)
            if user is None:
                user = await self.bot.fetch_user(user_id)
            if user is None:
                continue
            self.bot.birthdayusers.append(user)

    async def user_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        toreturn = []
        complete = []

        try:
            userid = str(int(current))
        except ValueError:
            userid = None

        for member in interaction.guild.members:
            if member.nick is None:
                continue
            s = [u.id for u in toreturn]
            if member.id in s:
                continue
            if current in member.nick.lower():
                toreturn.append(member)
                complete.append(app_commands.Choice(
                    value=str(member.id), name=f"{str(member)} - {member.nick}"))

        for user in self.bot.users:
            s = [u.id for u in toreturn]
            if user.id in s:
                continue
            if current in str(user).lower():
                complete.append(app_commands.Choice(
                    value=str(user.id), name=str(user)))
                toreturn.append(user)

        if userid:
            for user_id in [str(user.id) for user in self.bot.users]:
                if userid in user_id:
                    us = self.bot.get_user(int(user_id))
                    complete.append(app_commands.Choice(
                        value=str(us.id), name=str(us)))
                    toreturn.append(us)

        if len(complete) > 25:
            complete = complete[:25]
        return complete

    @app_commands.command(name="set", description="Adds or updates a birthday")
    @app_commands.describe(user="The user to set the birthday for, current user if not specified",
                           day="The day, must be a number between 1 and 31",
                           month="The month, must be a number between 1 and 12",
                           year="The year")
    @app_commands.autocomplete(user=user_autocomplete)
    async def _add(self, interaction: discord.Interaction,
                   user: typing.Optional[str],
                   day: app_commands.Range[int, 1, 31],
                   month: app_commands.Range[int, 1, 12],
                   year: int):
        if not user:
            user = str(interaction.user.id)
        else:
            m = self.bot.get_guild(mushroom_id).get_member(interaction.user.id)
            if m is None:
                return await interaction.response.send_message("You're not an allowed user to use this command on others", ephemeral=True)
            allowed = discord.utils.get(m.roles, id=777982059565154315)
            if not allowed:
                return await interaction.response.send_message("You're not an allowed user to use this command on others", ephemeral=True)
        try:
            user: discord.User = await UserConverter().convert((await self.bot.get_context(interaction)), user)
        except commands.UserNotFound:
            return await interaction.response.send_message(f"I couldn't find this user {user}", ephemeral=True)

        async with self.bot.db.cursor() as cur:
            await cur.execute(
                "INSERT OR REPLACE INTO birthdays (user, day, month, year) VALUES (?, ?, ?, ?)", (user.id, day, month, year))
            await self.bot.db.commit()
        dt = datetime.date(year, month, day)
        await interaction.response.send_message(embed=discord.Embed(color=discord.Color.orange(),
                                                                    description=f"Done, {user}'s birthday is: `{dt.strftime('%d %B %Y')}`"))
        await self.update_users()

    async def bdayautocomplete(self, interaction: discord.Interaction, current: str):
        complete = []
        done = []
        try:
            userid = str(int(current))
        except ValueError:
            userid = None

        for user in self.bot.birthdayusers:
            if user.id in done:
                continue
            if current in str(user).lower():
                complete.append(app_commands.Choice(
                    value=str(user.id), name=str(user)))
                done.append(user.id)
        if userid:
            for user_id in [str(user.id) for user in self.bot.birthdayusers]:
                if userid in user_id:
                    if int(userid) in done:
                        continue
                    us = self.bot.get_user(int(user_id))
                    complete.append(app_commands.Choice(
                        value=str(us.id), name=str(us)))
                    done.append(us.id)
        if len(complete) > 25:
            complete = complete[:25]
        return complete

    @app_commands.command(name="remove", description="Removes a birthday")
    @app_commands.autocomplete(user=bdayautocomplete)
    @app_commands.describe(user="This is autocompleted with users that have a birthday set")
    async def _remove(self, interaction: discord.Interaction, user: str = None):
        if user is None:
            user = str(interaction.user.id)
        try:
            user: discord.User = await UserConverter().convert((await self.bot.get_context(interaction)), user)
        except commands.UserNotFound:
            return await interaction.response.send_message(f"I couldn't find this user {user}", ephemeral=True)
        async with self.bot.db.cursor() as cur:
            await cur.execute(f"DELETE FROM birthdays WHERE user = {user.id}")
            await self.bot.db.commit()
        await interaction.response.send_message("\U0001f44d")
        await self.update_users()

    @app_commands.command(name="show", description="See a birthday")
    @app_commands.autocomplete(user=bdayautocomplete)
    @app_commands.describe(user="This is autocompleted with users that have a birthday set")
    async def _show(self, interaction: discord.Interaction, user: str = None):
        if user is None:
            user = str(interaction.user.id)
        try:
            user: discord.User = await UserConverter().convert((await self.bot.get_context(interaction)), user)
        except commands.UserNotFound:
            return await interaction.response.send_message(f"I couldn't find this user {user}", ephemeral=True)
        async with self.bot.db.cursor() as cur:
            await cur.execute(f"SELECT * FROM birthdays WHERE user = {user.id}")
            result = await cur.fetchone()
        if result is None:
            return await interaction.response.send_message(f"{user} doesn't have a birthday set", ephemeral=True)
        dt = datetime.date(result[3], result[2], result[1])
        await interaction.response.send_message(embed=discord.Embed(color=discord.Color.orange(),
                                                                    description=f"{user}'s birthday is: `{dt.strftime('%d %B %Y')}`"))

    @app_commands.command(name="list", description="Lists all birthdays")
    @app_commands.describe(dates="Wether to only show the dates")
    async def _list(self, interaction: discord.Interaction, dates: bool = False):
        if dates:
            async with self.bot.db.cursor() as cur:
                await cur.execute("SELECT * FROM birthdays")
                birthdates = await cur.fetchall()
            _dates = {k[0]: datetime.date(
                day=k[1], month=k[2], year=k[3]) for k in birthdates}
            _dates = {k: v for k, v in sorted(
                _dates.items(), key=lambda item: item[1])}
            currentyear = list({k: v.replace(year=datetime.date.today().year)
                                for k, v in _dates.items()
                                if v.replace(year=datetime.date.today().year) > datetime.date.today()}.keys())
            entries = []
            for k, v in _dates.items():
                us = self.bot.get_user(k)
                if us is None:
                    try:
                        us = await self.bot.fetch_user(k)
                        toapp = str(us)
                    except discord.NotFound:
                        await interaction.channel.send(f"I couldn't find user with ID {k}")
                else:
                    toapp = us.mention
                entries.append({"user": toapp,
                                "date": v.strftime('%d %B %Y'),
                                "age": f" is {(datetime.date.today().year - v.year)- (1 if k in currentyear else 0)}"},)

            pages = botconfig.SimpleBirthdayPages(
                entries=entries, ctx=(await self.bot.get_context(interaction)), title="All birthdays")
            await pages.start()
        else:
            async with self.bot.db.cursor() as cur:
                await cur.execute("SELECT * FROM birthdays")
                comingup = await cur.fetchall()
            _dates = {k[0]: datetime.date(
                day=k[1], month=k[2], year=k[3]) for k in comingup}
            _dates = {k: v for k, v in sorted(
                _dates.items(), key=lambda item: item[1])}
            currentyear = {k: v.replace(year=datetime.date.today().year)
                           for k, v in _dates.items()
                           if v.replace(year=datetime.date.today().year) > datetime.date.today()}
            currentyear = {k: v for k, v in sorted(
                currentyear.items(), key=lambda item: item[1])}
            nextyear = {k: v.replace(year=datetime.date.today().year+1)
                        for k, v in _dates.items()
                        if v.replace(year=datetime.date.today().year+1) < datetime.date.today().replace(year=datetime.date.today().year+1)}
            nextyear = {k: v for k, v in sorted(
                nextyear.items(), key=lambda item: item[1])}
            newdates = currentyear | nextyear
            entries = []
            for k, v in newdates.items():
                us = interaction.guild.get_member(k)
                if us is None:
                    us = self.bot.get_user(k)
                    if us is None:
                        try:
                            us = await self.bot.fetch_user(k)
                            toapp = str(us)
                        except discord.NotFound:
                            await interaction.channel.send(f"I couldn't find user with ID {k}")
                            continue
                    else:
                        toapp = str(us)
                else:
                    toapp = us.mention
                entries.append({"user": toapp, "date": v.strftime(
                    '%d %B %Y'), "age": f" turns {v.year-_dates[k].year}"})
            pages = botconfig.SimpleBirthdayPages(
                entries=entries, ctx=(await self.bot.get_context(interaction)))
            await pages.start()


class purge(app_commands.Group):
    def __init__(self, bot: botconfig.AndreiBot):
        super().__init__()
        self.bot = bot

    @app_commands.command(name="message", description="Purges messages")
    @app_commands.describe(limit="The number of messages to search through, this is not the number of mssages that will be deleted, though it can be",
                           content="Specific word/sentence to look for, deletes any message if not given")
    async def purge_message(self, interaction: discord.Interaction, limit: int, content: str = None):
        if not (interaction.channel.permissions_for(interaction.user).manage_messages or (interaction.user.id in self.bot.owner_ids)):
            return await interaction.response.send_message("You are missing the manage messages perms", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        if content:
            def mcheck(m: discord.Message):
                if m.content:
                    return content.lower() in m.content.lower()
            deleted = await interaction.channel.purge(limit=limit, check=mcheck)
            repl = f"with {content} in them"
        else:
            deleted = await interaction.channel.purge(limit=limit)
            repl = ""
        await interaction.followup.send(f"Deleted {len(deleted)} messages {repl}")

    @app_commands.command(name="files", description="Deletes messages with files or embeds")
    @app_commands.describe(limit="The number of messages to search through, this is not the number of mssages that will be deleted, though it can be")
    async def purge_files(self, interaction: discord.Interaction, limit: int):
        if not (interaction.channel.permissions_for(interaction.user).manage_messages or (interaction.user.id in self.bot.owner_ids)):
            return await interaction.response.send_message("You are missing the manage messages perms", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=limit, check=lambda m: m.attachments or m.embeds)
        await interaction.followup.send(f"Deleted {len(deleted)} messages with files/embeds")

    @app_commands.command(name="user", description="Deletes messages from a specific user")
    @app_commands.describe(limit="The number of messages to search through, this is not the number of mssages that will be deleted, though it can be",
                           user="The user to delete messages from")
    async def purge_user(self, interaction: discord.Interaction, user: discord.User, limit: int):
        if not (interaction.channel.permissions_for(interaction.user).manage_messages or (interaction.user.id in self.bot.owner_ids) or (interaction.user == user)):
            return await interaction.response.send_message("You are missing the manage messages perms", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=limit, check=lambda m: m.author == user)
        await interaction.followup.send(f"Deleted {len(deleted)} messages from {user}")

    @app_commands.command(name="bot", description="Deletes messages from bots")
    @app_commands.describe(limit="The number of messages to search through, this is not the number of mssages that will be deleted, though it can be")
    async def purge_bot(self, interaction: discord.Interaction, limit: int):
        if not (interaction.channel.permissions_for(interaction.user).manage_messages or (interaction.user.id in self.bot.owner_ids)):
            return await interaction.response.send_message("You are missing the manage messages perms", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=limit, check=lambda m: m.author.bot)
        await interaction.followup.send(f"Deleted {len(deleted)} messages from bots")


class snipe(app_commands.Group):
    """Snipe related commands"""

    def __init__(self, bot: botconfig.AndreiBot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="deleted", description="Shows deleted messages")
    @app_commands.describe(offset="How far to search",
                           hidden="Whether the message response should be ephemeral",
                           user="The user to search for, if not given then the bot searches for deleted messages from all users")
    async def _snipe(self, interaction: discord.Interaction, offset: int = None, user: discord.User = None, hidden: bool = False):
        if offset is not None:
            offset = offset-1
        else:
            offset = 0
        async with self.bot.db.cursor() as cur:
            if user is not None:
                request = f"SELECT * FROM messages WHERE channel = {interaction.channel.id} AND author = {user.id} ORDER BY timestamp DESC LIMIT 1 OFFSET {offset}"
                await cur.execute(request)
                res = await cur.fetchone()
            else:
                request = f"SELECT * FROM messages WHERE channel = {interaction.channel.id} ORDER BY timestamp DESC LIMIT 1 OFFSET {offset}"
                await cur.execute(request)
                res = await cur.fetchone()
        if not res:
            return await interaction.response.send_message("I couldn't find anything", ephemeral=hidden)
        data: tuple = res
        em = discord.Embed(color=discord.Color.orange())
        em.description = data[-1]  # message content
        em.timestamp = datetime.datetime.fromtimestamp(int(data[-2]))
        m = self.bot.get_user(int(data[3]))
        if m:
            em.set_author(name=str(m), icon_url=m.display_avatar)
        await interaction.response.send_message(embed=em, view=botconfig.InteractionDeletedView(bot=self.bot, author=m, interaction=interaction, hidden=hidden, message_id=data[2]), ephemeral=hidden)

    @app_commands.command(name="edits", description="Shows edited messages")
    @app_commands.describe(messages="How far to search", hidden="Whether the message response should be ephemeral",
                           message_id="This can be any message ID, the messages parameter will be bypassed")
    async def editsnipe(self, interaction: discord.Interaction, messages: int = None, hidden: bool = False, message_id: str = ""):

        async with self.bot.db.cursor() as cur:
            if message_id:
                request = f"SELECT message FROM edits WHERE message = {message_id}"
                await cur.execute(request)
                mes = await cur.fetchone()
                if not mes:
                    return await interaction.response.send_message(f"I couldn't find anything with ID: {message_id}", ephemeral=hidden)
                query = f"SELECT content, timestamp, author FROM edits WHERE message = {mes[0]} ORDER BY timestamp ASC"
            elif messages is None:  # search one only
                firstquer = f"SELECT message FROM edits WHERE channel = {interaction.channel.id} ORDER BY timestamp DESC LIMIT 1"
                await cur.execute(firstquer)
                mes = await cur.fetchone()
                if not mes:
                    return await interaction.response.send_message("I couldn't find anything", ephemeral=True)
                message_id = mes[0]
                query = f"SELECT content, timestamp, author FROM edits WHERE message = {message_id} ORDER BY timestamp ASC"
            elif messages is not None:  # offset
                try:
                    messages = int(messages)-1
                except ValueError:
                    return await interaction.response.send_message(f"`{messages}` is an invalid number", ephemeral=True)
                firstquer = f"SELECT DISTINCT message FROM edits WHERE channel = {interaction.channel.id} ORDER BY timestamp DESC LIMIT 1 OFFSET {messages}"
                await cur.execute(firstquer)
                mes = await cur.fetchone()
                if not mes:
                    return await interaction.response.send_message("I couldn't find anything")
                message_id = mes[0]
                query = f"SELECT content, timestamp, author FROM edits WHERE message = {message_id} ORDER BY timestamp ASC"

            await cur.execute(query)
            allmessages = await cur.fetchall()
            edits = allmessages[1:]
            # edits = [] #list of all edits [(content, timestamp, author), ...]
            original: tuple = allmessages[0]
            author = self.bot.get_user(int(original[-1]))
            if author is None:
                try:
                    author = await self.bot.fetch_user(int(original[-1]))
                except (discord.NotFound, discord.HTTPException):
                    author = None
            pages = botconfig.InteractionSnipeSimplePages(
                entries=edits, interaction=interaction, original=original, author=author, hidden=hidden)
            await pages.start()


async def backup(bot: botconfig.AndreiBot, link: str):
    params = {
        "url": link
    }
    headers = {
        'x-rapidapi-host': "tiktok-download-without-watermark.p.rapidapi.com",
        'x-rapidapi-key': "eefbcdcf5emsh8efbbe0eb6c7709p1aae98jsn008c15449684"
    }

    # Get your Free TikTok API from https://rapidapi.com/TerminalWarlord/api/tiktok-info/
    # Using the default one can stop working any moment

    api = 'https://tiktok-download-without-watermark.p.rapidapi.com/analysis'
    async with bot.session.get(api, params=params, headers=headers) as r:
        s = await r.json()
        return s


async def download_tiktok(bot: botconfig.AndreiBot, url) -> typing.Union[botconfig.tiktokvideo, str]:
    params = {
        "url": url
    }
    headers = {
        'x-rapidapi-host': "tiktok-download-without-watermark.p.rapidapi.com",
        'x-rapidapi-key': "1b2bcc06fdmsh2a8c86db3e5db2bp1905efjsnbbb4d597fdff"
    }

    # Get your Free TikTok API from https://rapidapi.com/TerminalWarlord/api/tiktok-info/
    # Using the default one can stop working any moment

    api = 'https://tiktok-download-without-watermark.p.rapidapi.com/analysis'
    async with bot.session.get(api, params=params, headers=headers) as r:
        data = await r.json()
        mes = data.get("message")
        if mes:
            if mes.startswith("You have exceeded"):
                data = await backup(url)
                mes = data.get("message")
                if mes:
                    if mes.startswith("You have exceeded"):
                        return "We hit ratelimits for today <:2_angrycat:930476797051687032>"
        data = data.get("data")
        if data is None:
            return "That's probably an invalid tiktok video URL"
        tiktok_url = data.get("play")
        if tiktok_url is None:
            tiktok_url = data.get("vmplay")
        if tiktok_url is None:
            return "Failed to download video"

    async with bot.session.get(tiktok_url) as r:
        bytes = await r.read()
    return botconfig.tiktokvideo(BytesIO(bytes), url, tiktok_url)


async def youtube_method(interaction: discord.Interaction, url, hidden: bool):
    await interaction.response.defer(ephemeral=hidden)
    try:
        streams = pytube.YouTube(url).streams
    except Exception as e:
        return await interaction.followup.send(e, ephemeral=True)
    mock_ctx = interaction.client.get_context(interaction)
    view = botconfig.YouTubeDownloadSelect(ctx=mock_ctx, streams=streams)
    return await interaction.followup.send(view=view)


async def tiktok_method(interaction: discord.Interaction, link: str, hidden: bool, url_only: bool = False):
    await interaction.response.defer(ephemeral=hidden)
    file = await download_tiktok(interaction.client, link)
    if isinstance(file, str):
        return await interaction.followup.send(file)
    if url_only:
        return await interaction.followup.send(embed=discord.Embed(color=discord.Color.orange(), description=f"[url]({file.download_url})"))
    try:
        if interaction.guild:
            if file.video.__sizeof__() > interaction.guild.filesize_limit:
                return await interaction.followup.send(embed=discord.Embed(color=discord.Color.orange(),
                                                                           description=f"The file is too big to be uploaded, [here]({file.download_url})'s the URL to download it yourself"))
        else:
            if file.video.__sizeof__() > 8388608:
                return await interaction.followup.send(embed=discord.Embed(color=discord.Color.orange(),
                                                                           description=f"The file is too big to be uploaded, [here]({file.download_url})'s the URL to download it yourself"))
        await interaction.followup.send(file=discord.File(file.video, filename="video.mp4"))
    except discord.HTTPException as e:
        await interaction.followup.send(embed=discord.Embed(color=discord.Color.orange(),
                                                            description=f"The file is too big to be uploaded, [here]({file.download_url})'s the URL to download it yourself"))


async def check_dms(user: discord.User):
    try:
        await user.send()
    except discord.HTTPException as e:
        if e.code == 50006:  # cannot send an empty message
            return True
        elif e.code == 50007:  # cannot send messages to this user
            return False
        else:
            raise


async def on_error(interaction: discord.Interaction, error):
    error = getattr(error, "original", error)
    if interaction.response.is_done():
        await interaction.followup.send(str(error))
    else:
        await interaction.response.send_message(str(error))


def can_add_role(author: discord.Member, target: discord.Member, role: discord.Role):
    if not role.is_assignable():
        return False
    if role.id in [r.id for r in target.roles]:
        return False
    if author.top_role.position <= role.position:
        return False
    return True


class role(app_commands.Group):
    """Role related commands"""

    def __init__(self, bot: botconfig.AndreiBot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="add", description="Add role(s) to a member")
    @app_commands.describe(member="The target member, uses the current user if not given", 
                        role="The role to add",
                           role2="Another optional role to add",
                           role3="Another optional role to add",
                           role4="Another optional role to add",
                           role5="Another optional role to add",)
    async def add_role(self, interaction: discord.Interaction,
                       member: discord.Member,
                       role: discord.Role,
                       role2: discord.Role = None, role3: discord.Role = None,
                       role4: discord.Role = None, role5: discord.Role = None):
        if not interaction.user.guild_permissions.manage_roles:
            return await interaction.response.send_message("You are missing the manage roles permission", ephemeral=True)
        to_add = []
        if role.id not in [r.id for r in member.roles]:
            to_add.append(role)
        if (role2) and (role2 not in to_add) and (role2.id not in [r.id for r in member.roles]):
            to_add.append(role2)
        if (role3) and (role3 not in to_add) and (role3.id not in [r.id for r in member.roles]):
            to_add.append(role3)
        if (role4) and (role4 not in to_add) and (role4.id not in [r.id for r in member.roles]):
            to_add.append(role4)
        if (role5) and (role5 not in to_add) and (role5.id not in [r.id for r in member.roles]):
            to_add.append(role5)

        if len(to_add) == 0:
            return await interaction.response.send_message("No changes need to be made", ephemeral=True)

        failed = []
        newroles = []
        for role in to_add:
            if not can_add_role(interaction.user, member, role):
                failed.append(role)
            else:
                newroles.append(role)
        if len(newroles) == 0:
            return await interaction.response.send_message("I can't add any of those roles due to permissions", ephemeral=True)
        await interaction.response.defer()
        try:
            await member.add_roles(*newroles)
        except discord.Forbidden:
            return await interaction.followup.send("I don't have permission to add roles to that member", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.followup.send(str(e), ephemeral=True)
        s = f"Added the following roles to {member.mention}: {' ,'.join([r.mention for r in newroles])}"
        if failed:
            s += f'\nand failed to add: {" ,".join([r.mention for r in failed])}'
        await interaction.followup.send(s, allowed_mentions=discord.AllowedMentions(roles=False))

    async def remove_autocomplete(self, interaction: discord.Interaction, current: str):
        if interaction.namespace.member is None:
            return []
        member = interaction.guild.get_member(interaction.namespace.member.id)
        if member is None:
            return []
        roles = member.roles
        toreturn = []
        for role in roles:
            if not role.is_assignable():
                continue
            if role.name.lower().startswith(current.lower()):
                toreturn.append(app_commands.Choice(
                    name=role.name, value=str(role.id)))
        if len(toreturn) > 25:
            toreturn = toreturn[:25]
        return toreturn
    
        

    @app_commands.command(name="remove", description="Removes a role from a member")
    @app_commands.describe(member="The member to remove the role from", role="The role to remove, only one at a time")
    @app_commands.autocomplete(role=remove_autocomplete)
    async def _remove(self, interaction: discord.Interaction, member: discord.Member, role: str):
        try:
            role = await RoleConverter().convert((await self.bot.get_context(interaction)), role)
        except commands.RoleNotFound:
            return await interaction.response.send_message(f"I couldn't find this role: {role}", ephemeral=True)
        if not interaction.user.guild_permissions.manage_roles:
            return await interaction.response.send_message("You are missing the manage roles permission to do that", ephemeral=True)
        try:
            await member.remove_roles(role)
        except Forbidden:
            return await interaction.response.send_message(f"I don't have permissions to do that", ephemeral=True)
        except HTTPException as e:
            return await interaction.response.send_message(str(e), ephemeral=True)
        await interaction.response.send_message(f"Removed {role.mention} from {member.mention}", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


class edit(app_commands.Group):
    """Edits the bot profile"""

    def __init__(self, bot: botconfig.AndreiBot):
        self.bot = bot
        super().__init__(guild_ids=[testguild_id, mushroom_id])

    @app_commands.command()
    @app_commands.describe(name="The bot's new username")
    async def username(self, interaction: discord.Interaction, name: str):
        """Changes the bot's username"""
        try:
            await self.bot.user.edit(username=name)
        except Exception as e:
            mes = str(e)
        else:
            mes = f"Changed my username to {name}"
        finally:
            await interaction.response.send_message(mes)

    @app_commands.command()
    @app_commands.describe(image="Gifs are supported, but will be converted to static pngs")
    async def avatar(self, interaction: discord.Interaction, image: discord.Attachment = None):
        """Edits the bot's profile picture, if image is a missing argument the bot's avatar will be removed"""
        await interaction.response.defer()
        if image:
            img = await image.read()
        else:
            img = None
        try:
            await self.bot.user.edit(avatar=img)
            mes = "Edited my avatar"
        except Exception as e:
            mes = str(e)
        await interaction.followup.send(mes)


testguild = discord.Object(id=testguild_id)
mushroom = discord.Object(id=mushroom_id)


class slashcommands(commands.Cog):

    def __init__(self, bot: botconfig.AndreiBot) -> None:
        super().__init__()
        self.bot = bot
        self.trans = googletrans.Translator()

    async def cog_load(self) -> None:
        tree = self.bot.tree
        tree.add_command(edit(self.bot))
        tree.add_command(role(self.bot))
        tree.add_command(snipe(self.bot))
        tree.add_command(purge(self.bot))
        tree.add_command(birthday(self.bot))
        tree.on_error = on_error

        @tree.context_menu(name="view avatar")
        async def avatar_contextmenu(interaction:discord.Interaction, member:discord.Member):
            embed = discord.Embed(color=discord.Color.orange())
            if member.avatar:
                av = member.avatar
                avatar_type = ""
            elif member.guild_avatar:
                av = member.guild_avatar
                avatar_type = "server"
            else:
                av = member.default_avatar
                avatar_type = "default"
            embed.set_image(url=av.with_size(4096).url)
            embed.set_author(name=f"{member}'s {avatar_type} avatar")
            embed.set_footer(text=f"ID: {member.id}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

            

        @tree.context_menu(name="steal emojis")
        async def stealemojis(interaction: discord.Interaction, message: discord.Message):
            if not message.content:
                return await interaction.response.send_message("This message has no content", ephemeral=True)
            emojis = []

            def get_emoji(arg):
                match = re.match(
                    r'<(a?):([a-zA-Z0-9\_]{1,32}):([0-9]{15,20})>$', arg)
                if match:
                    return discord.PartialEmoji.with_state(state=interaction.client._connection,
                                                           name=match.group(2),
                                                           animated=bool(
                                                               match.group(1)),
                                                           id=int(match.group(3)))
                return None
            pattern = r'<?a?:[a-zA-Z0-9\_]{1,32}:[0-9]{15,20}>?'
            s = re.findall(pattern, message.content)
            s = list(set(s))
            for match in s:
                emoji = get_emoji(match)
                if emoji:
                    if emoji in emojis:
                        continue
                    emojis.append(emoji)

            if len(emojis) == 0:  # no emojis found
                return await interaction.response.send_message("I couldn't find any emoji", ephemeral=True)

            elif len(emojis) == 1:  # one emoji, no confirmation needed
                emoj: discord.PartialEmoji = emojis[0]
                try:
                    new_emoji = await interaction.guild.create_custom_emoji(name=emoj.name, image=(await emoj.read()))
                    em = discord.Embed(color=discord.Color.green(),
                                       description=f"done {new_emoji}\nname: {new_emoji.name}\nID: {new_emoji.id}\nanimated: {new_emoji.animated}\n`{new_emoji}`")
                    em.set_thumbnail(url=new_emoji.url)
                    await interaction.response.send_message(embed=em)
                except (Forbidden, HTTPException) as e:
                    await interaction.response.send_message(str(e))
                return

            else:  # ask for confirmation
                if len(emojis) > 30:
                    emojis = emojis[:30]
                    s = "(limited to 30 to avoid rate limits)"
                else:
                    s = ""
                view = botconfig.ConfirmationView(org_inter=interaction, timeout=None)
                await interaction.response.send_message(f"This will add {len(emojis)} emojis to this server, are you sure? {s}", view=view)
                await view.wait()
                if not view.value:  # doesn't want to add them
                    return await interaction.edit_original_message(content="\U0001f44d")
                done = 0
                for emoji in emojis:
                    try:
                        await interaction.guild.create_custom_emoji(name=emoji.name, image=(await emoji.read()))
                        done += 1
                    except (Forbidden, HTTPException) as e:
                        pass
                await interaction.followup.send(f"Added {done} emojis")

        @tree.context_menu(name="translate")
        async def translate(interaction: discord.Interaction, message: discord.Message):
            if message.content == "" or message.content is None:
                return await interaction.response.send_message("This message has no content", ephemeral=True)
            try:
                ret = await self.bot.loop.run_in_executor(None, self.trans.translate, message.content, str(interaction.locale)[:2])
            except Exception as e:
                return await interaction.response.send_message(f'An error occurred: {e.__class__.__name__}: {e}', ephemeral=True)
            embed = discord.Embed(colour=discord.Color.orange())
            src = googletrans.LANGUAGES.get(ret.src, '(auto-detected)').title()
            embed.set_author(name=str(message.author),
                             icon_url=message.author.display_avatar.url)
            embed.description = f"[original]({message.jump_url})"
            embed.add_field(
                name=f"Translated from {src} to {ret.dest}", value=ret.text)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @tree.context_menu(name="view banner")
        async def viewbanner(interaction: discord.Interaction, member: discord.Member):
            user = await self.bot.fetch_user(member.id)
            if not user.banner:
                return await interaction.response.send_message("This user has no banner, bots don't have access to server specific banners btw", ephemeral=True)
            em = discord.Embed(color=discord.Color.orange())
            em.set_author(name=f"{user}'s banner",
                          icon_url=user.display_avatar.url)
            em.set_image(url=user.banner.url)
            await interaction.response.send_message(embed=em, ephemeral=True)

        return await super().cog_load()

    async def cog_unload(self) -> None:
        tree = self.bot.tree
        tree.remove_command(name="edit")
        tree.remove_command(name="role")
        tree.remove_command(name="translate")
        tree.remove_command(name="steal emojis")
        tree.remove_command(name="view banner")
        tree.remove_command(name="view avatar")
        tree.remove_command(name="snipe")
        tree.remove_command(name="purge")
        tree.remove_command(name="birthday")
        return await super().cog_unload()

    async def channel_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        toreturn = []
        complete = []
        channels = [
            channel for guild in self.bot.guilds for channel in guild.text_channels]

        try:
            channelid = str(int(current))
        except ValueError:
            channelid = None

        for channel in interaction.guild.text_channels:
            s = [c.id for c in toreturn]
            if channel.id in s:
                continue
            if current in channel.name.lower():
                toreturn.append(channel)
                complete.append(app_commands.Choice(
                    value=str(channel.id), name=channel.name))

        for channel in channels:
            s = [u.id for u in toreturn]
            if channel.id in s:
                continue
            if current in channel.name.lower():
                complete.append(app_commands.Choice(
                    value=str(channel.id), name=f"{channel.name} (SERVER: {channel.guild.name})"))
                toreturn.append(channel)

        if channelid:
            for channel_id in [str(channel.id) for channel in channels]:
                if channelid in channel_id:
                    chan = self.bot.get_channel(int(channel_id))
                    if channel in interaction.guild.text_channels:
                        complete.append(app_commands.Choice(
                            value=str(chan.id), name=chan.name))
                    else:
                        complete.append(app_commands.Choice(
                            value=str(chan.id), name=f"{chan.name} (SERVER: {chan.guild.name})"))
                    toreturn.append(chan)

        if len(complete) > 25:
            complete = complete[:25]
        return complete

    @app_commands.command(description="Sends a message through the bot")
    @app_commands.describe(channel="The target channel (use the autocomplete or it breaks (i'm lazy))",
                           content="The message's content",
                           file="An optional attachment",
                           reference="The message ID the bot is replying to, MUST be in the chosen channel",)
    @app_commands.autocomplete(channel=channel_autocomplete)
    @app_commands.guilds(testguild, mushroom)
    async def message(self,
                      interaction: discord.Interaction,
                      channel: str,
                      content: str = None,
                      file: discord.Attachment = None,
                      reference: str = None):
        if (content is None) and (file is None):
            return await interaction.response.send_message("I can't send an empty message", ephemeral=True)

        destination = self.bot.get_channel(int(channel))

        if destination is None:
            return await interaction.response.send_message(f"I couldn't find channel with ID: {channel}", ephemeral=True)

        if reference:
            try:
                refid = int(reference)
            except ValueError:
                return await interaction.response.send_message(f"{refid} is an invalid number", ephemeral=True)
            try:
                ref = await destination.fetch_message(refid)
            except NotFound:
                return await interaction.response.send_message(f"{refid} is not a message in this channel or an invalid ID", ephemeral=True)
        else:
            ref = None

        if file:
            await interaction.response.defer(thinking=True, ephemeral=True)
            file = await file.to_file()

        try:
            m = await destination.send(content=content, file=file, reference=ref)
        except (TypeError, ValueError, Forbidden, HTTPException) as e:
            if interaction.response.is_done():
                return await interaction.followup.send(str(e))
            return await interaction.response.send_message(str(e), ephemeral=True)
        resp = f"I sent a message in {destination.mention} - {m.jump_url}"
        if interaction.response.is_done():
            await interaction.followup.send(resp)
        else:
            await interaction.response.send_message(resp, ephemeral=True)

    async def user_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        toreturn = []
        complete = []

        try:
            userid = str(int(current))
        except ValueError:
            userid = None

        for member in interaction.guild.members:
            if member.nick is None:
                continue
            s = [u.id for u in toreturn]
            if member.id in s:
                continue
            if current in member.nick.lower():
                toreturn.append(member)
                complete.append(app_commands.Choice(
                    value=str(member.id), name=f"{str(member)} - {member.nick}"))

        for user in self.bot.users:
            s = [u.id for u in toreturn]
            if user.id in s:
                continue
            if current in str(user).lower():
                complete.append(app_commands.Choice(
                    value=str(user.id), name=str(user)))
                toreturn.append(user)

        if userid:
            for user_id in [str(user.id) for user in self.bot.users]:
                if userid in user_id:
                    us = self.bot.get_user(int(user_id))
                    complete.append(app_commands.Choice(
                        value=str(us.id), name=str(us)))
                    toreturn.append(us)

        if len(complete) > 25:
            complete = complete[:25]
        return complete

    @app_commands.command(description="Sends a DM through the bot")
    @app_commands.describe(content="The message content", file="An optional attachment")
    @app_commands.autocomplete(user=user_autocomplete)
    @app_commands.guilds(testguild, mushroom)
    async def dm(self, interaction: discord.Interaction, user: str, content: str = None, file: discord.Attachment = None):
        try:
            u = await UserConverter().convert(ctx=(await self.bot.get_context(interaction)), argument=user)
        except commands.UserNotFound:
            return await interaction.response.send_message("I couldn't find that user", ephemeral=True)
        if (content is None) and (file is None):
            can_dm = await check_dms(u)
            if can_dm:
                res = "I can DM"
            else:
                res = "I can't DM"
            return await interaction.response.send_message(f'{res} {u} (ID: {u.id})', ephemeral=True)
        await interaction.response.defer()
        if file:
            file = await file.to_file()
        try:
            await u.send(content, file=file)
        except discord.HTTPException as e:
            if e.code == 50006:
                return await interaction.followup.send("Cannot send an empty message", ephemeral=True)
            elif e.code == 50007:
                return await interaction.followup.send("Cannot DM this user", ephemeral=True)
            else:
                return await interaction.followup.send(str(e))
        except (TypeError, ValueError, Forbidden) as e:
            return await interaction.followup.send(str(e), ephemeral=True)
        await interaction.followup.send(f"Sent a DM to {u} (ID: {u.id})")

    @app_commands.command(description="View any discord user's banner")
    @app_commands.describe(user="This can be any discord user", hidden="Whether the message response should be ephemeral")
    @app_commands.autocomplete(user=user_autocomplete)
    async def banner(self, interaction: discord.Interaction, user: str = None, hidden: bool = False):
        if user is None:
            _user = interaction.user
        else:
            try:
                _user = await UserConverter().convert(ctx=await self.bot.get_context(interaction), argument=user)
            except commands.UserNotFound:
                return await interaction.response.send_message(f"I couldn't find user {user}", ephemeral=True)

        us = await self.bot.fetch_user(_user.id)
        if us.banner is None:
            return await interaction.response.send_message(f"{us} has no banner", ephemeral=True)
        em = discord.Embed(color=discord.Color.orange(),
                           title=f"{us}'s banner")
        em.set_image(url=us.banner.url)
        await interaction.response.send_message(embed=em, ephemeral=hidden)

    async def date_autocomplete(self, interaction: discord.Interaction, current: str):
        choices: list[app_commands.Choice] = []
        choices.append(app_commands.Choice(name="now", value=datetime.datetime.strftime(
            datetime.datetime.now(), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="30m ago", value=datetime.datetime.strftime(
            datetime.datetime.now() - datetime.timedelta(minutes=30), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="1h ago", value=datetime.datetime.strftime(
            datetime.datetime.now() - datetime.timedelta(hours=1), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="10h ago", value=datetime.datetime.strftime(
            datetime.datetime.now() - datetime.timedelta(hours=10), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="1d ago", value=datetime.datetime.strftime(
            datetime.datetime.now() - datetime.timedelta(days=1), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="2d ago", value=datetime.datetime.strftime(
            datetime.datetime.now() - datetime.timedelta(days=2), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="1 week ago", value=datetime.datetime.strftime(
            datetime.datetime.now() - datetime.timedelta(weeks=1), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="4 weeks ago", value=datetime.datetime.strftime(
            datetime.datetime.now() - datetime.timedelta(weeks=4), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="in 10 min", value=datetime.datetime.strftime(
            datetime.datetime.now() + datetime.timedelta(minutes=10), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="in 30 min", value=datetime.datetime.strftime(
            datetime.datetime.now() + datetime.timedelta(minutes=30), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="in 1h", value=datetime.datetime.strftime(
            datetime.datetime.now() + datetime.timedelta(hours=1), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="in 10h", value=datetime.datetime.strftime(
            datetime.datetime.now() + datetime.timedelta(hours=10), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="in 1d", value=datetime.datetime.strftime(
            datetime.datetime.now() + datetime.timedelta(days=1), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="in 2d", value=datetime.datetime.strftime(
            datetime.datetime.now() + datetime.timedelta(days=2), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="in 1 week", value=datetime.datetime.strftime(
            datetime.datetime.now() + datetime.timedelta(weeks=1), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="in 2 weeks", value=datetime.datetime.strftime(
            datetime.datetime.now() + datetime.timedelta(weeks=2), "%d/%m/%Y %H:%M:%S")))
        choices.append(app_commands.Choice(name="in 4 weeks", value=datetime.datetime.strftime(
            datetime.datetime.now() + datetime.timedelta(weeks=4), "%d/%m/%Y %H:%M:%S")))
        toreturn = []
        for choice in choices:
            if current.lower() in choice.name.lower():
                toreturn.append(choice)
        return toreturn

    @app_commands.command(description="Converts the date to a discord timestamp", name="timestamp")
    @app_commands.describe(date="format 'DD/MM/YEAR hh:mm:ss', \
        hh:mm:ss follow CET", timestamponly="Wether to return only the timestamp", hidden="Whether the message response should be ephemeral")
    @app_commands.autocomplete(date=date_autocomplete)
    async def _timestamp(self, interaction: discord.Interaction, date: str, timestamponly: bool = False, hidden: bool = False):
        if not ":" in date:
            date += " 00:00:00"
        try:
            dtime = datetime.datetime.strptime(date, "%d/%m/%Y %H:%M:%S")
            d = int(dtime.timestamp())
        except ValueError as e:
            return await interaction.response.send_message(f"'{date}' does not match format DD/MM/YEAR hh:mm:ss (example: 21/03/2005 15:31:50)", ephemeral=True)

        if timestamponly:
            return await interaction.response.send_message(d, ephemeral=hidden)

        s = ""
        s += f"`{discord.utils.format_dt(dtime, 't')}` - {discord.utils.format_dt(dtime, 't')} short time\n"
        s += f"`{discord.utils.format_dt(dtime, 'T')}` - {discord.utils.format_dt(dtime, 'T')} long time\n"
        s += f"`{discord.utils.format_dt(dtime, 'd')}` - {discord.utils.format_dt(dtime, 'd')} short date\n"
        s += f"`{discord.utils.format_dt(dtime, 'D')}` - {discord.utils.format_dt(dtime, 'D')} long date\n"
        s += f"`{discord.utils.format_dt(dtime, 'f')}` - {discord.utils.format_dt(dtime, 'f')} short date and time\n"
        s += f"`{discord.utils.format_dt(dtime, 'F')}` - {discord.utils.format_dt(dtime, 'F')} long date and time\n"
        s += f"`{discord.utils.format_dt(dtime, 'R')}` - {discord.utils.format_dt(dtime, 'R')} relative time"

        await interaction.response.send_message(s, ephemeral=hidden)

    @app_commands.command(description="View any discord user's avatar, and their history")
    @app_commands.describe(user="This can be any discord user", type="The avatar type", hidden="Whether the message response should be ephemeral")
    @app_commands.autocomplete(user=user_autocomplete)
    async def avatar(self, interaction: discord.Interaction, user: str = None,
                     type: typing.Literal["server",
                                          "profile", "default"] = "profile",
                     hidden: bool = False):
        if user is None:
            _user = interaction.user
        else:
            try:
                _user = await UserConverter().convert(ctx=await self.bot.get_context(interaction), argument=user)
            except commands.UserNotFound:
                return await interaction.response.send_message(f"I couldn't find user {user}", ephemeral=True)
        em = discord.Embed(color=discord.Color.orange())
        if type == "server":
            member = interaction.guild.get_member(_user.id)
            if member is None:
                return await interaction.response.send_message(f"{_user} isn't in this server", ephemeral=True)
            async with self.bot.db.cursor() as cur:
                await cur.execute("SELECT url, date, avatar FROM avatars WHERE user = ? AND server = ?", (
                    member.id, member.guild.id))
                data = await cur.fetchall()
            if not data:
                if member.guild_avatar is None:
                    return await interaction.response.send_message("This member has no server avatar")
                em = discord.Embed(color=discord.Color.orange())
                em.set_author(name=str(member),
                              icon_url=member.guild_avatar.url)
                em.set_image(url=member.guild_avatar.url)
                return await interaction.response.send_message(embed=em, allowed_mentions=discord.AllowedMentions.none())
            found = False
            av = member.guild_avatar
            if av:
                avname = f"{av.key}.{'gif' if av.is_animated() else 'png'}"

                for url, _, name in data:
                    if name == avname:
                        found = True
                        break
                if not found:
                    data.append(
                        (av.url, int(datetime.datetime.now().timestamp()), avname))
            avatars = sorted(data, key=lambda x: x[1], reverse=True)
            av_urls = [(k[0], k[1]) for k in avatars]
            if member.guild_avatar is None:
                pages = botconfig.InteractionAvatarPages(entries=av_urls, interaction=interaction,
                                               author=member, type="server", no_pfp=True, hidden=hidden)
            else:
                pages = botconfig.InteractionAvatarPages(entries=av_urls, interaction=interaction,
                                               author=member, type="server", hidden=hidden)
            await pages.start()
            pass  # copy server...
        elif type == "profile":
            async with self.bot.db.cursor() as cur:
                await cur.execute(
                    "SELECT url, date, avatar FROM avatars WHERE user = ? AND server = 0", (_user.id,))
                data = await cur.fetchall()
            if not data:
                em = discord.Embed(color=discord.Color.orange())
                em.set_author(name=str(_user),
                              icon_url=_user.display_avatar.url)
                em.set_image(url=_user.display_avatar.url)
                return await interaction.response.send_message(embed=em, allowed_mentions=discord.AllowedMentions.none(), ephemeral=hidden)
            found = False
            av = _user.avatar or _user.display_avatar
            avname = f"{av.key}.{'gif' if av.is_animated() else 'png'}"

            for url, _, name in data:
                if name == avname:
                    found = True
                    break
            if not found:
                data.append(
                    (av.url, int(datetime.datetime.now().timestamp()), avname))
            avatars = sorted(data, key=lambda x: x[1], reverse=True)
            av_urls = [(k[0], k[1]) for k in avatars]
            pages = botconfig.InteractionAvatarPages(entries=av_urls, interaction=interaction,
                                           author=_user, type="", hidden=hidden)
            return await pages.start()
        else:
            em.title = f"{_user}'s default avatar"
            av = _user.default_avatar
            em.set_image(url=av.url)
            return await interaction.response.send_message(embed=em, ephemeral=hidden)

    @app_commands.command(description="Returns all users with that role")
    @app_commands.describe(role="The role to search for", hidden="Whether the message response should be ephemeral")
    async def inrole(self, interaction: discord.Interaction, role: discord.Role, hidden: bool = False):
        if len(role.members) == 0:
            return await interaction.response.send_message("No users in this role", ephemeral=True)

        def sortfunc(m: discord.Member):
            return m.name.lower()
        sorted_list = role.members
        sorted_list.sort(key=sortfunc)
        new_list = []
        for member in sorted_list:
            name = member.name
            new_name = ""
            for character in name:
                if character in ("*", "_", "|", "~"):
                    new_name += chr(92) + character
                else:
                    new_name += character
            new_list.append(f"{new_name}#{member.discriminator}")
        mock_ctx = await self.bot.get_context(interaction)
        pages = botconfig.RolePages(entries=new_list, ctx=mock_ctx, role=role)
        await pages.start()

    @app_commands.command(name="download", description="Helper command to download media from internet, only tiktok and youtube currently work")
    @app_commands.describe(url="The url to download from, must be either tiktok or youtube", linkonly="Wether to only send the download URL", hidden="Whether the message response should be ephemeral")
    async def download(self, interaction: discord.Interaction, url: str, hidden: bool = False, linkonly: bool = False):
        tiktokmatch = re.match(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", url)
        youtubematch = re.match(
            r"^(https?\:\/\/)?((www\.)?youtube\.com|youtu\.be)\/.+$", url)
        if youtubematch:
            return await youtube_method(interaction, url, hidden)
        elif tiktokmatch:
            return await tiktok_method(interaction, url, hidden, linkonly)
        else:
            # return await ctx.send(embed=discord.Embed(color=red, description="`link` is not a valid youtube or tiktok URL"))
            return await interaction.response.send_message("`url` is not a valid youtube or tiktok URL", ephemeral=True)

    @app_commands.command(name="setinvitelog", description="Sets the channel for the invite logger, no more configuration required")
    @app_commands.describe(channel="The channel to log invites to, if not given then the bot stops logging invites for this srever",
                           hidden="Whether the message response should be ephemeral")
    async def invite_log(self, interaction: discord.Interaction, channel: discord.TextChannel = None, hidden: bool = False):
        if channel is None:
            async with self.bot.db.cursor() as cur:
                await cur.execute(
                    f"DELETE FROM invites WHERE server = {interaction.guild.id}")
                await self.bot.db.commit()
            await interaction.response.send_message("done \U0001f44d", ephemeral=hidden)
        else:
            async with self.bot.db.cursor() as cur:
                await cur.execute(
                    f"DELETE FROM invites WHERE server = {interaction.guild.id}")
                await self.bot.db.commit()
                await cur.execute(
                    f"INSERT INTO invites (server, channel) VALUES ({interaction.guild.id}, {channel.id})")
                await self.bot.db.commit()
            await interaction.response.send_message("done \U0001f44d", ephemeral=hidden)
        await self.bot.cogs["events"].update_invites.__call__()

    @app_commands.command(name="lurk", description="Lurks through a server's emojis, if available")
    @app_commands.describe(server="The server to lurk in, this MUST be the server ID, if not given then the bot uses the current server",
                           hidden="Whether the message response should be ephemeral")
    async def lurk(self, interaction: discord.Interaction, server: str = None, hidden: bool = False):
        if server is None:
            server = interaction.guild.id
        else:
            try:
                server = int(server)
            except ValueError:
                return await interaction.response.send_message("That's not a valid server ID.", ephemeral=True)
        route = discord.http.Route(
            "GET", "/guilds/{guild_id}/preview", guild_id=server)
        try:
            response = await self.bot.http.request(route)
        except discord.NotFound:
            return await interaction.response.send_message("Discord couldn't find that server or the ID is invalid", ephemeral=True)
        emojis: list[discord.PartialEmoji] = []
        for emoji_data in response.get("emojis"):
            if emoji_data["roles"]:
                continue
            emoji = discord.PartialEmoji.with_state(
                name=emoji_data["name"], id=emoji_data["id"], animated=emoji_data["animated"], state=self.bot._connection)
            emojis.append(emoji)
        icon = f'https://cdn.discordapp.com/icons/{response["id"]}/{response["icon"]}.{"gif" if response["icon"].startswith("a_") else "png"}'
        name = response["name"]
        source = botconfig.EmojiPageSource(emojis, per_page=1, name=name, icon=icon)
        pages = botconfig.EmojiPages(source, client=self.bot, author=interaction.user,
                           channel=interaction.channel, search=True, interaction=interaction, hidden=hidden)
        await pages.start()

    @app_commands.command(name="members", description="Shows members in the server, ordered by their joined date")
    async def _members(self, interaction: discord.Interaction, hidden: bool = False):
        entries = [f"<t:{int(k.joined_at.timestamp())}:d> {k.mention}" for k in sorted(
            [m for m in interaction.guild.members if (not m.bot)], key=lambda x: x.joined_at)]
        pages = botconfig.InteractionSimplePages(entries=entries, interaction=interaction, hidden=hidden,
                                       title="members")
        await pages.start()

    @app_commands.command(name="memberinfo", description="Shows useful info about a member")
    @app_commands.describe(member="The member to show info of, if not given then the bot uses the current member", hidden="Whether the message response should be ephemeral")
    async def _userinfo(self, interaction: discord.Interaction, member: discord.Member = None, hidden: bool = False):
        if member is None:
            member = interaction.user
        to_clean = ("add_reactions", "attach_files", "change_nickname", "connect", "create_instant_invite", "create_private_threads",
                    "create_public_threads", "deafen_members", "embed_links", "external_emojis", "external_stickers", "manage_threads",
                    "manage_webhooks", "use_voice_activation", "view_audit_log", "priority_speaker",
                    "read_message_history", "request_to_speak", "send_messages_in_threads", "send_tts_messages", "speak", "stream",
                    "view_guild_insights", "read_messages", "use_slash_commands", "send_messages")
        clean_perms: list[str] = []
        for name, value in member.guild_permissions:
            if (not (name in to_clean)) and value:
                clean_perms.append(name)
        if member.id == interaction.guild.owner.id:
            member_perms = ["Server Owner"]
        elif member.guild_permissions.administrator:
            member_perms = ["Administrator"]
        else:
            member_perms = [perm.title().replace("_", " ")
                            for perm in clean_perms]
            member_perms.sort()
            member_perms = [k.replace("Guild", "Server") for k in member_perms]
            member_perms = tuple(f"`{k}`" for k in member_perms)
        embed = discord.Embed(
            color=discord.Color.orange(),
            description=f"""account created: <t:{int(member.created_at.timestamp())}>\nmember joined: <t:{int(member.joined_at.timestamp())}>\non mobile: {member.is_on_mobile()}""")
        if member.premium_since:
            embed.description += f"\nboosting since <t:{int(member.premium_since.timestamp())}>"
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(f"SELECT day, month, year FROM birthdays WHERE user = {member.id}")
            birthdate = await cursor.fetchone()
        if birthdate:
            bd = datetime.date(
                birthdate["year"], birthdate["month"], birthdate["day"]).strftime('%d %B %Y')
            embed.description += f"\nbirthday: {bd}"
        if member_perms:
            embed.add_field(
                name=f"key permissions (permission value = {str(member.guild_permissions).split('=')[1][:-1]})", value=", ".join(member_perms))
        member_roles = tuple(
            f"{role.mention}" for role in member.roles if not role.is_default())
        if not member_roles:
            embed.add_field(name="server roles",
                            value="no roles", inline=False)
        else:
            str_member_roles = ", ".join(member_roles)
            embed.add_field(name="server roles", value=str_member_roles if (
                len(str_member_roles) < 1024) else "Too many roles to display", inline=False)

        embed.set_author(name=str(member),
                         icon_url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        try:
            user = await self.bot.fetch_user(member.id)
            if user.banner:
                embed.set_thumbnail(url=user.banner.url)
            else:
                pass  # set field with banner urls and stuff
        except (NotFound, HTTPException):
            pass
        await interaction.response.send_message(embed=embed, ephemeral=hidden)

    async def guild_autocomplete(self, interaction: discord.Interaction, current: str):
        toreturn = []
        if "local" in current.lower():
            toreturn.append(app_commands.Choice(
                name=interaction.guild.name, value=str(interaction.guild.id)))
        for guild in interaction.client.guilds:
            if current.lower() in guild.name.lower():
                toreturn.append(app_commands.Choice(
                    name=guild.name, value=str(guild.id)))
        if len(toreturn) > 25:
            toreturn = toreturn[:25]
        return toreturn

    @app_commands.command(name="sync", description="Syncs the slash commands")
    @app_commands.autocomplete(guild=guild_autocomplete)
    @app_commands.guilds(testguild, mushroom)
    @app_commands.describe(guild="Target server, syncs globally if not given")
    async def _sync(self, interaction: discord.Interaction, guild: typing.Optional[str]):
        if guild:
            try:
                guild = await GuildConverter().convert((await self.bot.get_context(interaction)), guild)
            except (commands.BadArgument, HTTPException) as e:
                return await interaction.response.send_message(str(e), ephemeral=True)
            newcommands = await self.bot.tree.sync(guild=guild)
            tp = f"in {guild.name}"
        else:
            newcommands = await self.bot.tree.sync()
            tp = "globally"
        await interaction.response.send_message(f"Synced {len(newcommands)} commands {tp}")

    @app_commands.command(name="meme", description="Generates a meme given the image")
    @app_commands.describe(image="The image to work on", toptext="Text to show at the top", bottomtext="Text to show at the bottom")
    async def _meme(self, interaction: discord.Interaction, image: discord.Attachment, toptext: str = None, bottomtext: str = None):
        if not image.filename.endswith(("png", "jpg", "jpeg", "gif")):
            return await interaction.response.send_message("Unsupported file type", ephemeral=True)
        await interaction.response.defer()
        headers = {"API-KEY": "ea103fd19b9e7b5f75c09727d8c707"}
        url = "https://memebuild.com/api/1.0/generateMeme"
        data = {
            "topText": toptext if toptext else "",
            "bottomText": bottomtext if bottomtext else "",
            "imgUrl": image.url
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, data=data) as response:
                if response.status != 200:
                    return await interaction.followup.send(str(await response.text()))
                dt = await response.json()

        await interaction.followup.send(dt["url"])


    @app_commands.command(name="muted", description="Shows timed out members in this server")
    @app_commands.describe(hidden="Wether the message response should be ephemeral")
    async def _showmuted(self, interaction: discord.Interaction, hidden: bool = False):
        return await interaction.response.send_message("I'll finish this command later.", ephemeral=True)
        muted = []
        for member in interaction.guild.members:
            if member.is_timed_out():
                muted.append(member)
        if not muted:
            return await interaction.response.send_message("No members are muted", ephemeral=hidden)

    @app_commands.command(description="Unbans a user from this server")
    @app_commands.describe(user="The user to unban, this autocompletes with users that are already banned", 
    reason="The optional reason")
    async def unban(self, interaction:discord.Interaction, user:str, reason:str=None):
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message(f"You are missing the `ban members` permissions",ephemeral=True)
        if reason is None:
            reason = f"Done by {interaction.user} (ID: {interaction.user.id})"
        else:
            reason += f"Done by {interaction.user} (ID: {interaction.user.id})"
        try:
            banentry=await interaction.guild.fetch_ban(discord.Object(id=int(user)))
        except NotFound:
            return await interaction.response.send_message(f"{user} is not banned")
        try:
            await interaction.guild.unban(banentry.user, reason=reason)
        except NotFound:
            return await interaction.response.send_message(f"{user} is not banned")
        await interaction.response.send_message(f"unbanned {banentry.user} (ID: {banentry.user.id})")

    @unban.autocomplete("user")
    async def unban_user_entry(self, interaction:discord.Interaction, current:str):
        if not interaction.guild.me.guild_permissions.ban_members:
            return []
        bans = [ban async for ban in interaction.guild.bans()]
        
        current = current.lower()
        toreturn = []
        complete = []

        try:
            userid = str(int(current))
        except ValueError:
            userid = None

        for entry in bans:
            s = [u.id for u in toreturn]
            if entry.user.id in s:
                continue
            if current in str(entry.user).lower():
                complete.append(app_commands.Choice(
                    value=str(entry.user.id), name=str(entry.user)))
                toreturn.append(entry.user)

        if userid:
            for user_id in [str(user.id) for user in [entry.user for entry in bans]]:
                if userid in user_id:
                    us = discord.utils.find(lambda entry: entry.user.id == int(user_id), bans)
                    if us:
                        complete.append(app_commands.Choice(
                            value=str(us.user.id), name=str(us.user)))
                        toreturn.append(us.user)

        if len(complete) > 25:
            complete = complete[:25]
        return complete


async def setup(bot: botconfig.AndreiBot):
    await bot.add_cog(slashcommands(bot))
    await birthday(bot).update_users()
