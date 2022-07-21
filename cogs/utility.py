import botconfig
from io import BytesIO
from typing import List, Dict, Any
import typing
import discord
from discord.errors import Forbidden, HTTPException, NotFound
from discord.ext import commands, menus
from discord.ext.commands.converter import PartialEmojiConverter, UserConverter
from discord.ext.commands.errors import BadArgument, CommandError, CommandNotFound, MemberNotFound, MissingPermissions, MissingRequiredArgument, PartialEmojiConversionFailure, RoleNotFound, UserNotFound
import datetime
import time
import os
import re
import io
import asyncio
import unicodedata
import googletrans
import zlib
import pytube
import importlib
from discord.http import Route

rx = re.compile(r'([0-9]{15,20})$')


class StickerModal(discord.ui.Modal):

    name = discord.ui.TextInput(label="name", style=discord.TextStyle.short)
    description = discord.ui.TextInput(
        label="description", style=discord.TextStyle.long)

    def __init__(self, view: discord.ui.View) -> None:
        super().__init__(title="Make a sticker")
        self.view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.view.stop()
        await interaction.response.defer(ephemeral=True)


class StickerView(discord.ui.View):
    def __init__(self, author: discord.Member, *, timeout: typing.Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.author = author
        self.value: typing.Literal[1, 2, 3] = None
        self.modal = StickerModal(view=self)

    @discord.ui.button(label="existing sticker")
    async def existing_sticker(self, interaction: discord.Interaction, _):
        self.value = 1
        await interaction.response.send_modal(self.modal)

    @discord.ui.button(label="from file")
    async def from_file(self, interaction: discord.Interaction, _):
        self.value = 2
        await interaction.response.send_modal(self.modal)

    @discord.ui.button(label="image url", disabled=True)
    async def from_url(self, interaction: discord.Interaction, _):
        self.value = 3
        self.interaction = interaction

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.author:
            return True
        await interaction.response.send_message("You can't use this button", ephemeral=True)
        return False


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


async def tiktok_method(ctx: commands.Context, link: str):
    await ctx.typing()
    file = await download_tiktok(ctx.bot, link)
    if isinstance(file, str):
        return await ctx.send(file)
    try:
        if ctx.guild:
            if file.video.__sizeof__() > ctx.guild.filesize_limit:
                return await ctx.send(embed=discord.Embed(color=discord.Color.orange(),
                                                          description=f"The file is too big to be uploaded, [here]({file.download_url})'s the URL to download it yourself"))
        else:
            if file.video.__sizeof__() > 8388608:
                return await ctx.send(embed=discord.Embed(color=discord.Color.orange(),
                                                          description=f"The file is too big to be uploaded, [here]({file.download_url})'s the URL to download it yourself"))
        await ctx.send(file=discord.File(file.video, filename="video.mp4"))
    except discord.HTTPException as e:
        await ctx.send(embed=discord.Embed(color=discord.Color.orange(),
                                           description=f"The file is too big to be uploaded, [here]({file.download_url})'s the URL to download it yourself"))


async def youtube_method(ctx: commands.Context, url):
    await ctx.typing()
    try:
        streams = pytube.YouTube(url).streams
    except Exception as e:
        return await ctx.send(e)
    view = botconfig.YouTubeDownloadSelect(ctx=ctx, streams=streams)
    return await ctx.send(view=view)


def format_description(s: pytube.Stream):
    parts = [f'{s.mime_type}']
    if s.includes_video_track:
        parts.extend(
            [f'{"with" if s.includes_audio_track else "without"} audio'])
        parts.extend([f'{s.resolution}', f'@{s.fps}fps'])

    else:
        parts.extend([f'{s.abr}', f'audio codec="{s.audio_codec}"'])
    return f"{' '.join(parts)}"


class BadDateFormat(commands.BadArgument):
    """Invalid date format, only dd/mm/year or dd/mm formats are accepted."""


async def convert_role(ctx: commands.Context, argument: str) -> discord.Role:
    match = rx.match(argument) or re.match(r'<@&([0-9]{15,20})>$', argument)
    if match:
        result = ctx.guild.get_role(int(match.group(1)))
    else:
        result = discord.utils.get(ctx.guild._roles.values(), name=argument)
    if result is None:
        for role in ctx.guild.roles:
            if role.name.lower() == argument:
                result = role
                break
    if result is None:
        for role in ctx.guild.roles:
            if role.name.lower().startswith(argument):
                result = role
                break
    if result is None:
        raise RoleNotFound(argument)
    return result


def finder(text, collection, *, key=None, lazy=True):
    suggestions = []
    text = str(text)
    pat = '.*?'.join(map(re.escape, text))
    regex = re.compile(pat, flags=re.IGNORECASE)
    for item in collection:
        to_search = key(item) if key else item
        r = regex.search(to_search)
        if r:
            suggestions.append((len(r.group()), r.start(), item))

    def sort_key(tup):
        if key:
            return tup[0], tup[1], key(tup[2])
        return tup

    if lazy:
        return (z for _, _, z in sorted(suggestions, key=sort_key))
    else:
        return [z for _, _, z in sorted(suggestions, key=sort_key)]


class SphinxObjectFileReader:
    # Inspired by Sphinx's InventoryFileReader
    BUFSIZE = 16 * 1024

    def __init__(self, buffer):
        self.stream = io.BytesIO(buffer)

    def readline(self):
        return self.stream.readline().decode('utf-8')

    def skipline(self):
        self.stream.readline()

    def read_compressed_chunks(self):
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self):
        buf = b''
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b'\n')
            while pos != -1:
                yield buf[:pos].decode('utf-8')
                buf = buf[pos + 1:]
                pos = buf.find(b'\n')


red = discord.Color.red()
orange = discord.Color.orange()


