from code import interact
from io import BytesIO
import discord
from discord.errors import Forbidden, HTTPException
from discord.ext import commands, tasks
import random
import asyncio
import os
import random
import datetime
import typing
import os
import botconfig
from subprocess import Popen

class events(commands.Cog):
    def __init__(self, bot: botconfig.AndreiBot):
        self.bot = bot
        self.gn_msg.start()
        self.gm_msg.start()
        self.birthdayannouncer.start()
        self.vanities: dict[int, discord.Invite] = {}
        self.invites = {}
        self.channels = {}  # server_id : channel_id
        self.update_invites.start()
        self.goodevening.start()
        self.raw_reaction_task.start()
        self.daily_backup.start()

    def cog_unload(self):
        self.gn_msg.cancel()
        self.gm_msg.cancel()
        self.birthdayannouncer.cancel()
        self.update_invites.cancel()
        self.goodevening.cancel()
        self.raw_reaction_task.cancel()
        self.daily_backup.cancel()

    @tasks.loop(hours=24)
    async def goodevening(self):
        channel = self.bot.get_channel(785651298090614784)
        replies = (
            "Good evening everyone!",
            "Good evening everybody!",
            "GOOD EVENING",
            "GOOD EVENING EVERYBODY",
            "good evening."
        )
        await channel.send(random.choice(replies))

    @goodevening.before_loop
    async def goodeveningwaiter(self):
        now = datetime.datetime.now().astimezone()
        next_run = now.replace(hour=16, minute=0, second=0)

        if next_run < now:
            next_run += datetime.timedelta(days=1)

        await discord.utils.sleep_until(next_run)

    @tasks.loop(hours=24)
    async def gm_msg(self):
        channel = self.bot.get_channel(785651298090614784)
        await channel.typing()
        authors = []
        async for message in channel.history(limit=None, after=datetime.datetime.utcnow() - datetime.timedelta(hours=11)):
            if message.author.id == self.bot.user.id:
                continue
            ctm = message.content.lower()
            if "morning" in ctm or "gm" in ctm or "g m" in ctm:
                if message.author.display_name in authors:
                    continue
                authors += [message.author.display_name]
        if authors == []:
            content = "Good morning everyone."
        elif len(authors) == 1:
            content = f"Good morning {authors[0]}"
        else:
            ct = ""
            last_index = len(authors) - 1
            for user in authors:
                if authors.index(user) == last_index:
                    ct = ct[:-2] + f" and fuck {user}"
                    break
                ct += f"{user}, "
            content = f"Good morning {ct}"
        await channel.send(content)

    @gm_msg.before_loop
    async def _gmwaiter(self):
        # `.now().astimezone()` uses the local timezone
        # for a specific timezone use `.now(timezone)` without `.astimezone()`
        # timezones can be acquired using any of
        # datetime.timezone.utc
        # datetime.timezone(datetime.timedelta(...))
        # zoneinfo.ZoneInfo('TZDB/Name')
        now = datetime.datetime.now().astimezone()
        next_run = now.replace(hour=10, minute=0, second=0)

        if next_run < now:
            next_run += datetime.timedelta(days=1)

        await discord.utils.sleep_until(next_run)

    @tasks.loop(hours=24)
    async def gn_msg(self):
        channel = self.bot.get_channel(785651298090614784)
        await channel.typing()
        authors = []
        async for message in channel.history(limit=None, after=datetime.datetime.utcnow() - datetime.timedelta(hours=16)):
            if message.author.id == self.bot.user.id:
                continue
            ctm = message.content.lower()
            if "night" in ctm or "gn" in ctm or "g n" in ctm or "nite" in ctm:
                if message.author.display_name in authors:
                    continue
                authors += [message.author.display_name]
        if authors == []:
            content = "Good night everyone."
        elif len(authors) == 1:
            content = f"Good night {authors[0]}"
        else:
            ct = ""
            last_index = len(authors) - 1
            for user in authors:
                if authors.index(user) == last_index:
                    ct = ct[:-2] + f" and fuck {user}"
                    break
                ct += f"{user}, "
            content = f"Good night {ct}"
        await channel.send(content)

    @gn_msg.before_loop
    async def _gnwaiter(self):
        # `.now().astimezone()` uses the local timezone
        # for a specific timezone use `.now(timezone)` without `.astimezone()`
        # timezones can be acquired using any of
        # datetime.timezone.utc
        # datetime.timezone(datetime.timedelta(...))
        # zoneinfo.ZoneInfo('TZDB/Name')
        now = datetime.datetime.now().astimezone()
        next_run = now.replace(hour=23, minute=0, second=0)

        if next_run < now:
            next_run += datetime.timedelta(days=1)

        await discord.utils.sleep_until(next_run)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        log_channel = self.bot.get_channel(self.bot.log_channel_id)
        em = discord.Embed(color=discord.Color.green(
        ), description=f"Joined a new Server\nOwner: {guild.owner.name}#{guild.owner.discriminator} - {guild.owner_id}\nMembers: {guild.member_count} - Roles: {len(guild.roles)} - Channels: {len(guild.text_channels) + len(guild.voice_channels)}")
        em.set_footer(text=f"Server ID: {guild.id}")
        if guild.icon:
            em.set_image(url=guild.icon.url)
            em.set_author(name=f"{guild.name}", icon_url=guild.icon.url)
        else:
            em.set_author(name=f"{guild.name}")
        await log_channel.send(embed=em)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        log_channel = self.bot.get_channel(self.bot.log_channel_id)
        em = discord.Embed(color=discord.Color.red(
        ), description=f"Left a Server\nOwner: {guild.owner.name}#{guild.owner.discriminator} - {guild.owner_id}\nMembers: {guild.member_count} - Roles: {len(guild.roles)} - Channels: {len(guild.text_channels) + len(guild.voice_channels)}")
        em.set_footer(text=f"Server ID: {guild.id}")
        if guild.icon:
            em.set_image(url=guild.icon.url)
            em.set_author(name=f"{guild.name}", icon_url=guild.icon.url)
        else:
            em.set_author(name=f"{guild.name}")
        await log_channel.send(embed=em)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
        async with self.bot.db.cursor() as cur:
            ts = int(message.created_at.timestamp())
            newreq = "INSERT into messages (server, channel, message, author, timestamp, content) VALUES (?, ?, ?, ?, ?, ?)"
            if message.content:
                mc = message.content
            else:
                mc = "This message had no content"
            await cur.execute(newreq, (message.guild.id, message.channel.id,
                                       message.id, message.author.id, ts, mc))
            await self.bot.db.commit()
        if message.attachments:
            attachment = message.attachments[0]
            filebytes = await attachment.read()
            self.bot.deleted_files[message.id] = (
                filebytes, attachment.filename)

            await asyncio.sleep(3600)
            self.bot.deleted_files.pop(message.id, None)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # counting channels i think
        if message.channel.id in (928597369111576597, 715986355485933619):
            if message.attachments or message.components or message.embeds or message.stickers:
                return await message.delete()
            elif message.content is None:
                return await message.delete()
            async for last_message in message.channel.history(before=message.created_at, limit=1):
                pass
            if message.author.id == last_message.author.id:
                return await message.delete()
            try:
                vals = ["*", "_", " "]
                c = message.content
                for val in vals:
                    if c.startswith(val) and c.endswith(val):
                        c = c.replace(val, "")
                number = int(c)
            except ValueError:
                return await message.delete()
            old_number = int(last_message.content)
            if number != (old_number+1):
                return await message.delete()
            return
        if message.author.bot:
            return

        if not message.guild:
            if message.author.id in (393033826474917889,):  # andrei id
                return
            member = message.author
            log = self.bot.get_channel(self.bot.log_channel_id)
            if message.content == "":
                em = discord.Embed(color=discord.Color.orange())
            else:
                em = discord.Embed(description=message.content,
                                   color=discord.Color.orange())
            em.set_author(
                name=member, icon_url=member.avatar if (member.avatar) else member.display_avatar, url=member.avatar if (member.avatar) else member.display_avatar)
            em.set_footer(text="user id: {}".format(member.id))

            if len(message.attachments) == 1:
                file_type = message.attachments[0].filename.split(
                    ".")[-1].lower()
                if file_type == "png" or file_type == "jpeg" or file_type == "jpg" or file_type == "gif":
                    # set as embed image
                    em.set_image(url=message.attachments[0].proxy_url)
                    await log.send(embed=em)
                else:
                    if message.attachments[0].size > 8388608:
                        return
                    file = await message.attachments[0].to_file()
                    # send file as attachment

                    await log.send(embed=em)
                    await log.send(file=file)

            elif len(message.attachments) > 1:
                await log.send(embed=em)
                for ATTACHMENT in message.attachments:
                    temp_embed = discord.Embed(
                        description=f"multiple files from: {member}", color=discord.Color.orange())
                    temp_embed.set_author(name=member, icon_url=member.avatar if (
                        member.avatar) else member.display_avatar, url=member.avatar if (member.avatar) else member.display_avatar)
                    temp_embed.set_footer(text=f"user id : {member.id}")
                    file_type = ATTACHMENT.filename.split(".")[-1].lower()
                    if file_type == "png" or file_type == "jpeg" or file_type == "jpg" or file_type == "gif":
                        temp_embed.set_image(url=ATTACHMENT.proxy_url)
                        await log.send(embed=temp_embed)
                    else:
                        if ATTACHMENT.size > 8388608:
                            continue
                        file = await ATTACHMENT.to_file()
                        await log.send(embed=temp_embed)
                        await log.send(file=file)
            else:
                await log.send(embed=em)

            return

        role = discord.utils.get(message.guild.roles, name="blacklisted")

        if not role:
            return

        if role in message.author.roles:
            await message.delete()

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]):
        async with self.bot.db.cursor() as cur:
            await cur.executemany("INSERT into messages (server, channel, message, author, timestamp, content) VALUES (?, ?, ?, ?, ?, ?)",
                                  [(message.guild.id, message.channel.id, message.id, message.author.id,
                                    int(message.created_at.timestamp()), message.content if message.content else "This message had no content")
                                   for message in messages])
            await self.bot.db.commit()

    @commands.Cog.listener(name="on_presence_update")
    async def _gaygame(self, before: discord.Member, after: discord.Member):
        if (after is None) or (before is None):
            return
        if before.guild.id != 749670809110315019:
            return
        if before.id in (191705280508067841,  # oxy
                         336233089548288010,  # 4ever
                         693222974777720934,  # giz
                         288319394776612865,  # neyla
                         334805610027679754,  # talha
                         ):
            return
        for role in before.roles:
            if role.is_premium_subscriber():
                return
        for role in after.roles:
            if role.is_premium_subscriber():
                return
        gaygame = False
        gaygames_list = ("league of legends", "fortnite")
        for activity in before.activities:
            if activity.name is None:
                continue
            if activity.name.lower() in gaygames_list:
                gaygame = True
        if not gaygame:
            return
        for activity in after.activities:
            if activity.name is None:
                continue
            if activity.name.lower() in gaygames_list:
                return
        if not gaygame:
            return
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT * FROM clash")
            urls = await cursor.fetchall()
        urls = [m[0] for m in urls]
        url = random.choice(urls)
        try:
            await after.send(content=f"Stop playing that shitty game here's something better\n{url}")
        except (HTTPException, Forbidden):
            c = self.bot.get_channel(755294513068638228)  # botspam
            await c.send(content=f"{after.mention} stop playing that shitty game here's something better\n{url}")

    @commands.Cog.listener(name="on_message")
    async def _cr_downloader(self, message: discord.Message):
        if message.channel.id != 989509034547744848:
            return
        if not message.attachments:
            return await message.delete()
        async with self.bot.db.cursor() as cursor:
            for attachment in message.attachments:
                await cursor.execute("INSERT INTO clash VALUES (?)", (attachment.url, ))
            await self.bot.db.commit()
        await message.add_reaction("\U0001f44d")

    @commands.Cog.listener(name="on_raw_reaction_add")
    async def _starboard_checker(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id in ():  # blacklisted guilds?
            return
        if str(payload.emoji) != "\U00002b50":
            return
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return
        starboard_channel = discord.utils.find(
            lambda t: t.name.lower() == "starboard", channel.guild.text_channels)
        if starboard_channel is None:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return
        pin = False
        for reaction in message.reactions:
            if str(reaction.emoji) == "\U00002b50":
                async for user in reaction.users(limit=None):
                    if user.guild:
                        if user.guild_permissions.administrator:
                            pin = True
                count = reaction.count
                break
            else:
                count = 0
        if (count < 3) and not pin:
            return
        #starboard_channel = self.bot.get_channel(944668442357817394)
        em = discord.Embed(color=discord.Color.orange())
        em.title = f"{count} \U00002b50"
        content = f"[Jump URL]({message.jump_url})\n"
        content += message.content
        em.set_author(name=message.author.display_name,
                      icon_url=message.author.display_avatar.url)
        em.timestamp = message.created_at
        em.set_footer(text=f"ID: {message.id}")
        image_set = False
        if len(message.attachments) == 1:
            if message.attachments[0].url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
                em.set_image(url=message.attachments[0].url)
                image_set = True
            else:
                em.add_field(
                    name="Attachment", value=f"[{message.attachments[0].filename}]({message.attachments[0].url})")

        else:
            for attachment in message.attachments:
                if attachment.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
                    if not image_set:
                        em.set_image(url=attachment.url)
                        image_set = True
                        continue
                em.add_field(name="Attachment",
                             value=f"[{attachment.filename}]({attachment.url})")
        if message.stickers:
            if not image_set:
                em.set_image(url=message.stickers[0].url)
            content += f"\nMessage has {len(message.stickers)} stickers"
        em.description = content
        async with self.bot.db.cursor() as cur:
            await cur.execute(f"SELECT star_id FROM stars WHERE original_message_id={message.id}")
            req = await cur.fetchone()
            if req:
                star_id = req[0]
                try:
                    star_message = await starboard_channel.fetch_message(star_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    return
                return await star_message.edit(embed=em)
            m = await starboard_channel.send(embed=em)
            await cur.execute(f"INSERT INTO stars (original_message_id, star_id) VALUES ({message.id}, {m.id})")
            await self.bot.db.commit()

    @commands.Cog.listener(name="on_raw_reaction_remove")
    async def _remove_star(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id in ():  # blacklisted guilds??
            return

        if str(payload.emoji) != "\U00002b50":
            return
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return
        starboard_channel = discord.utils.find(
            lambda t: t.name.lower() == "starboard", channel.guild.text_channels)
        if starboard_channel is None:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return
        pin = False
        count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == "\U00002b50":
                async for user in reaction.users(limit=None):
                    if user.guild:
                        if user.guild_permissions.administrator:
                            pin = True
                count = reaction.count
                break
            else:
                count = 0
        #starboard_channel = self.bot.get_channel(944668442357817394)
        if (count < 3):
            if pin:
                return
            async with self.bot.db.cursor() as cur:
                await cur.execute(f"SELECT star_id FROM stars WHERE original_message_id={message.id}")
                req = await cur.fetchone()
            if req:
                star_id = req[0]
                try:
                    star_message = await starboard_channel.fetch_message(star_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    return
                await star_message.delete()
                await cur.execute(
                    f"DELETE FROM stars WHERE original_message_id={message.id}")
                await self.bot.db.commit()
                return
        else:
            em = discord.Embed(color=discord.Color.orange())
            em.title = f"{count} \U00002b50"
            content = f"[Jump URL]({message.jump_url})\n"
            content += message.content
            em.set_author(name=message.author.display_name,
                          icon_url=message.author.display_avatar.url)
            em.timestamp = message.created_at
            em.set_footer(text=f"ID: {message.id}")
            image_set = False
            if len(message.attachments) == 1:
                if message.attachments[0].url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
                    em.set_image(url=message.attachments[0].url)
                    image_set = True
                else:
                    em.add_field(
                        name="Attachment", value=f"[{message.attachments[0].filename}]({message.attachments[0].url})")

            else:
                for attachment in message.attachments:
                    if attachment.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
                        if not image_set:
                            em.set_image(url=attachment.url)
                            image_set = True
                            continue
                    em.add_field(name="Attachment",
                                 value=f"[{attachment.filename}]({attachment.url})")
            if message.stickers:
                if not image_set:
                    em.set_image(url=message.stickers[0].url)
                content += f"\nMessage has {len(message.stickers)} stickers"
            em.description = content
            async with self.bot.db.cursor() as cur:
                await cur.execute(f"SELECT star_id FROM stars WHERE original_message_id={message.id}")
                req = await cur.fetchone()
            if req:
                star_id = req[0]
                try:
                    star_message = await starboard_channel.fetch_message(star_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    return
                await star_message.edit(embed=em)

    @commands.Cog.listener(name="on_presence_update")
    async def elsa_stalker(self, before: discord.Member, after: discord.Member):
        return
        if before.guild.id != 831556458398089217:
            return
        if before.id != 369917844508639236:  # elsa's id
            return
        # channel = self.bot.get_channel(785651298090614784)  # gm-gn
        andrei = self.bot.get_user(393033826474917889)
        lurking = (discord.Status.invisible, discord.Status.offline)
        if (before.status in lurking) and (after.status not in lurking):  # offline -> online
            await andrei.send("Elsa got online")
            # await channel.send(f"{before.mention} hello why online")
            return
        if (before.status not in lurking) and (after.status in lurking):  # online -> offline
            await andrei.send("Elsa got offline")
            # await channel.send(f"{before.mention} have fun lurking")
            return

    @commands.Cog.listener("on_message_edit")
    async def _editlogger(self, before: discord.Message, after: discord.Message):
        """(server INTEGER, channel INTEGER, message INTEGER, content, TEXT, timestamp TEXT)"""
        if before.content == after.content:
            return
        if before.author.bot:
            return
        async with self.bot.db.cursor() as cur:
            if before.edited_at is None:
                # original message
                await cur.execute("INSERT into edits (server, channel, message, content, timestamp, author) VALUES (?, ?, ?, ?, ?, ?)",
                                  (before.guild.id, before.channel.id, before.id, before.content, str(int(before.created_at.timestamp())), before.author.id))
            await cur.execute("INSERT into edits (server, channel, message, content, timestamp, author) VALUES (?, ?, ?, ?, ?, ?)",
                              (before.guild.id, before.channel.id, before.id, after.content, str(int(after.edited_at.timestamp())), before.author.id))
            await self.bot.db.commit()

    @tasks.loop(hours=24)
    async def birthdayannouncer(self):
        today = datetime.date.today()
        async with self.bot.db.cursor() as cur:
            await cur.execute(f"SELECT user, year FROM birthdays WHERE day={today.day} AND month={today.month}")
            birthdates = await cur.fetchall()
        if not birthdates:
            return
        us_year = {}
        for user, year in birthdates:
            us_year[user] = year
        birthdays = []
        bd: list[discord.User] = []
        for userid in [k[0] for k in birthdates]:
            us = self.bot.get_channel(
                773852231128186882).guild.get_member(userid)
            if us is None:
                try:
                    us = await self.bot.fetch_user(userid)
                    toapp = str(us)
                except discord.NotFound:
                    continue
            else:
                toapp = us.mention
            bd.append(us)
            birthdays.append(toapp)
        if not (len(birthdays) > 0):
            return
        channel = self.bot.get_channel(
            773852231128186882)  # announcement in mushroom
        await channel.send(f"Happy birthday {', '.join(birthdays)}!")
        for user in bd:
            m = channel.guild.get_member(us.id)
            if m is None:
                continue
            age = today.year - int(us_year[user.id])
            if age >= 18:
                role = channel.guild.get_role(
                    849833845603696690)  # birthday role
                if role not in m.roles:
                    await m.add_roles(role)

    @birthdayannouncer.before_loop
    async def birthdaywaiter(self):
        """This waits for 8am or something and starts looping over birthdays once a day
        I think it's a bad implementation but if it works it works"""
        while True:
            if datetime.datetime.utcnow().hour == 6:
                return
            await asyncio.sleep(10)

    @tasks.loop(minutes=10)
    async def update_invites(self):
        async with self.bot.db.cursor() as cur:
            await cur.execute("SELECT * FROM invites")
            data = await cur.fetchall()
        if not data:
            return
        self.channels = {}
        for server_id, channel_id in data:
            self.channels[server_id] = channel_id

        # list of the old server invites
        invite_servers = list(self.invites.keys())
        for server_id in invite_servers:
            if server_id not in self.channels.keys():
                del self.invites[server_id]
                del self.vanities[server_id]

        for server_id, channel_id in self.channels.items():
            self.invites[server_id] = await self.bot.get_guild(server_id).invites()

        for server_id, channel_id in self.channels.items():
            try:
                self.vanities[server_id] = await self.bot.get_guild(server_id).vanity_invite()
            except discord.Forbidden:
                self.vanities[server_id] = None

    @update_invites.before_loop
    async def waiter(self):
        await self.bot.wait_until_ready()
        async with self.bot.db.cursor() as cur:
            await cur.execute("SELECT * FROM invites")
            data = await cur.fetchall()
        if not data:
            return
        for server_id, channel_id in data:
            self.channels[server_id] = channel_id
            log_channel = self.bot.get_channel(channel_id)
            self.invites[server_id] = await log_channel.guild.invites()
            try:
                self.vanities[server_id] = await log_channel.guild.vanity_invite()
            except discord.Forbidden:
                self.vanities[server_id] = None

    def find_invite_by_code(self, inv_list: list[discord.Invite]) -> typing.Optional[discord.Invite]:
        for new_invite in inv_list:
            for old_invite in self.invites[new_invite.guild.id]:
                if new_invite.code == old_invite.code:
                    if new_invite.uses > old_invite.uses:
                        return new_invite  # if use incremented
                if not (old_invite in self.invites[new_invite.guild.id]):
                    return old_invite  # if an old invite is not in the new list anymore
        return None

    @commands.Cog.listener(name="on_member_join")
    async def joinertracker(self, member: discord.Member):
        if not member.guild.id in self.channels.keys():
            return
        em = discord.Embed(color=discord.Color.orange())
        em.set_author(name=member, icon_url=member.display_avatar.url)
        new_invites = await member.guild.invites()
        vanity = self.vanities[member.guild.id]
        invite = self.find_invite_by_code(new_invites)
        if invite:
            em.description = f"ID: {member.id}\nJoined with: <{invite.url}>\nInviter: {invite.inviter} - {invite.inviter.mention}"

        elif vanity is not None:
            new_vanity = None
            try:
                new_vanity = await member.guild.vanity_invite()
            except discord.Forbidden:
                new_vanity = None
            if new_vanity is None:
                em.description = f"I couldn't figure out how they joiend"
            else:
                if vanity.uses < new_vanity.uses:
                    em.description = f"Joined with the vanity URL (.gg/{new_vanity.code})"
                    self.vanities[member.guild.id] = new_vanity
                else:
                    em.description = f"I couldn't figure out how they joiend"
        else:
            em.description = f"I couldn't figure out how they joiend"
        await self.bot.get_channel(self.channels[member.guild.id]).send(embed=em)
        self.invites[member.guild.id] = await member.guild.invites()

    @commands.Cog.listener(name="on_member_remove")
    async def memberremovercheckidk(self, member: discord.Member):
        if not member.guild.id in self.channels.keys():
            return
        em = discord.Embed(color=discord.Color.red())
        em.set_author(name=member, icon_url=member.display_avatar.url)
        em.description = f"`{member.id}` left the server"
        await self.bot.get_channel(self.channels[member.guild.id]).send(embed=em)
        self.invites[member.guild.id] = await member.guild.invites()

    @commands.Cog.listener(name="on_invite_create")
    async def inviteupdatecreate(self, invite: discord.Invite):
        if not invite.guild.id in self.channels.keys():
            return
        self.invites[invite.guild.id] = await invite.guild.invites()

    @commands.Cog.listener(name="on_invite_delete")
    async def inviteupdatedelete(self, invite: discord.Invite):
        if not invite.guild.id in self.channels.keys():
            return
        self.invites[invite.guild.id] = await invite.guild.invites()

    @tasks.loop()
    async def raw_reaction_task(self):
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT * FROM tasks WHERE NOT completed ORDER BY end_time LIMIT 1")
            next_task = await cursor.fetchone()
        if next_task is None:
            self.raw_reaction_task.cancel()
            return
        until = datetime.datetime.fromtimestamp(
            next_task["end_time"], tz=datetime.timezone.utc)
        if until < discord.utils.utcnow():
            async with self.bot.db.cursor() as cursor:
                await cursor.execute("UPDATE tasks SET completed = true WHERE message = ?", (next_task["message"]))
                await self.bot.db.commit()
                return
        await discord.utils.sleep_until(until)
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("UPDATE tasks SET completed = true WHERE message = ?", (next_task["message"]))
            await self.bot.db.commit()

    @raw_reaction_task.before_loop
    async def wait_for_bot_online(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener(name="on_raw_reaction_add")
    async def mute_check(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "\U0001f507":
            return
        try:
            message: discord.Message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
        except (discord.NotFound, discord.HTTPException, discord.Forbidden):
            return

        reaction = discord.utils.find(lambda r: str(r.emoji) == str(payload.emoji), message.reactions)
        if reaction is None:
            return

        async with self.bot.db.cursor() as cursor:
            await cursor.execute(f"SELECT * FROM tasks WHERE message = {message.id} LIMIT 1")
            task = await cursor.fetchone()

        if task and task["completed"]:
            return
        

        if task is None: # you'll want to start one and cont == 1 will run
            old_count = 0
            begin = True
        else:
            begin = False
            old_count: int = task["count"]

        count = len([user async for user in reaction.users()])

        if count == 1:  # it means we start the task
            until = discord.utils.utcnow() + datetime.timedelta(seconds=60)
            if (not payload.member.guild_permissions.moderate_members) or (payload.member.top_role < message.author.top_role) or (not payload.member.id in self.bot.owner_ids):
                async with self.bot.db.cursor() as cursor:
                    await cursor.execute(f"INSERT INTO tasks (message, count, completed, end_time, start_time) VALUES ({message.id}, 1, false, {int(until.timestamp())}, {int(discord.utils.utcnow().timestamp())})")
                    await self.bot.db.commit()
                if self.raw_reaction_task.is_running():
                    self.raw_reaction_task.restart()
                else:
                    self.raw_reaction_task.start()
                return
        else:
            if old_count < 4:  # this means you'll want to add only 120s to the existing one
                seconds = 120
            else:  # this means you'll want to add 180s to the existing one
                seconds = 180
            if task is None:
                task = {"end_time":int((discord.utils.utcnow() + datetime.timedelta(seconds=60)).timestamp())}
            until = datetime.datetime.fromtimestamp(task["end_time"], tz=datetime.timezone.utc) + datetime.timedelta(seconds=seconds)

        if message.author.timed_out_until and (message.author.timed_out_until > until):
            return

        try:
            await message.author.timeout(until, reason="because of the reaction add")
        except (discord.Forbidden, discord.HTTPException):
            pass
        
        async with self.bot.db.cursor() as cursor:
            if begin:
                await cursor.execute(f"INSERT INTO tasks (message, count, completed, end_time, start_time) VALUES ({message.id}, 1, false, {int(until.timestamp())}, {int(discord.utils.utcnow().timestamp())})")
            else:
                await cursor.execute(f"UPDATE tasks SET count = {count} WHERE message = {message.id}")
            await self.bot.db.commit()
        if self.raw_reaction_task.is_running():
            self.raw_reaction_task.restart()
        else:
            self.raw_reaction_task.start()
    

    @tasks.loop(hours=24)
    async def daily_backup(self):
        log_message = discord.PartialMessage(channel=self.bot.get_channel(982282223166304277), id=999611278832189501)
        Popen(["/usr/lib/git-core/git", "add", "."], cwd=os.getcwd())
        Popen(["/usr/lib/git-core/git", "commit", "-m", "daily backup"], cwd=os.getcwd())
        a = Popen(["/usr/lib/git-core/git", "push", "origin", "main"], cwd=os.getcwd())
        await log_message.edit(content=f"Ran daily backup {discord.utils.format_dt(discord.utils.utcnow())}")
        await log_message.channel.send(a.communicate()[0])

    @daily_backup.before_loop
    async def daily_backup_wait(self):
        now = datetime.datetime.now().astimezone()
        next_run = now.replace(hour=12, minute=0, second=0)

        if next_run < now:
            next_run += datetime.timedelta(days=1)

        await discord.utils.sleep_until(next_run)

async def setup(bot: botconfig.AndreiBot):
    await bot.add_cog(events(bot))
