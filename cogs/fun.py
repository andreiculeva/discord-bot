
import random
import traceback
import discord
from discord.ext import commands, menus
import re
import asyncio
from discord.errors import Forbidden, HTTPException
import datetime
import copy
import typing
import botconfig


allowed_guilds = (749670809110315019, 831556458398089217)


class BadDateFormat(commands.BadArgument):
    """Invalid date format, only dd/mm/year is accepted."""


class DateConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> datetime.date:
        """Accepts a dd/mm/year string and returns a datetime object"""
        args = [k.strip() for k in argument.split("/")]
        if len(args) != 3:  # only accept dd/mm/year
            raise BadDateFormat(
                """Invalid date format, only `dd/mm/year` is accepted.""")
        for k in args:
            if not k.isdigit():
                raise BadDateFormat(
                    """Invalid date format, `day`, `month` and `year` MUST be integers.""")
        day, month, year = args
        day, month, year = int(day), int(month), int(year)
        if month > 12:
            raise BadDateFormat(
                """Invalid date format, there are only 12 months in a year""")
        if day > 31:
            raise BadDateFormat(
                """Invalid date format, no month has more than 31 days""")
        return datetime.date(year=year, month=month, day=day)


rx = re.compile(r'([0-9]{15,20})$')

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


class UrbanDictionaryPageSource(menus.ListPageSource):
    BRACKETED = re.compile(r'(\[(.+?)\])')

    def __init__(self, data):
        super().__init__(entries=data, per_page=1)

    def cleanup_definition(self, definition, *, regex=BRACKETED):
        def repl(m):
            word = m.group(2)
            return f'[{word}](http://{word.replace(" ", "-")}.urbanup.com)'

        ret = regex.sub(repl, definition)
        if len(ret) >= 2048:
            return ret[0:2000] + ' [...]'
        return ret

    async def format_page(self, menu, entry):
        maximum = self.get_max_pages()
        title = f'{entry["word"]}: {menu.current_page + 1} out of {maximum}' if maximum else entry['word']
        embed = discord.Embed(title=title, colour=0xE86222,
                              url=entry['permalink'])
        embed.set_footer(text=f'by {entry["author"]}')
        embed.description = self.cleanup_definition(entry['definition'])

        try:
            up, down = entry['thumbs_up'], entry['thumbs_down']
        except KeyError:
            pass
        else:
            embed.add_field(
                name='Votes', value=f'\N{THUMBS UP SIGN} {up} \N{THUMBS DOWN SIGN} {down}', inline=False)

        try:
            date = discord.utils.parse_time(entry['written_on'][0:-1])
        except (ValueError, KeyError):
            pass
        else:
            embed.timestamp = date

        return embed


