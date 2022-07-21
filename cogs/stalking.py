import asyncio
import typing
from discord.ext import commands
import discord
import datetime
import botconfig
from io import BytesIO
"""
blacklisted = (
    448822124929351691,  # cipo
    605398335691554827,  # andrei2
    872532633509306429,  # rohail
)"""


class stalking(commands.Cog):
    def __init__(self, bot: botconfig.AndreiBot) -> None:
        super().__init__()
        self.bot = bot
        self.guildid = 749670809110315019
        self.webhook: discord.Webhook = discord.Webhook.from_url(
            "https://discord.com/api/webhooks/994495985294266449/ep3RKX235U3Hq0_3OIMtIoMXKvCr23rCGg0bKPqs5mV3LzC7tGLe0xIu6wUOBMVSzkQL",
            session=self.bot.session,
            bot_token=self.bot.http.token)

    async def taguser(self, user: discord.User, message: str = None):
        if user.bot:
            return
        # if user.id in blacklisted:
        #    return
        m = self.bot.get_guild(self.guildid).get_member(user.id)
        if m is None:
            return
        if not (m.status in (discord.Status.invisible, discord.Status.offline)):
            return
        if message is None:
            tosend = f"I'm lurking"
        else:
            tosend = f"{message}"

        await self.webhook.send(tosend, avatar_url=m.display_avatar.url, username=str(m))

    @commands.Cog.listener()
    async def on_typing(self,
                        channel: discord.TextChannel,
                        user: typing.Union[discord.User, discord.Member],
                        when: datetime.datetime):
        if channel.guild is None:
            return
        if channel.guild.id == self.guildid:
            return await self.taguser(user, f"I was typing in {channel.mention}")
        us = self.bot.get_guild(self.guildid).get_member(user.id)
        if us is None:
            return
        await self.taguser(user, f"I was typing in {channel.guild.name} {channel.mention}")

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if invite.inviter is None:
            return
        if invite.guild.id == self.guildid:
            return await self.taguser(invite.inviter, "I created an invite")
        us = self.bot.get_guild(self.guildid).get_member(invite.inviter.id)
        if us is None:
            return
        await self.taguser(invite.inviter, f"I creted an invite in {invite.guild.name}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return
        if interaction.guild.id == self.guildid:
            return await self.taguser(interaction.user, "I used an interaction")
        us = self.bot.get_guild(self.guildid).get_member(interaction.user.id)
        if us is None:
            return
        await self.taguser(interaction.user, f"I used an interaction in {interaction.guild.name}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.guild.id == self.guildid:
            return await self.taguser(member, "I left")
        us = self.bot.get_guild(self.guildid).get_member(member.id)
        if us is None:
            return
        await self.taguser(member, f"I left {member.guild.name}")

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        # for users not in my server
        if self.bot.get_guild(self.guildid).get_member(before.id) is None:
            return
        await self.taguser(before, "I updated my profile")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return
        if message.guild.id == self.guildid:
            return await self.taguser(message.author, f"I sent a message in {message.channel.mention}")
        us = self.bot.get_guild(self.guildid).get_member(message.author.id)
        if us is None:
            return
        await self.taguser(message.author, f"I sent a message in {message.guild.name} {message.channel.mention}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.guild is None:
            return
        if before.guild.id == self.guildid:
            return await self.taguser(before.author, f"I edited a message in {before.channel.mention}")
        us = self.bot.get_guild(self.guildid).get_member(before.author.id)
        if us is None:
            return
        await self.taguser(before.author, f"I edited a message in {before.guild.name} {before.channel.mention}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: typing.Union[discord.Member, discord.User]):
        if reaction.message.guild is None:
            return
        if reaction.message.guild.id == self.guildid:
            return await self.taguser(user, f"I added a reaction in {reaction.message.channel.mention}")
        us = self.bot.get_guild(self.guildid).get_member(user.id)
        if us is None:
            return
        await self.taguser(user, f"I added a reaction in {reaction.message.guild.name} {reaction.message.channel.mention}")

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: typing.Union[discord.Member, discord.User]):
        if reaction.message.guild is None:
            return
        if reaction.message.guild.id == self.guildid:
            return await self.taguser(user, f"I removed a reaction in {reaction.message.channel.mention}")
        us = self.bot.get_guild(self.guildid).get_member(user.id)
        if us is None:
            return
        await self.taguser(user, f"I removed a reaction {reaction.message.guild.name} {reaction.message.channel.mention}")

    @commands.Cog.listener()
    async def on_thread_member_join(self, member: discord.ThreadMember):
        if member.thread.guild.id != self.guildid:
            return
        await self.taguser(member.thread.guild.get_member(member.id), f"I joined thread {member.thread.mention}")

    @commands.Cog.listener()
    async def on_thread_member_remove(self, member: discord.ThreadMember):
        if member.thread.guild.id != self.guildid:
            return
        await self.taguser(member.thread.guild.get_member(member.id), f"I left thread {member.thread.mention}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.guild is None:
            return
        if member.guild.id == self.guildid:
            await self.taguser(member, f"I updated my voice state in {before.channel.mention if before.channel else after.channel.mention}")
        us = self.bot.get_guild(self.guildid).get_member(member.id)
        if us is None:
            return
        await self.taguser(member, f"I updated my voice state in {member.guild.name} {before.channel.mention if before.channel else after.channel.mention}")

    @commands.Cog.listener(name="on_user_update")
    async def _profile_stalker(self, before: discord.User, after: discord.User):
        channel = self.bot.get_channel(
            978641097087651840)  # log in test server
        if before.id == self.bot.user.id:
            return
        if channel.guild.get_member(before.id) is None:
            return
        em = discord.Embed(color=discord.Color.orange(),
                           description="updated their profile")
        em.set_author(name=after, icon_url=after.display_avatar.url)
        em.set_footer(text=f"ID: {after.id}")
        if before.name != after.name:
            em.add_field(name="userame",
                         value=f"{before.name} -> {after.name}")
        if before.discriminator != after.discriminator:
            em.add_field(name="discriminator",
                         value=f"#{before.discriminator} -> #{after.discriminator}")
        if before.avatar != after.avatar:
            before_av, after_av = None, None
            if before.avatar:
                before_av = f"{before.avatar.key}.{'gif' if before.avatar.is_animated() else 'png'}"
            if after.avatar:
                after_av = f"{after.avatar.key}.{'gif' if after.avatar.is_animated() else 'png'}"
            await asyncio.sleep(20)
            async with self.bot.db.cursor() as cur:
                if before_av:
                    await cur.execute("SELECT url FROM avatars WHERE avatar=?", (before_av, ))
                    before_av = await cur.fetchone()
                    if before_av:
                        before_av = before_av[0]
                if after_av:
                    await cur.execute("SELECT url FROM avatars WHERE avatar=?", (after_av, ))
                    after_av = await cur.fetchone()
                    if after_av:
                        after_av = after_av[0]
            em.add_field(
                name="avatar", value=f"{f'[before]({before_av})' if before_av else 'None'} -> {f'[after]({after_av})' if after_av else 'None'}")
        if not em.fields:
            return
        await channel.send(embed=em)

    @commands.Cog.listener(name="on_member_update")
    async def _member_stalker(self, before: discord.Member, after: discord.Member):
        channel = self.bot.get_channel(
            978641097087651840)  # log in test server
        if before.guild.id != channel.guild.id:
            return
        em = discord.Embed(color=discord.Color.orange(),
                           description="updated their server profile")
        em.set_author(name=after, icon_url=after.display_avatar.url)
        em.set_footer(text=f"ID: {after.id}")
        if before.nick != after.nick:
            em.add_field(name="nickname",
                         value=f"{before.nick} -> {after.nick}")
        if before.guild_avatar != after.guild_avatar:
            before_av, after_av = before.guild_avatar, after.guild_avatar
            if before_av:
                before_av = f"{before_av.key}.{'gif' if before_av.is_animated() else 'png'}"
            if after_av:
                after_av = f"{after_av.key}.{'gif' if after_av.is_animated() else 'png'}"
            await asyncio.sleep(20)
            async with self.bot.db.cursor() as cur:
                if before_av:
                    await cur.execute("SELECT url FROM avatars WHERE avatar=?", (before_av, ))
                    before_av = await cur.fetchone()
                    if before_av:
                        before_av = before_av[0]
                if after_av:
                    await cur.execute("SELECT url FROM avatars WHERE avatar=?", (after_av, ))
                    after_av = await cur.fetchone()
                    if after_av:
                        after_av = after_av[0]
            em.add_field(name="server avatar",
                         value=f"{f'[before]({before_av})' if before_av else 'None'} -> {f'[after]({after_av})' if after_av else 'None'}")
        if not em.fields:
            return
        await channel.send(embed=em)

    @commands.Cog.listener(name="on_member_update")
    async def memberpfplogger(self, before: discord.Member, after: discord.Member):
        if (before.guild_avatar is None) and (after.guild_avatar is None):
            return
        if before.guild_avatar.key == after.guild_avatar.key:
            return

        try:
            av = after.guild_avatar
            fn = f"{av.key}.{'gif' if av.is_animated() else 'png'}"
            fb = await av.read()
            channel = self.bot.get_channel(972944024212234271)
            member = channel.guild.get_member(after.id)
            text = f"{after}'s server avatar (ID: {after.id})"
            if member is None:
                text += f", server ID: {after.guild.id}"
            else:
                text += f" {member.mention}"

            m = await channel.send(file=discord.File(BytesIO(fb), filename=fn), content=text, allowed_mentions=discord.AllowedMentions.none())
            url = m.attachments[0].url
            date = datetime.datetime.now().astimezone().timestamp()
            async with self.bot.db.cursor() as cur:
                await cur.execute("INSERT INTO avatars VALUES (?,?,?,?,?)",
                                  (after.id, fn, date, url, after.guild.id))
                await self.bot.db.commit()

        except (discord.NotFound, discord.HTTPException):
            print(
                f"Failed to download after guild avatar {after.guild.name} (ID: {after.guild.id}) for {after}")

    @commands.Cog.listener(name="on_user_update")
    async def userpfplogger(self, before: discord.User, after: discord.User):
        if (before.avatar is None) and (after.avatar is None):
            return
        if before.avatar.key == after.avatar.key:
            return
        try:
            av = after.avatar
            fn = f"{av.key}.{'gif' if av.is_animated() else 'png'}"
            fb = await av.read()
            channel = self.bot.get_channel(972944024212234271)
            text = f"{after}'s avatar (ID: {after.id})"
            member = channel.guild.get_member(after.id)
            if member:
                text += f" {after.mention}"
            m = await channel.send(file=discord.File(BytesIO(fb), filename=fn),
                                   content=text,
                                   allowed_mentions=discord.AllowedMentions.none())
            url = m.attachments[0].url
            date = datetime.datetime.now().astimezone().timestamp()
            async with self.bot.db.cursor() as cur:
                await cur.execute("INSERT INTO avatars VALUES (?,?,?,?,?)",
                                  (after.id, fn, date, url, 0))
                await self.bot.db.commit()
        except (discord.NotFound, discord.HTTPException):
            print(f"Failed to download avatar for user {after}")

    @commands.Cog.listener(name="on_user_update")
    async def username_logger(self, before: discord.User, after: discord.User):
        """as the name says it logs username changes"""
        if (before.name == after.name) and (before.discriminator == after.discriminator):
            return
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("INSERT INTO usernames (user, date, username, discriminator) VALUES (?, ?, ?, ?)",
                                 (before.id,
                                  int(discord.utils.utcnow().timestamp()),
                                  after.name,
                                  after.discriminator))
            await self.bot.db.commit()

    @commands.Cog.listener(name="on_member_update")
    async def nickname_logger(self, before: discord.Member, after: discord.Member):
        """As the name says this logs nickname changes"""
        if before.nick == after.nick:
            return
        if after.nick is None:
            return
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("INSERT INTO nicknames (server, user, date, nickname) VALUES (?, ?, ?, ?)",
                                 (after.guild.id,
                                  after.id,
                                  int(discord.utils.utcnow().timestamp()),
                                  after.nick))
            await self.bot.db.commit()

    @commands.Cog.listener(name="on_presence_update")
    async def activity_logger(self, before: discord.Member, after: discord.Member):
        if before.status == after.status:
            return
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(f"INSERT OR IGNORE INTO activities (user, time, activity) VALUES (?, ?, ?)",
                                (before.id, int(discord.utils.utcnow().timestamp()), str(after.status)))
            await self.bot.db.commit()


async def setup(bot: botconfig.AndreiBot):
    await bot.add_cog(stalking(bot))