async def convert(ctx: commands.Context, argument: str):
    match = rx.match(argument) or re.match(r'<@!?([0-9]{15,20})>$', argument)
    result = None
    users: list[discord.User] = ctx.bot.users

    if match is not None:
        user_id = int(match.group(1))
        result = ctx.bot.get_user(user_id)
        if result is None:
            try:
                result = await ctx.bot.fetch_user(user_id)
            except discord.HTTPException:
                raise commands.UserNotFound(argument) from None
        return result

    arg = argument.lower()

    # Remove the '@' character if this is the first character from the argument
    if arg[0] == '@':
        # Remove first character
        arg = arg[1:]

    # check for discriminator if it exists,
    if len(arg) > 5 and arg[-5] == '#':
        discrim = arg[-4:]
        name = arg[:-5]
        def predicate(u): return u.name.lower(
        ) == name and u.discriminator == discrim
        result = discord.utils.find(predicate, users)
        if result is not None:
            return result

    def predicate(u): return u.name.lower() == arg
    result = discord.utils.find(predicate, users)

    if result is None:
        raise commands.UserNotFound(argument)

    return result


class utility(commands.Cog):
    """chat commands with prefix"""

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='\N{BAR CHART}')

    def __init__(self, bot):
        self.bot: botconfig.AndreiBot = bot
        self.trans = googletrans.Translator()

    @staticmethod
    @commands.Cog.listener()
    async def on_command_error(ctx: commands.Context, error):
        if hasattr(ctx.command, "on_error"):
            return
        if ctx.cog:
            if ctx.cog._get_overridden_method(ctx.cog.cog_command_error) is not None:
                return
        error = getattr(error, "original", error)
        if isinstance(error, CommandNotFound):
            return
        emoji = "<:meh:854231053124370482>"
        if isinstance(error, UserNotFound):
            em = discord.Embed(color=discord.Color.red(
            ), description=f"I couldn't find the user `{error.argument}` {emoji}")
        elif isinstance(error, MemberNotFound):
            em = discord.Embed(color=discord.Color.red(
            ), description=f"I couldn't find `{error.argument}` in the server {emoji}")
        elif isinstance(error, MissingRequiredArgument):
            em = discord.Embed(color=discord.Color.red(
            ), description=f"`{error.param.name}` is a required argument that is missing {emoji}")
        elif isinstance(error, Forbidden):
            em = discord.Embed(color=discord.Color.red(
            ), description=f"I am missing permissions (just give me admin and check the role hierarchy)")
        elif isinstance(error, MissingPermissions):
            if ctx.author.id in ctx.bot.owner_ids:
                await ctx.reinvoke(restart=True) # bypass owners
                return 
            em = discord.Embed(color=discord.Color.red(
            ), description=f"You are missing the `{error.missing_permissions[0]}` perms {emoji}")
        elif isinstance(error, RoleNotFound):
            em = discord.Embed(color=discord.Color.red(
            ), description=f"I couldn't find the role: `{error.argument}` {emoji}")
        elif isinstance(error, discord.HTTPException):
            em = discord.Embed(color=discord.Color.red(
            ), title="HTTP exception:", description=f"error code {error.code}: {error.text}")
        elif isinstance(error, commands.BadLiteralArgument):
            em = discord.Embed(color=red, title="Bad command usage",
                               description=f"{error.param} is not a valid literal argument ({' ,'.join(error.literals)})")
        elif isinstance(error, commands.EmojiNotFound):
            em = discord.Embed(color=red, title="Couldn't find that emoji",
                               description="Maybe I am not in that server")
        elif isinstance(error, commands.PartialEmojiConversionFailure):
            em = discord.Embed(color=red,
                               description="I couldn't find that emoji")
        elif isinstance(error, ValueError):
            em = discord.Embed(
                color=red, description=f"{error.args[0]} is an invalid number")
        elif isinstance(error, BadDateFormat):
            em = discord.Embed(
                color=red, description="Invalid date format, only dd/mm/year or dd/mm formats are accepted.")
        elif isinstance(error, commands.BadArgument):
            em = discord.Embed(color=red, description=str(error))
        else:
            #raise error
            # return
            em = discord.Embed(color=red, description=f"error: {str(error)}")
        await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())

    # to rewrite tbh

    @commands.command(aliases=["pping", "p"],
                      help="Shows the bot latency from the discord websocket.")
    async def ping(self, ctx: commands.Context):
        async def measure_ping(coro):
            start = time.monotonic()
            await coro
            return time.monotonic() - start

        async with self.bot.db.cursor() as cursor:
            start = time.monotonic()
            await cursor.execute("SELECT * FROM messages LIMIT 1")
            await cursor.fetchone()
            db = time.monotonic() - start
        http_request = await measure_ping(self.bot.http.request(Route("GET", "/users/@me")))
        embed = discord.Embed(color=discord.Color.orange(), title="Ping")
        embed.add_field(name="Discord Websocket",
                        value=f"`{self.bot.latency * 1000:.2f}`ms")
        embed.add_field(name="Database", value=f"`{db * 1000:.2f}`ms"),
        embed.add_field(name="HTTP request",
                        value=f"`{http_request * 1000:.2f}`ms")
        await ctx.send(embed=embed)

    @commands.command()
    async def snipe(self, ctx: commands.Context, offset=None, user: discord.User = None):
        """Used to show deleted messages.
        `offset`: how far to search.
        `user`: will only search for messages from that user.
        Deleted files are stored in RAM for only 1 hour"""
        if offset is not None:
            try:
                offset = int(offset)-1
            except ValueError:
                em = discord.Embed(color=red)
                em.description = "please enter a valid number"
                await ctx.reply(embed=em)
                return
        else:
            offset = 0
        async with self.bot.db.cursor() as cur:
            if user is not None:
                request = f"SELECT * FROM messages WHERE channel = {ctx.channel.id} AND author = {user.id} ORDER BY timestamp DESC LIMIT 1 OFFSET {offset}"
                await cur.execute(request)
                res = await cur.fetchone()
            else:
                request = f"SELECT * FROM messages WHERE channel = {ctx.channel.id} ORDER BY timestamp DESC LIMIT 1 OFFSET {offset}"
                await cur.execute(request)
                res = await cur.fetchone()
        if not res:
            em = discord.Embed(color=red)
            em.description = "I couldn't find anything"
            return await ctx.reply(embed=em)
        data: tuple = res
        em = discord.Embed(color=orange)
        em.description = data[-1]  # message content
        em.timestamp = datetime.datetime.fromtimestamp(int(data[-2]))
        m = self.bot.get_user(int(data[3]))
        if m:
            em.set_author(name=str(m), icon_url=m.display_avatar)
        file = self.bot.deleted_files.get(data[2])
        v = botconfig.DeletedView(
            bot=self.bot, ctx=ctx, message_id=data[2], author=m)
        await ctx.reply(embed=em, view=v)

    @commands.command()
    async def whois(self, ctx: commands.Context, *, user: str = None):
        """Returns info about a discord user.
        `user` can be the message reference's author.
        You will have to give the `user`'s id if the bot doesn't share servers with them"""
        target = user
        if target is None:
            if ctx.message.reference:
                try:
                    _message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                    user_id = _message.author.id
                except (NotFound, Forbidden, HTTPException):
                    user_id = ctx.author.id
            else:
                user_id = ctx.author.id
        else:
            try:
                _temp_user = await UserConverter.convert(UserConverter(), ctx, target)
                user_id = _temp_user.id
            except (BadArgument, CommandError):
                try:
                    user_id = int(target)
                except ValueError:
                    em = discord.Embed(color=red)
                    em.description = "I couldn't find that user"
                    return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
        try:
            user: discord.User = await self.bot.fetch_user(user_id)
        except (NotFound, HTTPException):
            em = discord.Embed(color=red)
            em.description = "I couldn't find that user"
            return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())

        embed = discord.Embed(color=discord.Colour.orange(
        ), description=f"account created: <t:{int(user.created_at.timestamp())}>")
        embed.set_author(
            name=str(user), icon_url=user.display_avatar.url)
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(f"SELECT day, month, year FROM birthdays WHERE user = {user.id}")
            birthdate = await cursor.fetchone()
        if birthdate:
            bd = datetime.date(
                birthdate["year"], birthdate["month"], birthdate["day"]).strftime('%d %B %Y')
            embed.description += f"\nbirthday: {bd}"
        if user.banner:
            embed.set_thumbnail(url=user.banner.url)
            embed.add_field(
                name="urls", value=f"[avatar]({user.display_avatar.url})\n[banner]({user.banner.url})")
        else:
            embed.add_field(
                name="urls", value=f"[avatar]({user.display_avatar.url})")
        embed.set_footer(text=f"ID: {user.id}")
        await ctx.reply(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    # todo: add url fields
    @commands.command(aliases=["memberinfo"])
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None):
        """Returns info about a `member` in the server"""
        if member is None:
            member = ctx.author
        # magic check for message.reference
        to_clean = ("add_reactions", "attach_files", "change_nickname", "connect", "create_instant_invite", "create_private_threads",
                    "create_public_threads", "deafen_members", "embed_links", "external_emojis", "external_stickers", "manage_threads",
                    "manage_webhooks", "use_voice_activation", "view_audit_log", "priority_speaker",
                    "read_message_history", "request_to_speak", "send_messages_in_threads", "send_tts_messages", "speak", "stream",
                    "view_guild_insights", "read_messages", "use_slash_commands", "send_messages")
        clean_perms: List[str] = []
        for name, value in member.guild_permissions:
            if (not (name in to_clean)) and value:
                clean_perms.append(name)
        if member.id == ctx.guild.owner.id:
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
            color=orange,
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
        await ctx.reply(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(aliases=["av", "avatars", "avs"])
    async def avatar(self, ctx: commands.Context, user: str = None):
        """Returns the `user`'s avatar, and their saved avatar history.
        `user` can be the message reference's author.
        `user` can be any discord user."""
        target = user
        if target is None:
            if ctx.message.reference:
                try:
                    _message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                    user_id = _message.author.id
                except (NotFound, Forbidden, HTTPException):
                    em = discord.Embed(color=red)
                    em.description = "I couldn't load that message"
                    return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
            else:
                user_id = ctx.author.id
        else:
            try:
                _temp_user = await UserConverter().convert(ctx, target)
                user_id = _temp_user.id
            except (BadArgument, CommandError):
                try:
                    user_id = int(target)
                except ValueError:
                    em = discord.Embed(color=red)
                    em.description = "I couldn't find that user"
                    return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())

        user = self.bot.get_user(user_id)
        if user is None:
            try:
                user: discord.User = await self.bot.fetch_user(user_id)
            except (NotFound, HTTPException):
                em = discord.Embed(color=orange)
                em.description = "I couldn't find that user"
                return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())

        async with self.bot.db.cursor() as cur:
            await cur.execute("SELECT url, date, avatar FROM avatars WHERE user = ? AND server = 0", (user.id,))
            data = await cur.fetchall()
        if not data:
            em = discord.Embed(color=orange)
            em.set_author(name=str(user), icon_url=user.display_avatar.url)
            em.set_image(url=user.avatar.url)
            return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
        found = False
        av = user.avatar or user.display_avatar
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

        pages = botconfig.AvatarPages(
            entries=av_urls, ctx=ctx, author=user, type="")
        await pages.start()

    @commands.command(aliases=["sav", "savatars", "serveravatar", "serveravatars"])
    async def savatar(self, ctx: commands.Context, member: discord.Member = None):
        """Returns the `member`'s server avatar, if available.
        `member` can be the author of the message reference"""

        if member is None:
            if ctx.message.reference:
                mreference = ctx.message.reference
                if mreference.cached_message is not None:
                    member = mreference.cached_message.author
                else:
                    message = await ctx.channel.fetch_message(mreference.message_id)
                    if message is None:
                        em = discord.Embed(color=red)
                        em.description = "I couldn't load that message"
                        return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
                    member = message.author
                if ctx.guild.get_member(member.id) is None:
                    em = discord.Embed(
                        color=red, description="That user isn't in the server")
                    return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
            else:
                member = ctx.author
        # member is a member object, copy code

        async with self.bot.db.cursor() as cur:
            await cur.execute("SELECT url, date, avatar FROM avatars WHERE user = ? AND server = ?",
                              (member.id, member.guild.id))
            data = await cur.fetchall()
        if not data:
            if member.guild_avatar is None:
                return await ctx.reply("This member has no server avatar")
            em = discord.Embed(color=red)
            em.set_author(name=str(member), icon_url=member.guild_avatar.url)
            return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
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
            pages = botconfig.AvatarPages(entries=av_urls, ctx=ctx,
                                          author=member, type="server", no_pfp=True)
        else:
            pages = botconfig.AvatarPages(entries=av_urls, ctx=ctx,
                                          author=member, type="server")
        await pages.start()

    @commands.command()
    async def banner(self, ctx: commands.Context, user: str = None):
        """Returns the `user`'s banner, if available.
        `user` can be the author of the message reference"""
        target = user
        if target is None:
            if ctx.message.reference:
                try:
                    _message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                    user_id = _message.author.id
                except (NotFound, Forbidden, HTTPException):
                    em = discord.Embed(color=red)
                    em.description = "I couldn't load that message"
                    return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
            else:
                user_id = ctx.author.id
        else:
            try:
                _temp_user = await UserConverter.convert(UserConverter(), ctx, target)
                user_id = _temp_user.id
            except (BadArgument, CommandError):
                try:
                    user_id = int(target)
                except ValueError:
                    em = discord.Embed(color=red)
                    em.description = "I couldn't find that user"
                    return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
        try:
            user: discord.User = await self.bot.fetch_user(user_id)
        except (NotFound, HTTPException):
            em = discord.Embed(color=red)
            em.description = "I couldn't find that user"
            return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())

        if user.banner is None:
            em = discord.Embed(
                color=red, description=f"{str(user)} doesn't have a banner")
            return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())

        embed = discord.Embed(color=orange)
        embed.set_author(name=str(user), icon_url=user.display_avatar.url)

        embed.set_image(url=user.banner.url)
        await ctx.reply(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @commands.group(invoke_without_command=True, aliases=["emote"])
    async def emoji(self, ctx: commands.Context):
        """Sends emoji help command"""
        return await ctx.send_help("emoji")


    @emoji.command(aliases=["show"])
    async def info(self, ctx: commands.Context, emoji: discord.PartialEmoji):
        """Shows info about any discord `emoji`"""
        emoji_str = "<"
        if emoji.animated:
            emoji_str += "a"
        emoji_str += f":{emoji.name}:"
        emoji_str += f"{emoji.id}>"
        em = discord.Embed(
            color=orange, description=f"name: {emoji.name}\nID: {emoji.id}\nanimated: {emoji.animated}\n`{emoji_str}`\n[EMOJI URL]({emoji.url})")
        em.set_thumbnail(url=emoji.url)
        await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none(), view=botconfig.EmojiView(emoji))

    @commands.has_guild_permissions(manage_emojis=True)
    @emoji.command(aliases=["create", "clone", "copy"])
    async def add(self, ctx: commands.Context, emoji, *, name: str = None):
        """Adds `emoji` to the server\n`emoji` can be an image URL, `name` will be required in that case"""
        try:
            _emoji = await PartialEmojiConverter().convert(ctx, emoji)
            emoji_url = _emoji.url
            name = name or _emoji.name
        except PartialEmojiConversionFailure:
            if not re.match("http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", emoji):
                em = discord.Embed(color=discord.Color.red())
                em.description = "That's not a valid emoji or URL"
                return await ctx.reply(embed=em)
            emoji_url = emoji
        if name is None:
            em = discord.Embed(color=discord.Color.red(
            ), description=f"`name` is a required argument that is missing <:meh:854231053124370482>")
            return await ctx.reply(embed=em)
        name = name.replace(" ", "_")
        emoji_url = emoji_url.replace(".webp", ".png")

        async with self.bot.session.get(emoji_url) as r:
            image_bytes = await r.read()
        new_emoji = await ctx.guild.create_custom_emoji(name=name, image=image_bytes)
        emoji_str = str(new_emoji)
        em = discord.Embed(color=discord.Color.green(
        ), description=f"done {emoji_str}\nname: {new_emoji.name}\nID: {new_emoji.id}\nanimated: {new_emoji.animated}\n`{str(new_emoji)}`")
        em.set_thumbnail(url=new_emoji.url)
        await ctx.reply(embed=em)

    @emoji.command(aliases=["remove"])
    async def delete(self, ctx: commands.Context, emoji: discord.Emoji):
        """Deletes the `emoji`, if the bot can see it"""
        _author = emoji.guild.get_member(ctx.author.id)
        if _author is None:
            em = discord.Embed(color=discord.Color.red(),
                               description="You're not in that server")
            return await ctx.reply(embed=em)
        if not _author.guild_permissions.manage_emojis:
            em = discord.Embed(color=discord.Color.red(
            ), description=f"You are missing the `manage emojis` permission in {emoji.guild.name}")
            return await ctx.reply(embed=em)
        if not _author.guild.me.guild_permissions.manage_emojis:
            em = discord.Embed(color=discord.Color.red(
            ), description=f"I am missing the `manage emojis` permission in {emoji.guild.name}")
            return await ctx.reply(embed=em)

        await ctx.reply(embed=discord.Embed(color=orange, description=f"Are you sure you want to delete {str(emoji)}?"),
                        view=botconfig.ConfirmationDeleteView(ctx, emoji, timeout=None))

    @emoji.command(name="edit")
    async def edit(self, ctx: commands.Context, emoji: discord.Emoji, *, name: str):
        """Edits the `emoji`'s name, if the bot can see it"""
        _author = emoji.guild.get_member(ctx.author.id)
        if _author is None:
            em = discord.Embed(color=discord.Color.red(),
                               description="You're not in that server")
            return await ctx.reply(embed=em)
        if not _author.guild_permissions.manage_emojis:
            em = discord.Embed(color=discord.Color.red(
            ), description=f"You are missing the `manage emojis` permission in {emoji.guild.name}")
            return await ctx.reply(embed=em)
        if not _author.guild.me.guild_permissions.manage_emojis:
            em = discord.Embed(color=discord.Color.red(
            ), description=f"I am missing the `manage emojis` permission in {emoji.guild.name}")
            return await ctx.reply(embed=em)
        name = name.replace(" ", "_")
        try:
            await emoji.edit(name=name, reason=f"{ctx.author} changed name from {emoji.name} to {name}")
        except discord.HTTPException as e:
            em = discord.Embed(color=discord.Color.red(), description=str(e))
        await ctx.message.add_reaction("\U0001f44d")

    @emoji.command(aliases=["reactions"])
    async def reaction(self, ctx: commands.Context, message: discord.PartialMessage = None):
        """Shows the emojis of a message's reactions.
        message can be `channelID-messageID`, `messageID` (in the same channel), message URL or just a reply to that message"""
        try:
            if message is None:
                if ctx.message.reference is None:
                    raise commands.MissingRequiredArgument("message")
                mes = await ctx.fetch_message(ctx.message.reference.message_id)
            else:
                mes = await message.fetch()
        except (NotFound, HTTPException):
            return await ctx.reply("I couldn't find that message")
        if not mes.reactions:
            return await ctx.reply("This message has no reactions")
        emojis: list[typing.Union[discord.Emoji, discord.PartialEmoji]] = [
            m.emoji for m in mes.reactions if isinstance(m.emoji, (discord.Emoji, discord.PartialEmoji))]
        if not emojis:
            return await ctx.reply("This message has no custom emojis")
        source = botconfig.EmojiPageSource(emojis, per_page=1)
        pages = botconfig.EmojiPages(source, client=self.bot,
                                     author=ctx.author, channel=ctx.channel, search=True)
        await pages.start()

    @commands.group()
    @commands.has_guild_permissions(administrator=True)
    async def prefix(self, ctx: commands.Context):
        """Manages the bot's prefixes, use help prefix for subcommands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @prefix.command()
    async def set(self, ctx: commands.Context, *, prefix: str):
        """Sets or edits the bot's prefix for this server"""
        async with self.bot.db.cursor() as cur:
            await cur.execute("INSERT OR REPLACE INTO prefixes (id, prefix) VALUES (?, ?)", (ctx.guild.id, prefix))
            await self.bot.db.commit()
        em = discord.Embed(
            color=orange, description=f"Prefix set to `{prefix}` for this server")
        await ctx.reply(embed=em, mention_author=False)

    @prefix.command()
    async def remove(self, ctx: commands.Context):
        """Removes the bot's prefix from this server"""
        async with self.bot.db.cursor() as cur:
            await cur.execute("DELETE FROM servers WHERE id=?", (ctx.guild.id,))
            await self.bot.db.commit()
        await ctx.message.add_reaction("\U0001f44d")

    @commands.command(hidden=True)
    async def charinfo(self, ctx, *, characters: str):
        """Shows you information about a number of characters.
        Only up to 25 characters at a time.
        """
        def to_string(c):
            digit = f'{ord(c):x}'
            name = unicodedata.name(c, 'Name not found.')
            return f'`\\U{digit:>08}`: {name} - {c} \N{EM DASH} <http://www.fileformat.info/info/unicode/char/{digit}>'

        msg = '\n'.join(map(to_string, characters))
        if len(msg) > 2000:
            return await ctx.send('Output too long to display.')
        await ctx.send(msg)

    @commands.command(hidden=True)
    async def translate(self, ctx: commands.Context, *, message: commands.clean_content = None):
        """Translates a message to English using Google translate."""

        loop = self.bot.loop
        if message is None:
            ref = ctx.message.reference
            if ref and isinstance(ref.resolved, discord.Message):
                message = ref.resolved.content
                repl = ref.resolved
            else:
                return await ctx.send('Missing a message to translate')
        else:
            repl = ctx.message

        try:
            ret = await loop.run_in_executor(None, self.trans.translate, message)
        except Exception as e:
            return await ctx.send(f'An error occurred: {e.__class__.__name__}: {e}')

        embed = discord.Embed(colour=orange)
        src = googletrans.LANGUAGES.get(ret.src, '(auto-detected)').title()
        embed.title = f"Translated from {src}"
        embed.description = ret.text
        await repl.reply(embed=embed, mention_author=False)

    @commands.has_permissions(manage_messages=True)
    @commands.group(name="purge", aliases=["clear"], invoke_without_command=True)
    async def purge(self, ctx: commands.Context, limit=None, *, content=None):
        """Deletes messages from the current channel.
        `limit`: The number of messages to search through, defaults to 1.
        This is not the number of messages that will be deleted, though it can be.
        `content`: Deletes messages with that specific word/sentence.
        """
        if limit is None:
            limit = 1
        try:
            limit = int(limit)
        except ValueError:
            return await ctx.send(embed=discord.Embed(color=discord.Color.red(), description=f"{limit} is an invalid number"))
        if content is None:
            mes = await ctx.channel.purge(limit=limit+1)
            em = discord.Embed(color=orange)
            em.set_author(name=ctx.author,
                          icon_url=ctx.author.display_avatar.url)
            em.description = f"I deleted {len(mes)-1} messages"
            await ctx.send(embed=em)
        else:
            def check(message: discord.Message):
                if message.content == "":
                    return False
                else:
                    return content.lower() in message.content.lower()
            mes = await ctx.channel.purge(limit=limit+1, check=check)
            em = discord.Embed(color=orange)
            em.set_author(name=ctx.author,
                          icon_url=ctx.author.display_avatar.url)
            em.description = f"I deleted {len(mes)} messages with \"{content.lower()}\" in them"
            await ctx.send(embed=em)

    @commands.has_permissions(manage_messages=True)
    @purge.command(name="bot")
    async def _bot(self, ctx: commands.Context, limit=None):
        """Deletes bot messages from the current channel.
        `limit`: The number of messages to search through, defaults to 1.
        This is not the number of messages that will be deleted, though it can be."""
        if limit is None:
            limit = 1
        try:
            limit = int(limit)
        except ValueError:
            return await ctx.send(embed=discord.Embed(color=discord.Color.red(), description=f"{limit} is an invalid number"))

        def check(m: discord.Message):
            return m.author.bot
        mes = await ctx.channel.purge(limit=limit, check=check)
        em = discord.Embed(color=orange)
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        em.description = f"I deleted {len(mes)} messages from bots"
        await ctx.send(embed=em)

    @commands.has_permissions(manage_messages=True)
    @purge.command(aliases=["attachments", "files"])
    async def images(self, ctx: commands.Context, limit=None):
        """Deletes messages with attachments from the current channel.
        `limit`: The number of messages to search through, defaults to 1.
        This is not the number of messages that will be deleted, though it can be."""
        if limit is None:
            limit = 1
        try:
            limit = int(limit)
        except ValueError:
            return await ctx.send(embed=discord.Embed(color=discord.Color.red(), description=f"{limit} is an invalid number"))

        def check(m: discord.Message):
            return bool(m.attachments)
        mes = await ctx.channel.purge(limit=limit, check=check)
        em = discord.Embed(color=orange)
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        em.description = f"I deleted {len(mes)} messages with attachments"
        await ctx.send(embed=em)

    @commands.has_permissions(manage_messages=True)
    @purge.command(aliases=["sticker"])
    async def stickers(self, ctx: commands.Context, limit=None):
        """Deletes mesages with stickers from the current channel.
        `limit`: The number of messages to search through, defaults to 1.
        This is not the number of messages that will be deleted, though it can be."""
        if limit is None:
            limit = 1
        try:
            limit = int(limit)
        except ValueError:
            return await ctx.send(embed=discord.Embed(color=discord.Color.red(), description=f"{limit} is an invalid number"))

        def check(m: discord.Message):
            return bool(m.stickers)
        mes = await ctx.channel.purge(limit=limit, check=check)
        em = discord.Embed(color=orange)
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        em.description = f"I deleted {len(mes)} messages with stickers"
        await ctx.send(embed=em)

    @purge.command(aliases=["author"])
    async def self(self, ctx: commands.Context, limit=None):
        """Deletes your own messages from the current channel.
        Anyone can call this command on themselves.
        `limit`: The number of messages to search through, defaults to 1.
        This is not the number of messages that will be deleted, though it can be."""
        if limit is None:
            limit = 1
        try:
            limit = int(limit)
        except ValueError:
            return await ctx.send(embed=discord.Embed(color=discord.Color.red(), description=f"{limit} is an invalid number"))

        def check(m: discord.Message):
            return m.author == ctx.author
        mes = await ctx.channel.purge(limit=limit, check=check)
        em = discord.Embed(color=orange)
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        em.description = f"I deleted {len(mes)} messages from {ctx.author.mention}"
        await ctx.send(embed=em)

    @commands.has_permissions(manage_messages=True)
    @purge.command(aliases=["member"])
    async def user(self, ctx: commands.Context, user, limit=None):
        """Deletes messages from a specific `user` from the current channel.
        `limit`: The number of messages to search through, defaults to 1.
        This is not the number of messages that will be deleted, though it can be."""
        user = await convert(ctx, user)
        if limit is None:
            limit = 1
        try:
            limit = int(limit)
        except ValueError:
            return await ctx.send(embed=discord.Embed(color=discord.Color.red(), description=f"{limit} is an invalid number"))

        def check(m: discord.Message):
            return m.author == user
        mes = await ctx.channel.purge(limit=limit, check=check)
        em = discord.Embed(color=orange)
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        em.description = f"I deleted {len(mes)} messages from {user.mention}"
        await ctx.send(embed=em)

    @commands.command()
    async def inrole(self, ctx: commands.Context, role):
        """Returns all the users in the specified role."""
        role = await convert_role(ctx, role)
        if len(role.members) == 0:
            return await ctx.send(embed=discord.Embed(color=red, description="No users have that role"))

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
        pages = botconfig.RolePages(entries=new_list, ctx=ctx, role=role)
        await pages.start()

    @commands.command(aliases=["esnipe", "es"])
    async def editsnipe(self, ctx: commands.Context, messages=None):
        """Searches message edits in the database.
        `messages`: how far to search through.
        Works with a message reply too."""

        # TODO finish the single queries
        # TODO check for no messages returned (nothing to snipe)
        # TODO finish the magic queries

        async with self.bot.db.cursor() as cur:
            if (ctx.message.reference is None) and (messages is None):  # search one only
                firstquer = f"SELECT message FROM edits WHERE channel = {ctx.channel.id} ORDER BY timestamp DESC LIMIT 1"
                await cur.execute(firstquer)
                mes = await cur.fetchone()
                if not mes:
                    return await ctx.send(embed=discord.Embed(color=red, description="I couldn't find anything"))
                message_id = mes[0]
                query = f"SELECT content, timestamp, author FROM edits WHERE message = {message_id} ORDER BY timestamp ASC"
            elif messages is not None:  # offset
                try:
                    messages = int(messages)-1
                except ValueError:
                    return await ctx.send(embed=discord.Embed(color=red, description=f"`{messages}` is an invalid number"))
                firstquer = f"SELECT DISTINCT message FROM edits WHERE channel = {ctx.channel.id} ORDER BY timestamp DESC LIMIT 1 OFFSET {messages}"
                await cur.execute(firstquer)
                mes = await cur.fetchone()
                if not mes:
                    return await ctx.send(embed=discord.Embed(color=red, description="I couldn't find anything"))
                message_id = mes[0]
                query = f"SELECT content, timestamp, author FROM edits WHERE message = {message_id} ORDER BY timestamp ASC"
            else:  # magic reference lookup - ctx.reference should always exist
                message_id = ctx.message.reference.message_id
                query = f"SELECT content, timestamp, author FROM edits WHERE message = {message_id} ORDER BY timestamp ASC"

            await cur.execute(query)
            allmessages = await cur.fetchall()
        if not allmessages:
            return await ctx.reply(embed=discord.Embed(color=red, description="I couldn't find anything"))
        edits = allmessages[1:]
        # edits = [] #list of all edits [(content, timestamp, author), ...]
        original: tuple = allmessages[0]
        author = self.bot.get_user(int(original[-1]))
        if author is None:
            try:
                author = await self.bot.fetch_user(int(original[-1]))
            except (discord.NotFound, discord.HTTPException):
                author = None
        pages = botconfig.SnipeSimplePages(
            entries=edits, ctx=ctx, original=original, author=author)
        await pages.start()

    @commands.command()
    async def starboard(self, ctx: commands.Context):
        """You make a \"starboard\" channel and everything works like magic.
        Reactions > 3 :star: = pin.
        Reactions < 3 :star: = unpin.
        One admin star is enough to keep the message saved."""
        em = discord.Embed(color=orange)
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        em.description = """You make a \"starboard\" channel and everything works like magic.
        Reactions > 3 :star: = pin.
        Reactions < 3 :star: = unpin.
        One admin star is enough to keep the message saved."""
        await ctx.send(embed=em)

    @commands.command(name="18check")
    async def _18check(self, ctx: commands.Context):
        """Adds the 'over 18' role to above 18 mushroom members based only on their birthday."""
        mushroom = self.bot.get_guild(749670809110315019)
        over18 = mushroom.get_role(849833845603696690)
        async with self.bot.db.cursor() as cur:
            await cur.execute(f"SELECT user, year FROM birthdays")
            bd = await cur.fetchall()
        bds = {}
        for user, year in bd:
            bds[user] = year
        done = []
        for member in mushroom.members:
            if not member.id in bds.keys():
                continue
            age = datetime.datetime.now().year - bds[member.id]
            if age >= 18:
                if over18 in member.roles:
                    continue
                done.append(member)
                await member.add_roles(over18)
        if len(done) == 0:
            async with ctx.typing():
                await asyncio.sleep(5)
            return await ctx.reply("they all already have the role, stfu", mention_author=False)
        em = discord.Embed(color=orange)
        em.description = f"role added to: {', '.join([str(m) for m in done])}"
        await ctx.reply(embed=em)

    @commands.command()
    async def members(self, ctx: commands.Context):
        """Shows members in the server, ordered by their joined date"""
        entries = [f"<t:{int(k.joined_at.timestamp())}:d> {k.mention}" for k in sorted(
            [m for m in ctx.guild.members if (not m.bot)], key=lambda x: x.joined_at)]
        pages = botconfig.SimplePages(entries=entries, ctx=ctx,
                                      title="members", description="ordered by join date")
        await pages.start()

    @commands.has_guild_permissions(administrator=True)
    @commands.command()
    async def invitelog(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Sets the channel to log invites to.
        If no channel is given, the bot stops logging invites from this server."""
        if channel is None:
            await ctx.message.add_reaction("\U0001f44d")
            async with self.bot.db.cursor() as cur:
                await cur.execute(
                    f"DELETE FROM invites WHERE server = {ctx.guild.id}")
                await self.bot.db.commit()
        else:
            await ctx.message.add_reaction("\U0001f44d")
            async with self.bot.db.cursor() as cur:
                await cur.execute(
                    f"DELETE FROM invites WHERE server = {ctx.guild.id}")
                await self.bot.db.commit()
                await cur.execute(
                    f"INSERT INTO invites (server, channel) VALUES ({ctx.guild.id}, {channel.id})")
                await self.bot.db.commit()
        await self.bot.cogs["events"].update_invites.__call__()

    @commands.command(name="download")
    async def _download(self, ctx: commands.Context, *, link: str):
        """Helper command to download videos/media from internet.
        Supported sites: tiktok, youtube"""
        tiktokmatch = re.match(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", link)
        youtubematch = re.match(
            r"^(https?\:\/\/)?((www\.)?youtube\.com|youtu\.be)\/.+$", link)
        if youtubematch:
            return await youtube_method(ctx, link)
        elif tiktokmatch:
            return await tiktok_method(ctx, link)
        else:
            # return await ctx.send(embed=discord.Embed(color=red, description="`link` is not a valid youtube or tiktok URL"))
            raise commands.BadArgument(
                "`link` is not a valid youtube or tiktok URL")

    @commands.command()
    async def tiktok(self, ctx: commands.Context, *, link: str):
        """Downloads and uploads a titok video, without watermak, given the URL"""
        tiktokmatch = re.match(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", link)
        if (not tiktokmatch) and (not ("tiktok" in link)):
            return await ctx.reply("That's not a valid URL.")
        await ctx.typing()
        await tiktok_method(ctx, link)

    @commands.command()
    async def youtube(self, ctx: commands.Context, url):
        """Helper to download YouTube videos"""
        youtubematch = re.match(
            r"^(https?\:\/\/)?((www\.)?youtube\.com|youtu\.be)\/.+$", url)
        if not youtubematch:
            return await ctx.reply("That's not a valid YouTube URL.")
        await ctx.typing()
        await youtube_method(ctx, url)

    @commands.command()
    async def lurk(self, ctx: commands.Context, server=None):
        """Returns a paginator with the server's emojis, if available.
        This should work with servers the bot can see and public servers.
        `server` must be the ID of the server."""
        if server is None:
            server = ctx.guild.id
        else:
            try:
                server = int(server)
            except ValueError:
                return await ctx.reply("That's not a valid server ID.")
        route = discord.http.Route(
            "GET", "/guilds/{guild_id}/preview", guild_id=server)
        try:
            response = await self.bot.http.request(route)
        except discord.NotFound:
            return await ctx.reply("Discord couldn't find that server or the ID is invalid")
        emojis: list[discord.PartialEmoji] = []
        for emoji_data in response.get("emojis"):
            if emoji_data["roles"]:
                continue
            emoji = discord.PartialEmoji.with_state(
                name=emoji_data["name"], id=emoji_data["id"], animated=emoji_data["animated"], state=self.bot._connection)
            emojis.append(emoji)
        icon = f'https://cdn.discordapp.com/icons/{response["id"]}/{response["icon"]}.{"gif" if response["icon"].startswith("a_") else "png"}'
        name = response["name"]
        source = botconfig.EmojiPageSource(
            emojis, per_page=1, name=name, icon=icon)
        pages = botconfig.EmojiPages(source, client=self.bot,
                                     author=ctx.author, channel=ctx.channel, search=True)
        await pages.start()

    @commands.command(name="reload", hidden=True)
    async def _reload(self, ctx: commands.Context):
        """Owner only command to reload extensions"""
        if not ctx.author.id in self.bot.owner_ids:
            return
        importlib.reload(botconfig)
        cogs = [cog for cog in self.bot.cogs.keys()]
        for cog in cogs:
            if cog in ("Jishaku"):
                continue
            await self.bot.unload_extension(f"cogs.{cog}")
        reloaded = []
        for cog in os.listdir("cogs"):
            if not cog.endswith(".py"):
                continue
            if cog in (None,):  # add blacklisted cogs? idfk
                continue
            await self.bot.load_extension(f"cogs.{cog[:-3]}")
            reloaded.append(cog[:-3])
        await ctx.reply(f"Reloaded {', '.join(reloaded)}", mention_author=False)

    @commands.command(hidden=True)
    async def adminconfig(self, ctx: commands.Context):
        """Just sends the persistent view"""
        if not ctx.author.id in self.bot.owner_ids:
            return
        await ctx.message.delete(delay=5)
        await ctx.send(view=botconfig.ConfigView(self.bot))

    @commands.has_guild_permissions(manage_emojis_and_stickers=True)
    @commands.command(name="sticker")
    async def _sticker(self, ctx: commands.Context):
        """Helper command to create stickers"""
        view = StickerView(ctx.author)
        m = await ctx.reply("How do you want to make it?", view=view)
        await view.wait()
        if view.value == 1:
            modal = view.modal
            name = modal.name.value
            description = modal.description.value

            if modal.name.value is None or modal.description.value is None:
                return await m.edit(content="You fucked up submitting the modal or something")

            await m.edit(content="Now send me the sticker in the chat", view=None)

            def check(message: discord.Message):
                return message.author == ctx.author and message.stickers
            try:
                message = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                return await m.edit(content="Timed out...")
            sticker: discord.Sticker = message.stickers[0]

            await m.edit(content="Last thing, react to this message with a discord default emoji")

            def check(reaction: discord.Reaction, user: discord.User):
                return (user == ctx.author) and (reaction.message == m) and (isinstance(reaction.emoji, str))
            try:
                reaction, user = await self.bot.wait_for("reaction_add", check=check, timeout=60)
            except asyncio.TimeoutError:
                return await m.edit(content="You got timed out")
            try:
                new_sticker = await ctx.guild.create_sticker(name=name,
                                                             description=description, emoji=str(
                                                                 reaction.emoji),
                                                             file=(await sticker.to_file()), reason=f"Done by {ctx.author} (ID: {ctx.author.id})")
            except HTTPException as e:
                return await ctx.send(str(e))
            await message.delete()
            return await ctx.send("Done", stickers=[new_sticker])

        elif view.value == 2:
            modal = view.modal
            name = modal.name.value
            description = modal.description.value

            if modal.name.value is None or modal.description.value is None:
                return await m.edit(content="You fucked up submitting the modal or something")

            await m.edit(content="Send me the image in the chat", view=None)

            def check(message: discord.Message):
                return message.author == ctx.author and message.attachments
            try:
                message = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                return await m.edit(content="Timed out...")
            sticker: discord.Sticker = message.attachments[0]

            await m.edit(content="Last thing, react to this message with a discord default emoji")

            def check(reaction: discord.Reaction, user: discord.User):
                return (user == ctx.author) and (reaction.message == m) and (isinstance(reaction.emoji, str))
            try:
                reaction, user = await self.bot.wait_for("reaction_add", check=check, timeout=60)
            except asyncio.TimeoutError:
                return await m.edit(content="You got timed out")
            try:
                new_sticker = await ctx.guild.create_sticker(name=name,
                                                             description=description, emoji=str(
                                                                 reaction.emoji),
                                                             file=(await sticker.to_file()), reason=f"Done by {ctx.author} (ID: {ctx.author.id})")
            except HTTPException as e:
                return await ctx.send(str(e))
            await message.delete()
            return await ctx.send("Done", stickers=[new_sticker])
        elif view.value == 3:
            pass  # make them give url through a modal

    @commands.command()
    async def uptime(self, ctx: commands.Context):
        await ctx.send(f"""Started {discord.utils.format_dt(self.bot.launch_time, style='R')}, running since {discord.utils.format_dt(self.bot.launch_time, 'F')}""")

    @commands.command()
    async def sql(self, ctx: commands.Context, *, query: str):
        if not ctx.author.id in self.bot.owner_ids:
            return
        async with self.bot.db.cursor() as cursor:
            if query.endswith("-fetchone"):
                query = query[:-9].strip()
                await cursor.execute(query)
                data = await cursor.fetchone()
                if not data:
                    return await ctx.reply("Nothing found in the database")
                s = "\n".join(f"{k}: {v}" for k,v in zip(data.keys(), data))
                await ctx.reply(f"```{s}```")
            elif query.endswith("-execute"):
                query = query[:-8].strip()
                await cursor.execute(query)
                await self.bot.db.commit()
                await ctx.message.add_reaction("\U0001f44d")
            else:
                await cursor.execute(query)
                await self.bot.db.commit()
                await ctx.message.add_reaction("\U0001f44d")

    @commands.command()
    async def nicknames(self, ctx:commands.Context, member:typing.Optional[discord.Member]=None):
        """Shows `member`'s history of nicknames"""
        if member is None:
            member = ctx.author
        await ctx.reply("Still working on this")
    
    @commands.command()
    async def usernames(self, ctx:commands.Context, user:typing.Optional[discord.User]=None):
        """Shows `user`'s history of usernames"""
        if user is None:
            user = ctx.author
        await ctx.reply("Still working on this")
        


async def setup(bot: botconfig.AndreiBot):
    await bot.add_cog(utility(bot))