class fun(commands.Cog):
    """Useless commands"""
    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='\N{GAME DIE}')

    def __init__(self, bot: botconfig.AndreiBot) -> None:
        super().__init__()
        self.bot = bot

    @commands.command()
    async def urban(self, ctx, *, word):
        """Searches urban dictionary."""

        url = 'http://api.urbandictionary.com/v0/define'

        async with self.bot.session.get(url, params={'term': word}) as resp:
            if resp.status != 200:
                return await ctx.send(f'An error occurred: {resp.status} {resp.reason}')

            js = await resp.json()
            data = js.get('list', [])
            if not data:
                return await ctx.send('No results found, sorry.')

        pages = botconfig.RoboPages(UrbanDictionaryPageSource(data), ctx=ctx)
        await pages.start()

    @commands.command(name="message", aliases=["msg"], hidden=True)
    async def fakemsg(self, ctx: commands.Context, user, *, content):
        if ctx.guild.id not in (749670809110315019, 831556458398089217):
            return
        if not ctx.author.guild_permissions.administrator:
            return
        target = await convert(ctx, user)
        em = discord.Embed(color=orange)
        em.set_author(name=target, icon_url=target.display_avatar.url)
        em.timestamp = ctx.message.created_at
        em.description = content
        await ctx.send(embed=em)

    @commands.command(aliases=["shush", "blacklist"])
    @commands.has_permissions(manage_roles=True)
    async def stfu(self, ctx: commands.Context, member: discord.Member = None):
        """Gives the 'blacklisted' role to `member`.
        `memebr` can be the message reference's author."""
        em = discord.Embed(color=orange)
        if member is None:
            if ctx.message.reference:
                if ctx.message.reference is not None:
                    mreference = ctx.message.reference
                    if mreference.cached_message is not None:
                        member = mreference.cached_message.author
                    else:
                        message = await ctx.channel.fetch_message(mreference.message_id)
                        if message is None:
                            em.description = "I couldn't load that message"
                            return await ctx.reply(embed=em, mention_author=False)
                        member = message.author
                    if not (member in ctx.guild.members):
                        em.description = "That user isn't in the server"
                        return await ctx.reply(embed=em, mention_author=False)
            else:
                emoji = "<:meh:854231053124370482>"
                em = discord.Embed(
                    color=red, description=f"`member` is a required argument that is missing {emoji}")
                return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
        # magic stuff to check message.reference

        role = discord.utils.get(ctx.guild.roles, name="blacklisted")
        if role is None:
            role = await ctx.guild.create_role(name="blacklisted")
        if role in member.roles:
            em.description = f"{member} is already muted"
            return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
        try:
            await member.add_roles(role)
            em.description = f"{member.mention} stfu now"
            return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
        except Forbidden:
            em = discord.Embed(color=red)
            em.description = "I don't have permissions to mute that member"
            return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
        except HTTPException:
            em = discord.Embed(color=red, description="Adding role failed")
            return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(aliases=["unshush", "unblacklist"])
    @commands.has_permissions(manage_roles=True)
    async def unstfu(self, ctx: commands.Context, member: discord.Member):
        """Removes the 'blacklisted' role from `member`"""
        role = discord.utils.get(member.roles, name="blacklisted")
        if role:
            try:
                await member.remove_roles(role)
            except Exception as e:
                em = discord.Embed(color=red, description=e)
                return await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())
        else:
            em = discord.Embed(color=red, description=f"{member} is not muted")
            return await ctx.reply(embed=em)
        em = discord.Embed(color=orange)
        em.description = f"{ctx.author.mention} gave {member.mention} rights to talk but they should still stfu"
        await ctx.reply(embed=em, allowed_mentions=discord.AllowedMentions.none())

    @commands.group(aliases=["bday"], invoke_without_command=True)
    async def birthday(self, ctx: commands.Context,):
        """Shows your own birthday, `help birthday` for subcommands."""
        await ctx.send_help(ctx.command)

    @birthday.command()
    async def set(self, ctx: commands.Context, *, date: DateConverter):
        """You can use this to set your own birthday.
        Allowed date formats: dd/mm/year OR dd/mm"""
        day, month, year = date.day, date.month, date.year
        async with self.bot.db.cursor() as cur:
            await cur.execute("INSERT OR REPLACE INTO birthdays (user, day, month, year) VALUES (?, ?, ?, ?)",
                              (ctx.author.id, day, month, year))
            await self.bot.db.commit()
        dt = datetime.date(year, month, day)
        await ctx.reply(embed=discord.Embed(color=discord.Color.orange(),
                                            description=f"Done, your birthday is `{dt.strftime('%d %B %Y')}`"),
                        allowed_mentions=discord.AllowedMentions.none())

    @birthday.command()
    async def show(self, ctx: commands.Context, user: discord.User = None):
        """You can use this to see `user`'s birthday, if registered."""
        user = user or ctx.author
        async with self.bot.db.cursor() as cur:
            await cur.execute(f"SELECT day, month, year FROM birthdays WHERE user = {user.id}")
            data = await cur.fetchone()
            if not data:
                return await ctx.reply(embed=discord.Embed(color=discord.Color.red(),
                                                           description=f"I don't have {user}'s birthday saved"),
                                       allowed_mentions=discord.AllowedMentions.none())
        day, month, year = data
        dt = datetime.date(year, month, day)
        await ctx.reply(embed=discord.Embed(color=discord.Color.orange(),
                                            description=f"{user}'s birthday: `{dt.strftime('%d %B %Y')}`"),
                        allowed_mentions=discord.AllowedMentions.none())

    @commands.has_guild_permissions(administrator=True)
    @birthday.command(aliases=["add"])
    async def register(self, ctx: commands.Context, user: discord.User, *, date: DateConverter):
        """Can only be used by admins from allowed servers.
        Used to register or update `user`'s birthday.
        `user` doesn't have to be in the server.
        Allowed date formats: dd/mm/year OR dd/mm"""
        if not ctx.guild.id in allowed_guilds:
            return await ctx.send("You can't use this command in this server")
        day, month, year = date.day, date.month, date.year
        async with self.bot.db.cursor() as cur:
            await cur.execute("INSERT OR REPLACE INTO birthdays (user, day, month, year) VALUES (?, ?, ?, ?)",
                              (user.id, day, month, year))
            await self.bot.db.commit()
        dt = datetime.date(year, month, day)
        await ctx.reply(embed=discord.Embed(color=discord.Color.orange(),
                                            description=f"Done, {user}'s birthday is: `{dt.strftime('%d %B %Y')}`"),
                        allowed_mentions=discord.AllowedMentions.none())

    @birthday.command()
    async def update(self, ctx: commands.Context, *, date: DateConverter):
        """You can use this to update your own birthday.
        Allowed date formats: dd/mm/year OR dd/mm"""
        day, month, year = date.day, date.month, date.year
        async with self.bot.db.cursor() as cur:
            await cur.execute("INSERT OR REPLACE INTO birthdays (user, day, month, year) VALUES (?, ?, ?, ?)",
                              (ctx.author.id, day, month, year))
            await self.bot.db.commit()
        dt = datetime.date(year, month, day)
        await ctx.reply(embed=discord.Embed(color=discord.Color.orange(),
                                            description=f"Done, your birthday is: `{dt.strftime('%d %B %Y')}`"),
                        allowed_mentions=discord.AllowedMentions.none())

    @birthday.command(aliases=["unregister"])
    async def remove(self, ctx: commands.Context, user: discord.User = None):
        """You can use this to remove your own birthday.
        Admins from allowed servers can give `user` to remove their birthday."""
        if (user is not None) and (not ctx.guild.id in allowed_guilds):
            return await ctx.send("You can't use this command in this server")
        if (user is not None) and (not ctx.author.guild_permissions.administrator):
            return await ctx.reply(embed=discord.Embed(color=discord.Color.red(),
                                                       description="You can't remove other users' birthdays"),
                                   allowed_mentions=discord.AllowedMentions.none())
        user = user or ctx.author
        async with self.bot.db.cursor() as cur:
            await cur.execute(f"DELETE FROM birthdays WHERE user = {user.id}")
            await self.bot.db.commit()
        await ctx.message.add_reaction("\U0001f44d")

    @commands.command(name="birthdays", aliases=["nb", "nextbirthdays", "bdays"])
    async def nb(self, ctx: commands.Context):
        """Shows coming up birthdays until today of next year"""
        async with self.bot.db.cursor() as cur:
            await cur.execute("SELECT * FROM birthdays")
            comingup = await cur.fetchall()
        dates = {k[0]: datetime.date(
            day=k[1], month=k[2], year=k[3]) for k in comingup}
        dates = {k: v for k, v in sorted(
            dates.items(), key=lambda item: item[1])}
        currentyear = {k: v.replace(year=datetime.date.today().year)
                       for k, v in dates.items()
                       if v.replace(year=datetime.date.today().year) > datetime.date.today()}
        currentyear = {k: v for k, v in sorted(
            currentyear.items(), key=lambda item: item[1])}
        nextyear = {k: v.replace(year=datetime.date.today().year+1)
                    for k, v in dates.items()
                    if v.replace(year=datetime.date.today().year+1) < datetime.date.today().replace(year=datetime.date.today().year+1)}
        nextyear = {k: v for k, v in sorted(
            nextyear.items(), key=lambda item: item[1])}
        newdates = currentyear | nextyear
        entries = []
        for k, v in newdates.items():
            us = ctx.guild.get_member(k)
            if us is None:
                us = self.bot.get_user(k)
                if us is None:
                    try:
                        us = await self.bot.fetch_user(k)
                        toapp = str(us)
                    except discord.NotFound:
                        await ctx.send(f"I couldn't find user with ID {k}")
                        continue
                else:
                    toapp = str(us)
            else:
                toapp = us.mention
            entries.append({"user": toapp, "date": v.strftime(
                '%d %B %Y'), "age": f" turns {v.year-dates[k].year}"})
        pages = botconfig.SimpleBirthdayPages(entries=entries, ctx=ctx)
        await pages.start()

    @birthday.command(aliases=["all"])
    async def list(self, ctx: commands.Context):
        """Shows all registered birthdays in order"""
        async with self.bot.db.cursor() as cur:
            await cur.execute("SELECT * FROM birthdays")
            birthdates = await cur.fetchall()
        dates = {k[0]: datetime.date(
            day=k[1], month=k[2], year=k[3]) for k in birthdates}
        dates = {k: v for k, v in sorted(
            dates.items(), key=lambda item: item[1])}
        currentyear = list({k: v.replace(year=datetime.date.today().year)
                            for k, v in dates.items()
                            if v.replace(year=datetime.date.today().year) > datetime.date.today()}.keys())
        entries = []
        for k, v in dates.items():
            us = self.bot.get_user(k)
            if us is None:
                try:
                    us = await self.bot.fetch_user(k)
                    toapp = str(us)
                except discord.NotFound:
                    await ctx.send(f"I couldn't find user with ID {k}")
            else:
                toapp = us.mention
            entries.append({"user": toapp,
                            "date": v.strftime('%d %B %Y'),
                            "age": f" is {(datetime.date.today().year - v.year)- (1 if k in currentyear else 0)}"},)

        pages = botconfig.SimpleBirthdayPages(
            entries=entries, ctx=ctx, title="All birthdays")
        await pages.start()

    @commands.command()
    async def games(self, ctx: commands.Context):
        """ Start one of the new discord voice chat activities """
        if not ctx.author.voice:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=discord.Embed(color=discord.Color.red(),
                                                      description='You are not connected to a voice channel'))
        view = botconfig.YoutubeDropdown(ctx)
        await view.start()

    @commands.command()
    async def c4(self, ctx: commands.Context, target: discord.Member):
        PLAYER = ctx.message.author
        YES_EMOJI = "✅"
        NO_EMOJI = "❌"
        NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]
        RED = "🔴"
        BLUE = "🔵"
        BLACK = "⚫"
        GREEN = "🟢"

        if (target is None) and (ctx.message.reference is not None):
            player2 = (await ctx.message.channel.fetch_message(ctx.message.reference.message_id)).author
        else:
            player2 = target
            player1 = ctx.message.author
            if player2 == player1:
                await ctx.send("why do you want to play with yourself")
                return
            GAMEBOARD = [[0]*6 for _ in range(7)]
            GAMEBOARD.reverse()
            invite_message = await ctx.send(f"<@{player2.id}> {player1.name} invited you to a c4 game, react to accept")

            await invite_message.add_reaction(YES_EMOJI)
            await invite_message.add_reaction(NO_EMOJI)

            def check(reaction, user):
                if user == player2 and reaction.message == invite_message:
                    if str(reaction.emoji) == YES_EMOJI:
                        return True
                    elif str(reaction.emoji) == NO_EMOJI:
                        return True

            try:
                reaction, user = await self.bot.wait_for("reaction_add", check=check, timeout=60)
            except asyncio.TimeoutError:
                await ctx.send(f"{player2.name} didn't react", delete_after=10)
                await invite_message.delete(delay=10)
                return
            if str(reaction.emoji) == YES_EMOJI:
                await invite_message.delete()
            elif str(reaction.emoji) == NO_EMOJI:
                await ctx.send(f"{player2.name} didn't accept your game", delete_after=10)
                await invite_message.delete(delay=10)
                return

            choices = copy.deepcopy(NUMS)

            def get_board_str(board):
                """takes the board with numbers and returns a string with colored balls"""
                temp_board = copy.deepcopy(board)
                for ls in temp_board:
                    for n, i in enumerate(ls):
                        if i == 0:
                            ls[n] = BLACK
                        elif i == 1:
                            ls[n] = RED
                        elif i == 2:
                            ls[n] = BLUE
                        elif i == 3:
                            ls[n] = GREEN
                return "\n".join(["  ".join([str(temp_board[x][y]) for x in range(7)]) for y in range(6)]) + "\n" + "  ".join(K for K in NUMS)

            def play(choice, turn):
                """changes the value of the column in the board"""
                col = GAMEBOARD[choice]
                i = -1
                while col[i] != 0:
                    i -= 1
                col[i] = turn

            def get_winner(board, turn):
                """checks if there's a winner"""
                for row in range(6):
                    for col in range(4):
                        if board[col][row] == turn and board[col+1][row] == turn and board[col+2][row] == turn and board[col+3][row] == turn:
                            board[col][row] = GREEN
                            board[col+1][row] = GREEN
                            board[col+2][row] = GREEN
                            board[col+3][row] = GREEN
                            return turn
                for col in board:
                    for row in range(3):
                        if col[row] == turn and col[row+1] == turn and col[row+2] == turn and col[row+3] == turn:
                            col[row] = GREEN
                            col[row+1] = GREEN
                            col[row+2] = GREEN
                            col[row+3] = GREEN
                            return turn
                for col in range(4):
                    for i in range(3):
                        if board[col][i] == turn and board[col+1][i+1] == turn and board[col+2][i+2] == turn and board[col+3][i+3] == turn:
                            board[col][i] = GREEN
                            board[col+1][i+1] = GREEN
                            board[col+2][i+2] = GREEN
                            board[col+3][i+3] = GREEN
                            return turn

                for col in range(3, 7):
                    for i in range(3):
                        if board[col][i] == turn and board[col-1][i+1] == turn and board[col-2][i+2] == turn and board[col-3][i+3] == turn:
                            board[col][i] = GREEN
                            board[col-1][i+1] = GREEN
                            board[col-2][i+2] = GREEN
                            board[col-3][i+3] = GREEN
                            return turn

            title = f"CONNECT 4 GAME:\n{player1.name} vs {player2.name}"
            em = discord.Embed(
                title=title, description=get_board_str(GAMEBOARD))

            game_message = await ctx.send(embed=em)

            for emoji in NUMS:
                await game_message.add_reaction(emoji)
            await game_message.add_reaction(NO_EMOJI)

            for i in range(1000):
                if i % 2 == 0:
                    player = player1
                    p2 = player2
                    turn = 1
                    color = RED
                else:
                    player = player2
                    p2 = player1
                    turn = 2
                    color = BLUE

                status = f"{color}  {player}'s turn"
                em.set_footer(text=status)
                await game_message.edit(embed=em)

                def check(reaction, user):
                    if reaction.message == game_message:
                        if (user.guild_permissions.administrator and user != self.bot.user) and str(reaction.emoji) == NO_EMOJI:
                            return True
                        elif reaction.message == game_message and user == player and str(reaction.emoji) in choices:
                            return True
                        elif (user == player1 or user == player2) and str(reaction.emoji) == NO_EMOJI:
                            return True
                        else:
                            return False

                try:
                    reaction, user = await self.bot.wait_for("reaction_add", check=check, timeout=180)
                except asyncio.TimeoutError:
                    try:
                        em.set_footer(
                            text=f"{player.name} didn't react, game ended")
                        await game_message.edit(embed=em)
                        game_msg = await ctx.message.channel.fetch_message(game_message.id)
                        await game_msg.clear_reactions()
                    except:
                        pass
                    return

                if str(reaction.emoji) == NO_EMOJI and user == p2:
                    em.set_footer(text=f"{p2} gave up")
                    await game_message.edit(embed=em)
                    try:
                        game_msg = await ctx.message.channel.fetch_message(game_message.id)
                        await game_msg.clear_reactions()
                    except:
                        pass
                    return

                elif str(reaction.emoji) == NO_EMOJI and ((user != player1 and user != player2 and user != self.bot.user) and user.guild_permissions.administrator):
                    em.set_footer(text=f"game ended by an admin {user}")
                    await game_message.edit(embed=em)
                    try:
                        game_msg = await ctx.message.channel.fetch_message(game_message.id)
                        await game_msg.clear_reactions()
                    except:
                        pass
                    return

                elif str(reaction.emoji) == NO_EMOJI and user == player:
                    em.set_footer(text=f"{player} gave up")
                    await game_message.edit(embed=em)
                    try:
                        game_msg = await ctx.message.channel.fetch_message(game_message.id)
                        await game_msg.clear_reactions()
                    except:
                        pass
                    return

                else:
                    choice = NUMS.index(str(reaction.emoji))

                try:
                    game_msg = await ctx.message.channel.fetch_message(game_message.id)
                except:
                    em = discord.Embed(
                        title=title, description=get_board_str(GAMEBOARD))
                    em.set_footer(text=status)
                    game_message = await ctx.send(embed=em)
                    for n in choices:
                        await game_message.add_reaction(n)

                for r in game_msg.reactions:
                    rusers = [user async for user in r.users()]
                    for u in rusers:
                        if u != self.bot.user:
                            await r.remove(u)

                play(choice, turn)

                desc = get_board_str(GAMEBOARD)

                em = discord.Embed(title=title, description=desc)
                em.set_footer(text=status)
                await game_message.edit(embed=em)

                if GAMEBOARD[choice][0] != 0:
                    await game_msg.remove_reaction(NUMS[choice], self.bot.user)
                    choices.remove(NUMS[choice])

                w = get_winner(GAMEBOARD, turn)
                if w:
                    if w == 1:
                        w = player1
                    elif w == 2:
                        w = player2

                    winning_text = f"{color}  {w} won!"

                    em = discord.Embed(
                        title=title, description=desc)
                    em.set_footer(text=winning_text)

                    await game_message.edit(embed=em)
                    await game_msg.clear_reactions()
                    em = discord.Embed(
                        title=title, description=get_board_str(GAMEBOARD))
                    em.set_footer(text=winning_text)
                    await asyncio.sleep(2)
                    await game_message.edit(embed=em)
                    return

                elif not any(0 in ls for ls in GAMEBOARD):
                    em = discord.Embed(
                        title=title, description=get_board_str(GAMEBOARD))
                    em.set_footer(text="TIE")
                    await game_message.edit(embed=em)
                    await game_msg.clear_reactions()
                    return

    async def chimpleaderboard(self, channel: discord.TextChannel, author: discord.User, bot: botconfig.AndreiBot):
        async with bot.db.cursor() as cursor:
            await cursor.execute("SELECT * FROM chimps")
            data = await cursor.fetchall()
        records: dict[int, tuple[int, int]] = {x[0]: (x[1], x[2]) for x in sorted(
            data, key=lambda k: k[1], reverse=True)}
        embed = discord.Embed(color=discord.Color.orange(),
                              title="Chimp leaderboard")
        embed.set_author(name=str(author), icon_url=author.display_avatar.url)
        s = "\n".join([f"{index+1}. {f'{bot.get_user(x[0])} {x[1][0]} ({x[1][1] if x[1][1] else 0}s)' if x[0]!=author.id else f'**{bot.get_user(x[0])} {x[1][0]} ({x[1][1] if x[1][1] else 0}s)**'}" for index,
                      x in enumerate(records.items())][:10])
        s = s.replace("1.", "\U0001f947").replace(
            "2.", "\U0001f948").replace("3.", "\U0001f949")
        if not (str(author) in s):
            d = records.get(author.id, (0, 0))
            if d:
                s += f"\n\n**{author}**: {d[0]} ({d[1]}s)"
        embed.description = s
        await channel.send(embed=embed)

    @commands.group(invoke_without_command=True)
    async def chimp(self, ctx: commands.Context, amount: int = 5):
        """Play the chimp game"""
        if amount > 25:
            amount = 25
        view = botconfig.ChimpView(amount, author=ctx.author, bot=self.bot)
        view.m = await ctx.send(view=view, content="Memorize the numbers on the grid and tap on the first one to start the game")

    @chimp.command(aliases=["lb"])
    async def leaderboard(self, ctx: commands.Context):
        """Pulls out the leaderboard"""
        await self.chimpleaderboard(ctx.channel, ctx.author, self.bot)

    @commands.Cog.listener("on_raw_reaction_add")
    async def chimp_leaderboard_check(self, payload: discord.RawReactionActionEvent):
        """Pulls out the leaderboard as well"""
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != "\U0001f3c5":
            return
        channel = self.bot.get_channel(payload.channel_id)
        author = payload.member
        message = await channel.fetch_message(payload.message_id)
        if message.author != self.bot.user:
            return
        await self.chimpleaderboard(channel, author, self.bot)

    @commands.command()
    async def suggest(self, ctx:commands.Context[commands.Bot], *, suggestion:str):
        """This command can be used to suggest new bot features or edits to the existing ones"""
        suggestions = ctx.bot.get_channel(999321557476311090)
        embed = discord.Embed(color=discord.Color.orange(), description=suggestion)
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"ID: {ctx.author.id}")
        await suggestions.send(embed=embed)
        await ctx.message.add_reaction("\U0001f44d")

    @commands.command()
    async def slidepuzzle(self, ctx: commands.Context, number: int = 3):
        """Credit to z03h#6375"""
        return await ctx.reply("I'm still making this game")
        if number < 2:
            number = 2
        if number > 5:
            number = 5
        await ctx.send(view=SlidePuzzle(ctx.author, number))


