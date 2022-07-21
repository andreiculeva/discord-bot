import typing
from discord.ext import commands
import discord
import datetime
from typing import Optional
import re
import botconfig

rx = re.compile(r'([0-9]{15,20})$')


class MyRoleConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str):
        match = rx.match(argument) or re.match(
            r'<@&([0-9]{15,20})>$', argument)
        if match:
            result = ctx.guild.get_role(int(match.group(1)))
        else:
            result = discord.utils.get(
                ctx.guild._roles.values(), name=argument)
        if result is None:
            for role in ctx.guild.roles:
                if role.name.lower() == argument:
                    return role
        if result is None:
            for role in ctx.guild.roles:
                if role.name.lower().startswith(argument):
                    return role
        if result is None:
            raise commands.RoleNotFound(argument)
        if (result.position > ctx.author.top_role.position) and (ctx.author.guild.owner != ctx.author):
            raise commands.BadArgument(
                f"You don't have permissions to touch {role.mention}")
        return result


class RemoveRoleConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str):
        match = rx.match(argument) or re.match(
            r'<@&([0-9]{15,20})>$', argument)
        if match:
            result = discord.utils.get(ctx.guild.roles, id=int(match.group(1)))
        else:
            result = discord.utils.get(ctx.guild.roles, name=argument)
        if result is None:
            for role in ctx.guild.roles:
                if role.name.lower() == argument:
                    return role
        if result is None:
            for role in ctx.guild.roles:
                if role.name.lower().startswith(argument):
                    return role
        if result is None:
            raise commands.RoleNotFound(argument)
        if (result.position > ctx.author.top_role.position) and (ctx.author.guild.owner != ctx.author):
            raise commands.BadArgument(
                f"You don't have permissions to touch {role.mention}")
        return result


def can_execute_action(ctx, user, target):
    return user.id == ctx.bot.owner_id or \
        user == ctx.guild.owner or \
        user.top_role > target.top_role


class kickmember(commands.Converter):
    async def convert(self, ctx: commands.Context, argument):
        m = await commands.MemberConverter().convert(ctx, argument)
        if not can_execute_action(ctx, ctx.author, m):
            raise commands.BadArgument(
                f"You can't execute this action on {m} due to role hiearchy")
        return m


class Banuser(commands.Converter):
    async def convert(self, ctx: commands.Context, argument):
        try:
            m = await commands.MemberConverter().convert(ctx, argument)
        except commands.MemberNotFound:
            try:
                member_id = int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(
                    f"{argument} is not a valid member or member ID") from None
            else:
                m = ctx.guild.get_member(member_id)
                if m is None:
                    # just hackban everyone else tbh
                    return discord.Object(id=member_id)
        if not can_execute_action(ctx, ctx.author, m):
            raise commands.BadArgument(
                f"You can't execute this action on {m} due to role hiearchy")
        return m


def can_execute_mute(ctx: commands.Context, user: discord.Member, target: discord.Member):
    return user.id in ctx.bot.owner_ids or \
        user == ctx.guild.owner or \
        user.top_role > target.top_role or \
        ctx.bot != target


orange = discord.Color.orange()
red = discord.Color.red()