class SlidePuzzleButton(discord.ui.Button):
    def __init__(self, x: int, y: int, value: int = 0):
        super().__init__(style=discord.ButtonStyle.gray)
        self.value = value
        self.x = x
        self.y = y
        self.label = str(self.value) if self.value else " "
        self.row = y-1
        self.view: SlidePuzzle
    
    def new_move(self):
        for children in self.view.children:
            if children.value == 0:
                if children.x == self.x-1 and children.y == self.y:  # case on the left
                    return children
                elif children.x == self.x+1 and children.y == self.y:  # case on the right
                    return children
                elif children.x == self.x and children.y == self.y-1:  # case under it
                    return children
                elif children.x == self.x and children.y == self.y + 1:  # case above it
                    return children
        return None

    async def callback(self, interaction: discord.Interaction):
        move = self.new_move()
        if not move:
            return await interaction.response.defer()
        temp = (move.x, move.y)
        move.x, move.y = self.x, self.y
        self.x, self.y = temp
        
        await interaction.response.edit_message(content=f"{self.x=} {self.y=}",view=self.view)


class SlidePuzzle(discord.ui.View):
    def __init__(self, author: discord.Member, number: int = 3, *, timeout: typing.Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.author = author
        self.size: typing.Literal[2, 3, 4, 5] = number
        self.coordinates :dict[tuple[int, int], SlidePuzzleButton]= {}
        for x in range(1, self.size+1):
            for y in range(1, self.size+1):
                button = SlidePuzzleButton(x, y)
                self.add_item(button)
                self.coordinates[(x, y)] = button
        n = self.children.copy()
        random.shuffle(n)
        for number in range(1, (self.size*self.size)):
            button = n[number-1]
            button.value = number
            button.label = str(button.value) if button.value else " "
            button.disabled = not button.value

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author == interaction.user:
            return True
        await interaction.response.send_message(f"This game is for {self.author} (ID: {self.author.id})", ephemeral=True)


async def setup(bot: botconfig.AndreiBot):
    await bot.add_cog(fun(bot))