class moderation(commands.Cog):
    """Moderation commands"""

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='stafftools', id=314348604095594498)

    def __init__(self, bot: botconfig.AndreiBot) -> None:
        super().__init__()
        self.bot = bot
    

    @commands.has_guild_permissions(manage_messages=True)
    @commands.command(aliases=["cf"])
    async def clearfiles(self, ctx: commands.Context):
        """Deletes all deleted messages from this server saved in ram"""
        async with self.bot.db.cursor() as cur:
            await cur.execute(f"SELECT message FROM messages WHERE  server = {ctx.guild.id}")
            resp = await cur.fetchall()
            if not resp:
                return await ctx.reply("There's nothing to delete")
            messages = [k[0] for k in resp]
            for message in messages:
                self.bot.deleted_files.pop(message, None)
            await ctx.reply("I deleted all files for this server")

    @commands.command(aliases=["timeout"])
    @commands.has_guild_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context,
                    members: commands.Greedy[typing.Union[discord.Member, discord.Role]],
                    amount: commands.Greedy[botconfig.TimeConverter] = None, *,
                    reason: Optional[str] = None):
        """gives `members` a timeout.
        members can take both server members or roles.
        amount defaults to 5 minutes.
        because of the crazy command syntax, here are some examples:
        .mute @user
        .mute @user1 @user2 @user3 1h
        .mute @user spamming
        .mute @user1 @user2 @role1 @user3 5h too active (notice the `@role`)"""
        

        if amount is None:
            amount = 300
        else:
            amount = int(sum(amount))
        if len(members) == 0:
            return await ctx.reply(embed=discord.Embed(color=red, description="`members` is a required argument"))
        if amount > 2419199:
            amount = 2419199
        delta = datetime.timedelta(seconds=int(amount))
        hours, remainder = divmod(int(amount), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        s = ""
        if days:
            s += f"{days} days "
        if hours:
            s += f"{hours} hours "
        if minutes:
            s += f"{minutes} minutes "
        if seconds:
            s += f"{seconds} seconds"

        tomute = []
        for entry in members:
            if isinstance(entry, discord.Member):
                if can_execute_action(ctx, ctx.author, entry):
                    if entry not in tomute:
                        tomute.append(entry)
            elif isinstance(entry, discord.Role):
                for member_role in entry.members:
                    if can_execute_action(ctx, ctx.author, member_role):
                        if member_role not in tomute:
                            tomute.append(member_role)
            else:
                return await ctx.reply("I genuinely have no idea what happened, dm andrei with error code HARRYGAY")
        em = discord.Embed(color=orange)
        if not tomute:
            return await ctx.reply("You can't mute any of those members")
        for member in tomute:
            await member.edit(timed_out_until=(discord.utils.utcnow() + delta),
                              reason=reason or f"action done by {ctx.author} (ID: {ctx.author.id})")
        em.description = f"{', '.join([m.mention for m in tomute])} {'have' if len(tomute) > 1 else 'has'} been muted for {s}"
        if reason:
            em.description+=f"\nreason: {reason}"
        em.set_footer(icon_url=ctx.author.display_avatar.url, text=f"by {ctx.author}")
        await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())

    @commands.command()
    @commands.has_guild_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, members: commands.Greedy[discord.Member]):
        """Removes the timeout from `member`"""
        if len(members) == 0:
            return await ctx.reply(embed=discord.Embed(color=red, description="`members` is a required argument"))
        unmuted: typing.List[discord.Member] = []

        for member in members:
            if member.timed_out_until is None:
                continue
            if can_execute_action(ctx, ctx.author, member):
                unmuted.append(member)

        for member in unmuted:
            await member.edit(timed_out_until=None,reason=f"action done by {ctx.author} (ID: {ctx.author.id})")
        em = discord.Embed(color=orange)
        em.description = f"{', '.join([str(m) for m in unmuted])} {'have' if len(unmuted)>1 else 'has'} been unmuted"
        await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, members: commands.Greedy[Banuser], *, reason=None):
        """Allows you to ban multiple discord users.
        If more than one member is passed, converting errors will silently be ignored.
        """
        if reason is None:
            reason = f"Done by {ctx.author} (ID: {ctx.author.id})"
        if len(members) == 0:
            raise commands.BadArgument("Missing members to ban")
        elif len(members) > 1:
            view = botconfig.ConfirmationView(timeout=None, ctx=ctx)
            await ctx.reply(f"This will ban {len(members)} members, are you sure?", view=view)
            await view.wait()
            if view.value:
                failed = 0
                for member in members:

                    try:
                        await ctx.guild.ban(member, reason=reason)
                    except discord.HTTPException:
                        failed += 1
                em = discord.Embed(
                    color=orange, description=f"Banned {len(members)-failed} members")
                em.set_author(name=ctx.author,
                              icon_url=ctx.author.display_avatar.url)
                return await ctx.reply(embed=em)

        else:
            member = members[0]
            if isinstance(member, discord.Object):
                try:
                    member = await self.bot.fetch_user(member.id)
                except discord.NotFound:
                    pass
            await ctx.guild.ban(member, reason=reason)
            em = discord.Embed(color=orange, description=f"Banned {member}")
            em.set_author(name=ctx.author,
                          icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=em)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def softban(self, ctx: commands.Context, members: commands.Greedy[Banuser], *, reason=None):
        """Allows you to softban (ban and unban with 7 days message delete) multiple discord users.
        If more than one member is passed, converting errors will silently be ignored."""
        if reason is None:
            reason = f"Done by {ctx.author} (ID: {ctx.author.id})"
        if len(members) == 0:
            raise commands.BadArgument("Missing members to softban")
        elif len(members) > 1:
            view = botconfig.ConfirmationView(timeout=None, ctx=ctx)
            await ctx.reply(f"This will softban {len(members)} members, are you sure?", view=view)
            await view.wait()
            if view.value:
                failed = 0
                for member in members:

                    try:
                        await ctx.guild.ban(member, reason=reason, delete_message_days=7)
                        await ctx.guild.unban(member, reason=reason)
                    except discord.HTTPException:
                        failed += 1
                em = discord.Embed(
                    color=orange, description=f"Softbannned {len(members)-failed} members")
                em.set_author(name=ctx.author,
                              icon_url=ctx.author.display_avatar.url)
                return await ctx.reply(embed=em)

        else:
            member = members[0]
            if isinstance(member, discord.Object):
                try:
                    member = await self.bot.fetch_user(member.id)
                except discord.NotFound:
                    pass
            await ctx.guild.ban(member, reason=reason, delete_message_days=7)
            await ctx.guild.unban(member, reason=reason)
            em = discord.Embed(
                color=orange, description=f"Softbannned {member}")
            em.set_author(name=ctx.author,
                          icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=em)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def kick(self, ctx: commands.Context, members: commands.Greedy[kickmember], *, reason=None):
        """Allows you to kick multiple members.
        If more than one member is passed, converting errors will silently be ignored."""
        if reason is None:
            reason = f"Done by {ctx.author} (ID: {ctx.author.id})"
        if len(members) == 0:
            raise commands.BadArgument("Missing members to kick")
        elif len(members) > 1:
            view = botconfig.ConfirmationView(timeout=None, ctx=ctx)
            await ctx.reply(f"This will kick {len(members)} members, are you sure?", view=view)
            await view.wait()
            if view.value:
                failed = 0
                for member in members:
                    try:
                        await ctx.guild.kick(member, reason=reason)
                    except discord.HTTPException:
                        failed += 1
                em = discord.Embed(
                    color=orange, description=f"Kicked {len(members)-failed} members")
                em.set_author(name=ctx.author,
                              icon_url=ctx.author.display_avatar.url)
                return await ctx.reply(embed=em)
        else:
            member = members[0]
            await ctx.guild.kick(member, reason=reason)
            em = discord.Embed(color=orange, description=f"Kicked {member}")
            em.set_author(name=ctx.author,
                          icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=em)

    @commands.has_guild_permissions(manage_roles=True)
    @commands.group(invoke_without_command=True)
    async def role(self, ctx: commands.Context):
        """Add/remove roles from a member"""
        await ctx.send_help("role")
        

    @role.command()
    async def add(self, ctx: commands.Context, member: typing.Optional[discord.Member], roles: commands.Greedy[MyRoleConverter]):
        """Adds `roles` to `member`.
        Member can be the command invoker."""
        if member is None:
            member = ctx.author
        done = []
        failed = []
        if len(roles) == 0:
            em = discord.Embed(color=red, description="Missing roles to add")
            return await ctx.reply(embed=em)
        elif len(roles) == 1:
            await member.add_roles(roles[0], reason=f"Command invoked by {ctx.author} (ID: {ctx.author.id})")
            return await ctx.message.add_reaction("\U0001f44d")
        for role in roles:
            try:
                await member.add_roles(role, reason=f"Command invoked by {ctx.author} (ID: {ctx.author.id})")
                done.append(role)
            except discord.Forbidden:
                failed.append(role)
        em = discord.Embed(color=orange)
        em.description = f"Added {len(done)} roles to {member}"
        if failed:
            em.add_field(name="Failed to add these roles",
                         value=f"{' '.join([r.mention for r in failed])}\nDue to permissions/hierarchy")
        await ctx.reply(embed=em)

    @role.command()
    async def remove(self, ctx: commands.Context, member: typing.Optional[discord.Member], roles: commands.Greedy[RemoveRoleConverter]):
        """Removes `roles` from `memebr`.
        Member can be the command invoker."""
        if member is None:
            member = ctx.author
        toremove = []
        for role in roles:
            for authorrole in member.roles:
                if role.id == authorrole.id:
                    toremove.append(role)
        done = []
        failed = []
        if len(roles) == 0:
            em = discord.Embed(
                color=red, description="Missing roles to remove")
            return await ctx.reply(embed=em)
        elif len(toremove) == 0:
            em = discord.Embed(
                color=red, description=f"{member} doesn't have any of those roles")
            return await ctx.reply(embed=em)
        elif len(toremove) == 1:
            await member.remove_roles(toremove[0], reason=f"Command invoked by {ctx.author} (ID: {ctx.author.id})")
            return await ctx.message.add_reaction("\U0001f44d")
        for role in toremove:
            try:
                await member.remove_roles(role, reason=f"Command invoked by {ctx.author} (ID: {ctx.author.id})")
                done.append(role)
            except discord.Forbidden:
                failed.append(role)
        em = discord.Embed(color=orange)
        em.description = f"Removed {len(done)} roles from {member}"
        if failed:
            em.add_field(name="Failed to remove these roles",
                         value=f"{' '.join([r.mention for r in failed])}\nDue to permissions/hierarchy")
        await ctx.reply(embed=em)


async def setup(bot: botconfig.AndreiBot):
    await bot.add_cog(moderation(bot))
