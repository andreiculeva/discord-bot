import re
import asqlite
import discord
from discord.ext import commands, menus
from typing import Any, Optional, Dict, List, Union
import aiohttp
import os
import datetime
import asyncio
import inspect
import itertools
import contextlib
import random
import io
import pytube
import typing
import time

default_prefix = "."

ANDREI_ID = 393033826474917889
SHAWN_ID = 385690978696167424
ANDREI2_ID = 605398335691554827
CUBE_ID = 318726272731709441
SNOWY_ID = 492280759348887572

class AvatarConfirmationView(discord.ui.View):
    def __init__(self, *, timeout: Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.value = False

    @discord.ui.button(label="yes", style=discord.ButtonStyle.green)
    async def yes(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        self.value = True
        self.stop()

    @discord.ui.button(label="no", style=discord.ButtonStyle.red)
    async def no(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        await interaction.delete_original_message()
        self.value = False
        self.stop()


class ConfigView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot: AndreiBot = bot
        self._select.options.clear()
        for name, cog in self.bot.cogs.items():
            self._select.append_option(discord.SelectOption(
                label=str(name), value=str(name), description=cog.description, emoji=getattr(cog, "display_emoji", None)
            ))
        

    @discord.ui.select(max_values=1, custom_id="cogselect")
    async def _select(self, interaction: discord.Interaction, select: discord.ui.Select):
        select.options.clear()
        for name, cog in self.bot.cogs.items():
            self._select.append_option(discord.SelectOption(
                label=str(name),
                value=str(name),
                description=cog.description,
                emoji=getattr(cog, "display_emoji", None)
            ))
        await self.bot.reload_extension(f"cogs.{select._selected_values[0]}")
        await interaction.response.edit_message(content=f"Reloaded {select._selected_values[0]}", view=self)

    @discord.ui.button(label="Reload cogs", custom_id="reloadcogs")
    async def reloadcogs(self, interaction: discord.Interaction, _):
        start = time.perf_counter()
        await interaction.response.defer()
        if not interaction.user.id in interaction.client.owner_ids:
            return
        cogs = [cog for cog in interaction.client.cogs.keys()]
        for cog in cogs:
            if cog in ("Jishaku"):
                continue
            await interaction.client.unload_extension(f"cogs.{cog}")
        reloaded = []
        for cog in os.listdir("cogs"):
            if not cog.endswith(".py"):
                continue
            if cog in (None,):  # add blacklisted cogs? idfk
                continue
            await interaction.client.load_extension(f"cogs.{cog[:-3]}")
            reloaded.append(cog[:-3])
        self._select.options.clear()
        for name, cog in self.bot.cogs.items():
            self._select.append_option(discord.SelectOption(label=str(name), value=str(name), description=cog.description, emoji=getattr(cog, "display_emoji", None)))
        await interaction.edit_original_message(content=f"Reloaded {', '.join(reloaded)} in {time.perf_counter() - start:.2f}s", view=self)

    @discord.ui.button(label="Restart", custom_id="restart:pi")
    async def __restart(self, interaction: discord.Interaction, _):
        if not interaction.user.id in interaction.client.owner_ids:
            return
        await interaction.response.edit_message(content="Restarting...")
        os.system("sudo reboot")

    @discord.ui.button(label="sync", custom_id="sync:commands")
    async def __sync(self, interaction: discord.Interaction, _):
        commands = await interaction.client.tree.sync()
        await interaction.response.edit_message(content=f"synced {len(commands)} commands globally")


class RoboPages(discord.ui.View):
    def __init__(
        self,
        source: menus.PageSource,
        *,
        ctx: commands.Context,
        check_embeds: bool = True,
        compact: bool = False,
    ):
        super().__init__()
        self.source: menus.PageSource = source
        self.check_embeds: bool = check_embeds
        self.ctx: commands.Context = ctx
        self.message: Optional[discord.Message] = None
        self.current_page: int = 0
        self.compact: bool = compact
        self.input_lock = asyncio.Lock()
        self.clear_items()
        self.fill_items()
        self.timeout = None

    def fill_items(self) -> None:
        if not self.compact:
            self.numbered_page.row = 1
            self.stop_pages.row = 1

        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)  # type: ignore
            self.add_item(self.go_to_previous_page)  # type: ignore
            if not self.compact:
                self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            if use_last_and_first:
                self.add_item(self.go_to_last_page)  # type: ignore
            if not self.compact:
                self.add_item(self.numbered_page)  # type: ignore
            self.add_item(self.stop_pages)  # type: ignore

    async def _get_kwargs_from_page(self, page: int) -> Dict[str, Any]:
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {'content': value, 'embed': None}
        elif isinstance(value, discord.Embed):
            return {'embed': value, 'content': None}
        else:
            return {}

    async def show_page(self, interaction: discord.Interaction, page_number: int) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_number)
        if kwargs:
            if interaction.response.is_done():
                if self.message:
                    await self.message.edit(**kwargs, view=self)
            else:
                await interaction.response.edit_message(**kwargs, view=self)

    def _update_labels(self, page_number: int) -> None:
        self.go_to_first_page.disabled = page_number == 0
        if self.compact:
            max_pages = self.source.get_max_pages()
            self.go_to_last_page.disabled = max_pages is None or (
                page_number + 1) >= max_pages
            self.go_to_next_page.disabled = max_pages is not None and (
                page_number + 1) >= max_pages
            self.go_to_previous_page.disabled = page_number == 0
            return

        self.go_to_current_page.label = str(page_number + 1)
        self.go_to_previous_page.label = str(page_number)
        self.go_to_next_page.label = str(page_number + 2)
        self.go_to_next_page.disabled = False
        self.go_to_previous_page.disabled = False
        self.go_to_first_page.disabled = False

        max_pages = self.source.get_max_pages()
        if max_pages is not None:
            self.go_to_last_page.disabled = (page_number + 1) >= max_pages
            if (page_number + 1) >= max_pages:
                self.go_to_next_page.disabled = True
                self.go_to_next_page.label = '…'
            if page_number == 0:
                self.go_to_previous_page.disabled = True
                self.go_to_previous_page.label = '…'

    async def show_checked_page(self, interaction: discord.Interaction, page_number: int) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(interaction, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.ctx.author:
            return True
        elif interaction.user == self.ctx.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message("This button isn't for you", ephemeral=True)

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            await interaction.followup.send('An unknown error occurred, sorry', ephemeral=True)
        else:
            await interaction.response.send_message('An unknown error occurred, sorry', ephemeral=True)

    async def start(self) -> None:
        if self.check_embeds and not self.ctx.channel.permissions_for(self.ctx.me).embed_links:
            await self.ctx.send('Bot does not have embed links permission in this channel.')
            return

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        self.message = await self.ctx.send(**kwargs, view=self)

    @discord.ui.button(label='≪', style=discord.ButtonStyle.grey)
    async def go_to_first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the first page"""
        await self.show_page(interaction, 0)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.blurple)
    async def go_to_previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the previous page"""
        await self.show_checked_page(interaction, self.current_page - 1)

    @discord.ui.button(label='Current', style=discord.ButtonStyle.grey, disabled=True)
    async def go_to_current_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label='Next', style=discord.ButtonStyle.blurple)
    async def go_to_next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the next page"""
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button(label='≫', style=discord.ButtonStyle.grey)
    async def go_to_last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(interaction, self.source.get_max_pages() - 1)

    @discord.ui.button(label='Skip to page...', style=discord.ButtonStyle.grey)
    async def numbered_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """lets you type a page number to go to"""
        modal = PageModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        page = modal.page.value
        if page is None:
            return await interaction.response.defer(ephemeral=True)
        page = int(modal.page.value)-1
        await self.show_checked_page(interaction, page)

    @discord.ui.button(label='Quit', style=discord.ButtonStyle.red)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button):
        """stops the pagination session."""
        await interaction.response.defer()
        await interaction.delete_original_message()
        self.stop()


class HelpMenu(RoboPages):
    def __init__(self, source: menus.PageSource, ctx: commands.Context):
        super().__init__(source, ctx=ctx, compact=True)

    def add_categories(self, commands: Dict[commands.Cog, List[commands.Command]]) -> None:
        self.clear_items()
        self.add_item(HelpSelectMenu(commands, self.ctx.bot))
        self.fill_items()

    async def rebind(self, source: menus.PageSource, interaction: discord.Interaction) -> None:
        self.source = source
        self.current_page = 0

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        await interaction.response.edit_message(**kwargs, view=self)


class FrontPageSource(menus.PageSource):
    def is_paginating(self) -> bool:
        # This forces the buttons to appear even in the front page
        return True

    def get_max_pages(self) -> Optional[int]:
        # There's only one actual page in the front page
        # However we need at least 2 to show all the buttons
        return 2

    async def get_page(self, page_number: int) -> Any:
        # The front page is a dummy
        self.index = page_number
        return self

    def format_page(self, menu: HelpMenu, page):
        embed = discord.Embed(title='Bot Help', colour=discord.Color.orange())
        embed.description = inspect.cleandoc(
            f"""
            Hello! Welcome to the help page.
            Use "{menu.ctx.clean_prefix}help command" for more info on a command.
            Use "{menu.ctx.clean_prefix}help category" for more info on a category.
            Use the dropdown menu below to select a category.
            My [source code](https://github.com/andreiculeva/discord-bot) is public.
            You can join the [testing server](https://discord.gg/W9KHWZkHA8).
        """
        )

        entries = (
            ('<argument>', 'This means the argument is __**required**__.'),
            ('[argument]', 'This means the argument is __**optional**__.'),
            ('[A|B]', 'This means that it can be __**either A or B**__.'),
            (
                '[argument...]',
                'This means you can have multiple arguments.\n'
            ),
        )

        for name, value in entries:
            embed.add_field(name=name, value=value, inline=False)

        return embed


class HelpSelectMenu(discord.ui.Select['HelpMenu']):
    def __init__(self, commands: Dict[commands.Cog, List[commands.Command]], bot: commands.AutoShardedBot):
        super().__init__(
            placeholder='Select a category...',
            min_values=1,
            max_values=1,
            row=0,
        )
        self.commands = commands
        self.bot = bot
        self.__fill_options()

    def __fill_options(self) -> None:
        self.add_option(
            label='Index',
            emoji='\N{WAVING HAND SIGN}',
            value='__index',
            description='The help page showing how to use the bot.',
        )
        for cog, commands in self.commands.items():
            if not commands:
                continue
            description = cog.description.split('\n', 1)[0] or None
            emoji = getattr(cog, 'display_emoji', None)
            self.add_option(label=cog.qualified_name, value=cog.qualified_name,
                            description=description, emoji=emoji)

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        value = self.values[0]
        if value == '__index':
            await self.view.rebind(FrontPageSource(), interaction)
        else:
            cog = self.bot.get_cog(value)
            if cog is None:
                await interaction.response.send_message('Somehow this category does not exist?', ephemeral=True)
                return

            commands = self.commands[cog]
            if not commands:
                await interaction.response.send_message('This category has no commands for you', ephemeral=True)
                return

            source = GroupHelpPageSource(
                cog, commands, prefix=self.view.ctx.clean_prefix)
            await self.view.rebind(source, interaction)


class PageModal(discord.ui.Modal, title="Select a page"):
    page = discord.ui.TextInput(
        label="page",
        style=discord.TextStyle.short,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not self.page.value.isdigit():
            await interaction.response.send_message(f"{self.page.value} is not a valid number", ephemeral=True)
            self.page.value = None
            self.stop()

        await interaction.response.defer()
        self.stop()


class AndreiBot(commands.Bot):
    def __init__(self,  **options: Any) -> None:
        super().__init__(command_prefix=get_prefix,
                         help_command=PaginatedHelpCommand(),
                         intents=discord.Intents.all(),
                         case_insensitive=True,
                         status=discord.Status.dnd,
                         owner_ids=(ANDREI_ID, SHAWN_ID, CUBE_ID, ANDREI2_ID, SNOWY_ID), **options)
        self.log_channel_id = int(os.getenv("log_channel_id"))
        self.deleted_files = {}  # message_id : (filebytes, filename)
        self.case_insensitive = True
        self.birthdayusers: list[discord.User] = []
        self._connection.max_messages = 100000
        self.launch_time = discord.utils.utcnow()
    
    

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        self.db = await asqlite.connect("/home/pi/betabot/database.db")
        async with self.db.cursor() as cursor:
            await cursor.execute("CREATE TABLE IF NOT EXISTS avatars (user INT, avatar TEXT, date INT, url TEXT, server INT)")
            await cursor.execute("CREATE TABLE IF NOT EXISTS birthdays (user INTEGER, day INTEGER, month INTEGER, year INTEGER DEFAULT 0)")
            await cursor.execute("CREATE TABLE IF NOT EXISTS edits (server INTEGER, channel INTEGER, message INTEGER, content TEXT, timestamp TEXT, author INTEGER)")
            await cursor.execute("CREATE TABLE IF NOT EXISTS invites (server INTEGER, channel INTEGER)")
            await cursor.execute("CREATE TABLE IF NOT EXISTS messages (server INTEGER, channel INTEGER, message INTEGER, author INTEGER, timestamp TEXT, content TEXT)")
            await cursor.execute("CREATE TABLE IF NOT EXISTS servers (id INTEGER, prefix TEXT)")
            await cursor.execute("CREATE TABLE IF NOT EXISTS stars (original_message_id INT, star_id INT)")
            await cursor.execute("CREATE TABLE IF NOT EXISTS chimps (user INT, score INT)")
            await self.db.commit()

        self.add_view(ConfigView(self))
        await self.load_extension("jishaku")
        for cog in os.listdir("cogs"):
            if not cog.endswith(".py"):
                continue
            if cog in (None,):  # add blacklisted cogs? idfk
                continue
            await self.load_extension(f"cogs.{cog[:-3]}")
            print(f"Loaded {cog}")

    async def on_ready(self):
        print(f"{self.user} online")
        await asyncio.sleep(1)
        mes = await self.get_channel(982282223166304277).fetch_message(990226576413179934)
        t = mes.edited_at
        dt = discord.utils.utcnow() - t
        hours, remainder = divmod(dt.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        await mes.edit(content=f"online: <t:{int(datetime.datetime.now().timestamp())}:F>\ntime taken:{'' if not hours else f'{hours}h,'} {minutes}m, {int(seconds)}s")


class GroupHelpPageSource(menus.ListPageSource):
    def __init__(self, group: Union[commands.Group, commands.Cog], commands: List[commands.Command], *, prefix: str):
        super().__init__(entries=commands, per_page=6)
        self.group = group
        self.prefix = prefix
        self.title = f'{self.group.qualified_name} Commands'
        self.description = self.group.description

    async def format_page(self, menu, commands):
        embed = discord.Embed(
            title=self.title, description=self.description, colour=discord.Colour.orange())

        for command in commands:
            signature = f'{command.qualified_name} {command.signature}'
            embed.add_field(
                name=signature, value=command.short_doc or 'No help given...', inline=False)

        maximum = self.get_max_pages()
        if maximum > 1:
            embed.set_author(
                name=f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} commands)')

        embed.set_footer(
            text=f'Use "{self.prefix}help command" for more info on a command.')
        return embed


class PaginatedHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(
            command_attrs={
                'cooldown': commands.CooldownMapping.from_cooldown(1, 3.0, commands.BucketType.member),
                'help': 'Shows help about the bot, a command, or a category',
            }
        )

    async def on_help_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            # Ignore missing permission errors
            if isinstance(error.original, discord.HTTPException) and error.original.code == 50013:
                return

            await ctx.send(str(error.original))

    def get_command_signature(self, command):
        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = '|'.join(command.aliases)
            fmt = f'[{command.name}|{aliases}]'
            if parent:
                fmt = f'{parent} {fmt}'
            alias = fmt
        else:
            alias = command.name if not parent else f'{parent} {command.name}'
        return f'{alias} {command.signature}'

    async def send_bot_help(self, mapping):
        bot = self.context.bot

        def key(command) -> str:
            cog = command.cog
            return cog.qualified_name if cog else '\U0010ffff'

        entries: List[commands.Command] = await self.filter_commands(bot.commands, sort=True, key=key)

        all_commands: Dict[commands.Cog, List[commands.Command]] = {}
        for name, children in itertools.groupby(entries, key=key):
            if name == '\U0010ffff':
                continue

            cog = bot.get_cog(name)
            all_commands[cog] = sorted(
                children, key=lambda c: c.qualified_name)

        menu = HelpMenu(FrontPageSource(), ctx=self.context)
        menu.add_categories(all_commands)
        await menu.start()

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        menu = HelpMenu(GroupHelpPageSource(
            cog, entries, prefix=self.context.clean_prefix), ctx=self.context)
        await menu.start()

    def common_command_formatting(self, embed_like, command):
        embed_like.title = self.get_command_signature(command)
        if command.description:
            embed_like.description = f'{command.description}\n\n{command.help}'
        else:
            embed_like.description = command.help or 'No help found...'

    async def send_command_help(self, command):
        # No pagination necessary for a single command.
        embed = discord.Embed(colour=discord.Colour.orange())
        self.common_command_formatting(embed, command)
        await self.context.send(embed=embed)

    async def send_group_help(self, group):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        if len(entries) == 0:
            return await self.send_command_help(group)

        source = GroupHelpPageSource(
            group, entries, prefix=self.context.clean_prefix)
        self.common_command_formatting(source, group)
        menu = HelpMenu(source, ctx=self.context)
        await menu.start()


async def get_prefix(bot: AndreiBot, message: discord.Message):
    # return "="
    p = [f"<@!{bot.user.id}> ", f"<@{bot.user.id}> ", f"<@!{bot.user.id}>",
         f"<@{bot.user.id}>"]  # note the space at the end
    if message.guild:
        async with bot.db.cursor() as cur:
            await cur.execute("SELECT prefix FROM servers WHERE id = ?", (message.guild.id,))
            guild_prefix = await cur.fetchone()
            if guild_prefix:
                p.append(guild_prefix[0])
            else:
                p.append(default_prefix)
    else:
        p.append(default_prefix)
        p += ["", " "]
    return p


DONE = [
    '<:done:912190157942308884>',
    '<:done:912190217102970941>',
    '<a:done:912190284698361876>',
    '<a:done:912190377757376532>',
    '<:done:912190445289877504>',
    '<a:done:912190496791728148>',
    '<a:done:912190546192265276>',
    '<a:done:912190649493749811>',
    '<:done:912190753084694558>',
    '<:done:912190821321814046>',
    '<a:done:912190898241167370>',
    '<a:done:912190952200871957>',
    '<a:done:912191063589027880>',
    '<a:done:912191153326145586>',
    '<:done:912191209919897700>',
    '<:done:912191260356407356>',
    '<a:done:912191386575577119>',
    '<:done:912191480351825920>',
    '<:done:912191682534047825>',
    '<a:done:912192596305129522>',
    '<a:done:912192718212583464>',
]


class YoutubeDropdown(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__()
        self.ctx = ctx
        self.message: discord.Message = None  # type: ignore

    @discord.ui.select(placeholder='Select an activity type...', options=[
        discord.SelectOption(label='Cancel', value='cancel', emoji='❌'),
        discord.SelectOption(label='Youtube', value='youtube',
                             emoji='<:youtube:898052487989309460>'),
        discord.SelectOption(label='Poker', value='poker',
                             emoji='<:poker_cards:917645571274195004>'),
        discord.SelectOption(label='Betrayal', value='betrayal',
                             emoji='<:betrayal:917647390717141072>'),
        discord.SelectOption(label='Fishing', value='fishing', emoji='🎣'),
        discord.SelectOption(label='Chess', value='chess',
                             emoji='\U0000265f\U0000fe0f'),
        discord.SelectOption(label='Letter Tile', value='letter-tile',
                             emoji='<:letterTile:917647925927084032>'),
        discord.SelectOption(label='Word Snacks', value='word-snack',
                             emoji='<:wordSnacks:917648019342655488>'),
        discord.SelectOption(
            label='Doodle Crew', value='doodle-crew', emoji='<:doodle:917648115656437810>'),
        discord.SelectOption(label='Spellcast', value='spellcast', emoji='📜'),
        discord.SelectOption(label='Awkword', value='awkword',
                             emoji='<a:typing:895397923687399517>'),
        discord.SelectOption(label='Checkers', value='checkers', emoji='🏁'),
        discord.SelectOption(label='Cancel', value='cancel2', emoji='❌'),
    ])
    async def activity_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        member = interaction.user
        if not member.voice:
            await interaction.response.edit_message(embed=discord.Embed(color=discord.Color.red(),
                                                                        description='You are not connected to a voice channel'),
                                                    view=None)
            return self.stop()
        if 'cancel' in select.values[0]:
            self.stop()
            with contextlib.suppress(discord.HTTPException):
                await interaction.message.delete()
                await self.ctx.message.add_reaction(random.choice(DONE))
            return
        try:
            link = await create_link(self.ctx.bot, member.voice.channel, select.values[0])
        except Exception as e:
            self.stop()
            self.ctx.bot.dispatch('command_error', self.ctx, e)
            with contextlib.suppress(discord.HTTPException):
                await self.message.delete()
            return
        em = discord.Embed(color=discord.Color.orange(),
                           title=select.values[0].capitalize())
        em.description = f'Click the link to start your activity\n<{link}>'
        em.set_footer(text="activities don't work on mobile")

        await interaction.response.edit_message(content=None, view=None, embed=em)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.ctx.author:
            return True
        elif interaction.user == self.ctx.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message("This button isn't for you", ephemeral=True)

    async def start(self):
        await self.ctx.reply(view=self, mention_author=False)

    async def on_timeout(self) -> None:
        with contextlib.suppress(discord.HTTPException):
            await self.message.delete()
            await self.ctx.message.add_reaction(random.choice(DONE))


async def create_link(bot: commands.Bot, vc: discord.VoiceChannel, option: str) -> str:
    """
    Generates an invite link to a VC with the Discord Party VC Feature.
    Parameters
    ----------
    bot: :class: commands.Bot
        the bot instance. It must have a :attr:`session` attribute (a :class:`aiohttp.ClientSession`)
    vc: :class: discord.VoiceChannel
        the voice channel to create the invite link for
    option: str
        the event type to create the invite link for
    Returns
    ----------
    :class:`str`
        Contains the discord invite link which, upon clicked, starts the custom activity in the VC.
    """

    if not vc.permissions_for(vc.guild.me).create_instant_invite:
        raise commands.BotMissingPermissions(['CREATE_INSTANT_INVITE'])

    data = {
        'max_age': 0,
        'max_uses': 0,
        'target_application_id': event_types.get(option),
        'target_type': 2,
        'temporary': False,
        'validate': None
    }
    session = bot.session

    async with session.post(f"https://discord.com/api/v8/channels/{vc.id}/invites",
                            json=data, headers={'Authorization': f'Bot {bot.http.token}',
                                                'Content-Type': 'application/json'}) as resp:
        resp_code = resp.status
        result = await resp.json()

    if resp_code == 429:
        raise commands.BadArgument('You are being rate-limited.'
                                   f'\nTry again in {result.get("X-RateLimit-Reset-After")}s')
    elif resp_code == 401:
        raise commands.BadArgument('Unauthorized')
    elif result['code'] == 10003 or (result['code'] == 50035 and 'channel_id' in result['errors']):
        raise commands.BadArgument(
            'For some reason, that voice channel is not valid...')
    elif result['code'] == 50013:
        raise commands.BotMissingPermissions(['CREATE_INSTANT_INVITE'])
    elif result['code'] == 130000:
        raise commands.BadArgument(
            'The api is currently overloaded... Try later maybe?')

    return f"https://discord.gg/{result['code']}"

event_types = {
    'youtube': '880218394199220334',
    'poker': '755827207812677713',
    'betrayal': '773336526917861400',
    'fishing': '814288819477020702',
    'chess': '832012774040141894',
    'letter-tile': '879863686565621790',
    'word-snack': '879863976006127627',
    'doodle-crew': '878067389634314250',
    'spellcast': '852509694341283871',
    'awkword': '879863881349087252',
    'checkers': '832013003968348200',
}


class SimpleBirthdayPageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        menu.embed.clear_fields()
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            menu.embed.add_field(name=str(entry["date"]),
                                 value=(
                                     f"{entry['user']}"+(entry["age"] if entry["age"] else "")),
                                 inline=False)
            #menu.embed.add_field(name=str(entry["date"]), value=f"{entry['user']} turns {entry['age']}", inline=False)

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)'
            menu.embed.set_footer(text=footer)

        return menu.embed


class SimpleBirthdayPages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(self, entries, *, ctx: commands.Context, per_page: int = 6, title="Coming up birthdays"):
        super().__init__(SimpleBirthdayPageSource(entries, per_page=per_page), ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.orange(), title=title)


class EmojiView(discord.ui.View):
    def __init__(self, emoji: discord.PartialEmoji, *, timeout: Optional[float] = 180):
        super().__init__(timeout=None)
        self.emoji = emoji

    @discord.ui.button(label="send file")
    async def _upload_emoji(self, _, interaction: discord.Interaction):
        await interaction.response.defer()
        emoji_file = await self.emoji.read()
        emoji_file = io.BytesIO(emoji_file)
        name = self.emoji.name
        if self.emoji.animated:
            name += ".gif"
        else:
            name += ".png"
        await interaction.channel.send(content=f"{interaction.user} requested file", file=discord.File(emoji_file, filename=name))


class DeletedView(discord.ui.View):
    def __init__(self, bot: AndreiBot, ctx: commands.Context, message_id: int, author: discord.User, *, timeout: typing.Optional[float] = 180):
        super().__init__(timeout=None)
        self.bot = bot
        self.ctx = ctx
        self.message_id = message_id
        self.author = author
        self.file = self.bot.deleted_files.get(message_id)
        if self.file is None:
            self.remove_item(self._snipefile)

    @discord.ui.button(label="delete message", style=discord.ButtonStyle.red)
    async def _delete_message(self, interaction: discord.Interaction, button: discord.Button):
        if not ((interaction.user == self.author) or interaction.channel.permissions_for(interaction.user).manage_messages):
            return await interaction.response.send_message("You need to either be the author of that message or have manage messages permissions in this channel to do that", ephemeral=True)
        async with self.bot.db.cursor() as cur:
            await cur.execute(f"DELETE FROM messages WHERE message = {self.message_id}")
            await self.bot.db.commit()
        await interaction.response.defer()
        await interaction.delete_original_message()

    @discord.ui.button(label="snipe file")
    async def _snipefile(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message(f"You need the `manage messages` permission to snipe files", ephemeral=True)
        filetuple = self.bot.deleted_files.get(self.message_id)
        if filetuple is None:
            return await interaction.response.send_message(f"I don't have that file saved anymore (I delete them after 1 hour)", ephemeral=True)
        await interaction.response.defer(ephemeral=self.hidden)
        try:
            await interaction.followup.send(file=discord.File(io.BytesIO(filetuple[0]), filename=filetuple[1]), content=f"Requested by {interaction.user}")
        except (discord.HTTPException, discord.Forbidden, ValueError, TypeError):
            await interaction.followup.send(content="I couldn't upload that file")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.ctx.author:
            return True
        elif interaction.user == self.ctx.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message("This button isn't for you", ephemeral=True)


class ConfirmationView(discord.ui.View):
    def __init__(self, *, ctx: commands.Context, timeout: Optional[float] = 180):
        super().__init__(timeout=None)
        self.value = None
        self.ctx = ctx

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.defer()
        await interaction.delete_original_message()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        await interaction.delete_original_message()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.ctx.author:
            return True
        elif interaction.user == self.ctx.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message("This button isn't for you", ephemeral=True)


class TimeConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str):
        """This converter returns the time in seconds"""
        time_regex = re.compile(r"(\d{1,5}(?:[.,]?\d{1,5})?)([smhdw])")
        time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400, "w": 604800}
        matches = time_regex.findall(argument.lower())
        if not matches:
            raise commands.BadArgument("Invalid time given")
        time = 0
        for v, k in matches:
            try:
                time += time_dict[k]*float(v)
            except KeyError:
                raise commands.BadArgument(
                    "{} is an invalid time-key! h/m/s/d are valid!".format(k))
            except ValueError:
                raise commands.BadArgument("{} is not a number!".format(v))
        return time


class InteractionRoboPages(discord.ui.View):
    def __init__(
        self,
        source: menus.PageSource,
        *,
        interaction: discord.Interaction,
        check_embeds: bool = True,
        compact: bool = False,
        hidden: bool = False
    ):
        super().__init__()
        self.source: menus.PageSource = source
        self.check_embeds: bool = check_embeds
        self.interaction: discord.Interaction = interaction
        self.message: Optional[discord.Message] = None
        self.current_page: int = 0
        self.compact: bool = compact
        self.clear_items()
        self.fill_items()
        self.timeout = None
        self.hidden: bool = hidden

    def fill_items(self) -> None:
        if not self.compact:
            self.numbered_page.row = 1
            self.stop_pages.row = 1

        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)  # type: ignore
            self.add_item(self.go_to_previous_page)  # type: ignore
            if not self.compact:
                self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            if use_last_and_first:
                self.add_item(self.go_to_last_page)  # type: ignore
            if not self.compact:
                self.add_item(self.numbered_page)  # type: ignore
            self.add_item(self.stop_pages)  # type: ignore

    async def _get_kwargs_from_page(self, page: int) -> Dict[str, Any]:
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {'content': value, 'embed': None}
        elif isinstance(value, discord.Embed):
            return {'embed': value, 'content': None}
        else:
            return {}

    async def show_page(self, interaction: discord.Interaction, page_number: int) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_number)
        if kwargs:
            if interaction.response.is_done():
                await interaction.edit_original_message(**kwargs, view=self)
            else:
                await interaction.response.edit_message(**kwargs, view=self)
        else:
            if interaction.response.is_done():
                await interaction.edit_original_message(view=self)
            else:
                await interaction.response.edit_message(view=self)

    def _update_labels(self, page_number: int) -> None:
        self.go_to_first_page.disabled = page_number == 0
        if self.compact:
            max_pages = self.source.get_max_pages()
            self.go_to_last_page.disabled = max_pages is None or (
                page_number + 1) >= max_pages
            self.go_to_next_page.disabled = max_pages is not None and (
                page_number + 1) >= max_pages
            self.go_to_previous_page.disabled = page_number == 0
            return

        self.go_to_current_page.label = str(page_number + 1)
        self.go_to_previous_page.label = str(page_number)
        self.go_to_next_page.label = str(page_number + 2)
        self.go_to_next_page.disabled = False
        self.go_to_previous_page.disabled = False
        self.go_to_first_page.disabled = False

        max_pages = self.source.get_max_pages()
        if max_pages is not None:
            self.go_to_last_page.disabled = (page_number + 1) >= max_pages
            if (page_number + 1) >= max_pages:
                self.go_to_next_page.disabled = True
                self.go_to_next_page.label = '…'
            if page_number == 0:
                self.go_to_previous_page.disabled = True
                self.go_to_previous_page.label = '…'

    async def show_checked_page(self, interaction: discord.Interaction, page_number: int) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(interaction, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        elif interaction.user == interaction.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message("This button isn't for you", ephemeral=True)

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)
        elif self.interaction:
            await self.interaction.edit_original_message(view=None)

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            await interaction.followup.send('An unknown error occurred, sorry', ephemeral=True)
        else:
            await interaction.response.send_message('An unknown error occurred, sorry', ephemeral=True)

    async def start(self) -> None:
        if self.check_embeds and not self.interaction.channel.permissions_for(self.interaction.guild.me).embed_links:
            await self.interaction.response.send_message('Bot does not have embed links permission in this channel.', ephemeral=True)
            return

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        await self.interaction.response.send_message(ephemeral=self.hidden, view=self, **kwargs)
        self.message = await self.interaction.original_message()

    @discord.ui.button(label='≪', style=discord.ButtonStyle.grey)
    async def go_to_first_page(self,  interaction: discord.Interaction, button: discord.ui.Button):
        """go to the first page"""
        await self.show_page(interaction, 0)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.blurple)
    async def go_to_previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the previous page"""
        await self.show_checked_page(interaction, self.current_page - 1)

    @discord.ui.button(label='Current', style=discord.ButtonStyle.grey, disabled=True)
    async def go_to_current_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label='Next', style=discord.ButtonStyle.blurple)
    async def go_to_next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the next page"""
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button(label='≫', style=discord.ButtonStyle.grey)
    async def go_to_last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(interaction, self.source.get_max_pages() - 1)

    @discord.ui.button(label='Skip to page...', style=discord.ButtonStyle.grey)
    async def numbered_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """lets you type a page number to go to"""
        modal = PageModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        page = modal.page.value
        if page is None:
            return await interaction.response.defer(ephemeral=True)
        page = int(modal.page.value)-1
        await self.show_checked_page(interaction, page)

    @discord.ui.button(label='Quit', style=discord.ButtonStyle.red)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button):
        """stops the pagination session."""
        await interaction.response.defer()
        await interaction.delete_original_message()
        self.stop()


class InteractionDeletedView(discord.ui.View):
    def __init__(self, bot: AndreiBot, interaction: discord.Interaction, hidden: bool, message_id: int, author: discord.User, *, timeout: typing.Optional[float] = 180):
        super().__init__(timeout=None)
        self.bot = bot
        self.interaction = interaction
        self.message_id = message_id
        self.hidden = hidden
        self.author = author
        self.file = self.bot.deleted_files.get(message_id)
        if self.file is None:
            self.remove_item(self._snipefile)

    @discord.ui.button(label="delete message", style=discord.ButtonStyle.red)
    async def _delete_message(self, interaction: discord.Interaction, button: discord.Button):
        if not ((interaction.user == self.author) or interaction.channel.permissions_for(interaction.user).manage_messages):
            return await interaction.response.send_message("You need to either be the author of that message or have manage messages permissions in this channel to do that", ephemeral=True)
        bot: AndreiBot = interaction.client
        async with bot.db.cursor() as cur:
            await cur.execute(f"DELETE FROM messages WHERE message = {self.message_id}")
            await bot.db.commit()
        await interaction.response.defer()
        await interaction.delete_original_message()

    @discord.ui.button(label="snipe file")
    async def _snipefile(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message(f"You need the `manage messages` permission to snipe files", ephemeral=True)
        filetuple = self.bot.deleted_files.get(self.message_id)
        if filetuple is None:
            return await interaction.response.send_message(f"I don't have that file saved anymore (I delete them after 1 hour)", ephemeral=True)
        await interaction.response.defer(ephemeral=self.hidden)
        try:
            await interaction.followup.send(file=discord.File(io.BytesIO(filetuple[0]), filename=filetuple[1]), content=f"Requested by {interaction.user}")
        except (discord.HTTPException, discord.Forbidden, ValueError, TypeError):
            await interaction.followup.send(content="I couldn't upload that file")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        elif interaction.user == interaction.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message("This button isn't for you", ephemeral=True)


class EmojiSearchModal(discord.ui.Modal, title="Search emojis"):
    name = discord.ui.TextInput(label="name")

    def __init__(self, *, title: str = "emoji search", emojis: list[discord.PartialEmoji]) -> None:
        self.emojis = emojis
        super().__init__(title=title)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        entries = []
        for emoji in self.emojis:
            if self.name.value.lower() in emoji.name.lower():
                entries.append(emoji)

        if not entries:
            return await interaction.response.send_message(f"No results for {self.name.value}", ephemeral=True)
        await interaction.response.defer()

        source = EmojiPageSource(entries, per_page=1)
        pages = EmojiPages(source, client=interaction.client,
                           author=interaction.user, channel=interaction.channel, search=False)
        pages.embed.set_author(name=interaction.user,
                               icon_url=interaction.user.display_avatar)
        pages.embed.add_field(
            name=f"{len(entries)} emojis matching", value=f"{self.name.value}")
        await pages.start()


class EmojiPageSource(menus.ListPageSource):

    def __init__(self, entries, *, per_page, icon=None, name=None):
        super().__init__(entries, per_page=per_page)
        self.entries = entries
        self.icon = icon
        self.name = name

    async def format_page(self, menu: menus.Menu, entry: discord.PartialEmoji):
        if self.name:
            menu.embed.set_author(name=self.name, icon_url=self.icon)
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)'
            menu.embed.set_footer(text=footer)
        menu.embed.set_image(url=entry.url)
        emoji_str = f"<{'a' if entry.animated else ''}:{entry.name}:{entry.id}>"
        menu.embed.description = f"`{emoji_str}`\n[URL]({entry.url})"
        return menu.embed


class EmojiPages(discord.ui.View):
    def __init__(
        self,
        source: menus.PageSource,
        *,
        search: bool = True,
        client: AndreiBot,
        author: discord.User,
        channel: discord.TextChannel,
        check_embeds: bool = True,
        compact: bool = False,
    ):
        super().__init__()
        self.source: menus.PageSource = source
        self.check_embeds: bool = check_embeds
        self.client = client
        self.author = author
        self.channel = channel
        self.message: Optional[discord.Message] = None
        self.current_page: int = 0
        self.compact: bool = compact
        self.search = search
        self.input_lock = asyncio.Lock()
        self.clear_items()
        self.fill_items()
        self.timeout = None
        self.embed = discord.Embed(color=discord.Color.orange())

    def fill_items(self) -> None:
        if not self.compact:
            self.numbered_page.row = 1
            self.stop_pages.row = 1

        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)  # type: ignore
            self.add_item(self.go_to_previous_page)  # type: ignore
            if not self.compact:
                self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            if use_last_and_first:
                self.add_item(self.go_to_last_page)  # type: ignore
            if not self.compact:
                self.add_item(self.numbered_page)  # type: ignore
            self.add_item(self.stop_pages)  # type: ignore
            if self.search:
                self.add_item(self._search)
            self.add_item(self._steal)
        else:
            self.add_item(self._steal)
            self.add_item(self.stop_pages)

    async def _get_kwargs_from_page(self, page: int) -> Dict[str, Any]:
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {'content': value, 'embed': None}
        elif isinstance(value, discord.Embed):
            return {'embed': value, 'content': None}
        else:
            return {}

    async def show_page(self, interaction: discord.Interaction, page_number: int) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_number)
        if kwargs:
            if interaction.response.is_done():
                if self.message:
                    await self.message.edit(**kwargs, view=self)
            else:
                await interaction.response.edit_message(**kwargs, view=self)

    def _update_labels(self, page_number: int) -> None:
        self.go_to_first_page.disabled = page_number == 0
        if self.compact:
            max_pages = self.source.get_max_pages()
            self.go_to_last_page.disabled = max_pages is None or (
                page_number + 1) >= max_pages
            self.go_to_next_page.disabled = max_pages is not None and (
                page_number + 1) >= max_pages
            self.go_to_previous_page.disabled = page_number == 0
            return

        self.go_to_current_page.label = str(page_number + 1)
        self.go_to_previous_page.label = str(page_number)
        self.go_to_next_page.label = str(page_number + 2)
        self.go_to_next_page.disabled = False
        self.go_to_previous_page.disabled = False
        self.go_to_first_page.disabled = False

        max_pages = self.source.get_max_pages()
        if max_pages is not None:
            self.go_to_last_page.disabled = (page_number + 1) >= max_pages
            if (page_number + 1) >= max_pages:
                self.go_to_next_page.disabled = True
                self.go_to_next_page.label = '…'
            if page_number == 0:
                self.go_to_previous_page.disabled = True
                self.go_to_previous_page.label = '…'

    async def show_checked_page(self, interaction: discord.Interaction, page_number: int) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(interaction, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.author:
            return True
        elif interaction.user == self.channel.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message("This button isn't for you", ephemeral=True)

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            await interaction.followup.send('An unknown error occurred, sorry', ephemeral=True)
        else:
            await interaction.response.send_message('An unknown error occurred, sorry', ephemeral=True)

    async def start(self) -> None:
        if self.check_embeds and not self.channel.permissions_for(self.channel.guild.me).embed_links:
            await self.channel.send('Bot does not have embed links permission in this channel.')
            return

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        self.message = await self.channel.send(**kwargs, view=self)

    @discord.ui.button(label='≪', style=discord.ButtonStyle.grey)
    async def go_to_first_page(self,  interaction: discord.Interaction, button: discord.ui.Button):
        """go to the first page"""
        await self.show_page(interaction, 0)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.blurple)
    async def go_to_previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the previous page"""
        await self.show_checked_page(interaction, self.current_page - 1)

    @discord.ui.button(label='Current', style=discord.ButtonStyle.grey, disabled=True)
    async def go_to_current_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label='Next', style=discord.ButtonStyle.blurple)
    async def go_to_next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the next page"""
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button(label='≫', style=discord.ButtonStyle.grey)
    async def go_to_last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(interaction, self.source.get_max_pages() - 1)

    @discord.ui.button(label='Skip to page...', style=discord.ButtonStyle.grey)
    async def numbered_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """lets you type a page number to go to"""
        modal = PageModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        page = modal.page.value
        if page is None:
            return await interaction.response.defer(ephemeral=True)
        page = int(modal.page.value)-1
        await self.show_checked_page(interaction, page)

    @discord.ui.button(label='Quit', style=discord.ButtonStyle.red)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button):
        """stops the pagination session."""
        await interaction.response.defer()
        await interaction.delete_original_message()
        self.stop()

    @discord.ui.button(label="search")
    async def _search(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.send_modal(EmojiSearchModal(title="Search for emojis", emojis=self.source.entries))

    @discord.ui.button(label="steal")
    async def _steal(self, interaction: discord.Interaction, button: discord.Button):
        if not interaction.user.guild_permissions.manage_emojis:
            return await interaction.response.send_message("You don't have the permissions to do that!", ephemeral=True)
        await interaction.response.defer()
        emoji: discord.PartialEmoji = self.source.entries[self.current_page]
        bytes = await emoji.read()
        try:
            new_emoji = await interaction.guild.create_custom_emoji(name=emoji.name, image=bytes, reason=f"Action done by {interaction.user} (ID: {interaction.user.id})")
            emoji_str = str(new_emoji)
            em = discord.Embed(color=discord.Color.green(
            ), description=f"done {emoji_str}\nname: {new_emoji.name}\nID: {new_emoji.id}\nanimated: {new_emoji.animated}\n`{str(new_emoji)}`")
            em.set_thumbnail(url=new_emoji.url)
            em.set_author(name=str(interaction.user),
                          icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=em)
        except discord.HTTPException as e:
            await interaction.followup.send(str(e), ephemeral=True)


class tiktokvideo:
    def __init__(self, video: io.BytesIO, url: str, download_url: str) -> None:
        self.video = video
        self.url = url
        self.download_url = download_url


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


class AvatarPages(RoboPages):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.author:
            return True
        if interaction.user == self.ctx.author:
            return True
        elif interaction.user == self.ctx.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message("This button isn't for you", ephemeral=True)

    def __init__(self, entries, *, ctx: commands.Context, author: discord.User, type: str, no_pfp=False):
        super().__init__(AvatarSimplePageSource(entries=entries, per_page=1), ctx=ctx)
        self.author = author
        self.embed = discord.Embed(colour=discord.Colour.orange())
        # begins with formatted timestamp + original content
        self.embed.set_author(name=author, icon_url=author.display_avatar.url)
        if no_pfp:
            self.embed.title = "this user has no server avatar"
            self.embed.description = "Here's the avatar history anyway"
        else:
            self.embed.title = f"{type} avatars history"

    def fill_items(self) -> None:
        if not self.compact:
            self.numbered_page.row = 1
            self.stop_pages.row = 1

        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)  # type: ignore
            self.add_item(self.go_to_previous_page)  # type: ignore
            if not self.compact:
                self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            if use_last_and_first:
                self.add_item(self.go_to_last_page)  # type: ignore
            if not self.compact:
                self.add_item(self.numbered_page)  # type: ignore
            self.add_item(self.stop_pages)  # type: ignore
        self.add_item(self.delete_avatar)

    @discord.ui.button(label="Delete from database", style=discord.ButtonStyle.red)
    async def delete_avatar(self, interaction: discord.Interaction, button: discord.Button):
        #return await interaction.response.send_message("HELLO")
        if self.author != self.ctx.author:
            if interaction.user == self.ctx.guild.owner:
                pass
            elif interaction.user.guild_permissions.administrator:
                pass
            elif interaction.user.id in interaction.client.owner_ids:
                pass
            else:
                return await interaction.response.send_message("This button isn't for you", ephemeral=True)
        try:
            avatar_url = self.source.entries[self.current_page][0]
            embed = discord.Embed(color=discord.Color.orange(),
                                description="Are you sure you want to delete this avatar?")
            view = AvatarConfirmationView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            await view.wait()
            if not view.value:
                return
            async with interaction.client.db.cursor() as cursor:
                await cursor.execute("DELETE FROM avatars WHERE url = ?", (avatar_url, ))
                await interaction.client.db.commit()
            await interaction.edit_original_message(view=None, embeds=[], content="Done")
        except Exception as e:
            if interaction.response.is_done():
                await interaction.followup.send(str(e))
            else:
                await interaction.response.send_message(str(e), ephemeral=True)


class AvatarSimplePageSource(menus.ListPageSource):
    async def format_page(self, menu: menus.Menu, entry):
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)'
            menu.embed.set_footer(text=footer)
        menu.embed.set_image(url=entry[0])
        menu.embed.timestamp = datetime.datetime.fromtimestamp(entry[1])
        return menu.embed


class RoleSimplePageSource(menus.ListPageSource):
    async def format_page(self, menu: menus.Menu, entries: list[discord.Member]):
        pages = []
        # one emoji per page
        for index, member in enumerate(entries, start=menu.current_page * 1):
            pages.append(f'{member}')

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum}'
            if self.role.id == 849833845603696690:
                footer += f" ({len(self.entries)}/{len([m for m in self.role.guild.members if not m.bot])})"
            else:
                footer +=  f" ({len(self.entries)} entries)"
            menu.embed.set_footer(text=footer)
        menu.embed.description = '\n'.join(pages)
        return menu.embed


class EmojiPageSource(menus.ListPageSource):

    def __init__(self, entries, *, per_page, icon=None, name=None):
        super().__init__(entries, per_page=per_page)
        self.entries = entries
        self.icon = icon
        self.name = name

    async def format_page(self, menu: menus.Menu, entry: discord.PartialEmoji):
        if self.name:
            menu.embed.set_author(name=self.name, icon_url=self.icon)
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)'
            menu.embed.set_footer(text=footer)
        menu.embed.set_image(url=entry.url)
        emoji_str = f"<{'a' if entry.animated else ''}:{entry.name}:{entry.id}>"
        menu.embed.description = f"`{emoji_str}`\n[URL]({entry.url})"
        return menu.embed


class RolePages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(self,entries, *, ctx: commands.Context, per_page: int = 12, role: discord.Role):
        source = RoleSimplePageSource(entries=entries, per_page=per_page)
        source.role=role
        super().__init__(source, ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.orange(
        ), title=f"Members in {role.name}", description=f"{role.mention}\n\n")
        self.emojis: list[discord.PartialEmoji] = entries


class ConfirmationDeleteView(discord.ui.View):
    def __init__(self, ctx: commands.Context, emoji: discord.Emoji, *, timeout: Optional[float] = 180):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.emoji = emoji

    @discord.ui.button(style=discord.ButtonStyle.green, emoji="\U0001f44d")
    async def _delete_emoji_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.emoji.delete(reason=f"Deleted by {self.ctx.author}")
        await interaction.response.edit_message(embed=discord.Embed(color=discord.Color.orange(), description="Done \U0001f44d"), view=None)
        self.stop()

    @discord.ui.button(style=discord.ButtonStyle.red, emoji="\U0001f44e")
    async def _cancel_everything(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=discord.Embed(color=discord.Color.orange(), description="Ok, canceled"), view=None)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.ctx.author:
            return True
        elif interaction.user == self.ctx.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message("This button isn't for you", ephemeral=True)


class SimplePageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        pages = []
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            pages.append(f'{index + 1}. {entry}')

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)'
            menu.embed.set_footer(text=footer)

        menu.embed.description = '\n'.join(pages)
        return menu.embed


class SimplePages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(self, entries, *, ctx: commands.Context, per_page: int = 12, title=None, description=None, footer=None):
        super().__init__(SimplePageSource(entries, per_page=per_page), ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.orange(), title=title)
        if description:
            self.embed.add_field(name=description, value="\u200b")
        if footer:
            self.embed.set_footer(text=footer)


class SnipeSimplePageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        entry = entries
        content = f'<t:{entry[1]}:d> <t:{entry[1]}:T>\n{entry[0]}'
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)'
            menu.embed.set_footer(text=footer)

        menu.embed.clear_fields()
        num = str(menu.current_page+1)
        if num[-1] == "1":
            num += "st"
        elif num[-1] == "2":
            num += "nd"
        elif num[-1] == "3":
            num += "rd"
        else:
            num += "th"

        menu.embed.add_field(name=f"{num} edit", value=content if (len(
            content) < 1024) else f"{content[:960]}\n\n----REST IS TOO LONG TO DISPLAY----")

        return menu.embed


class SnipeSimplePages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(self, entries, *, ctx: commands.Context, original, author: discord.User):
        super().__init__(SnipeSimplePageSource(entries=entries, per_page=1), ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.orange())
        # begins with formatted timestamp + original content
        if author:
            self.embed.set_author(
                name=author, icon_url=author.display_avatar.url)
        self.embed.title = "Original"
        self.embed.description = f"<t:{original[1]}:d> <t:{original[1]}:T>\n{original[0]}\n\n"


def format_description(s: pytube.Stream):
    parts = [f'{s.mime_type}']
    if s.includes_video_track:
        parts.extend(
            [f'{"with" if s.includes_audio_track else "without"} audio'])
        parts.extend([f'{s.resolution}', f'@{s.fps}fps'])

    else:
        parts.extend([f'{s.abr}', f'audio codec="{s.audio_codec}"'])
    return f"{' '.join(parts)}"


class YouTubeDownloadSelect(discord.ui.View):
    def __init__(self, *, timeout: Optional[float] = 180, streams: pytube.StreamQuery, ctx: commands.Context):
        super().__init__(timeout=None)
        self.options = streams
        self.audio: bool = False
        self.all_pts: bool = False
        self.ctx = ctx
        for stream in self.options.filter(progressive=True):
            s = format_description(stream)
            self._select.add_option(description=s, value=str(
                stream.itag), label=f"{stream.resolution} @{stream.fps}fps")

    @discord.ui.button(label="all options", style=discord.ButtonStyle.red)
    async def all_options(self, interaction: discord.Interaction, button: discord.Button):
        self.all_pts = not self.all_pts
        if self.all_pts:
            button.style = discord.ButtonStyle.green
        else:
            button.style = discord.ButtonStyle.red

        if self.all_pts:
            self._select.options.clear()
            opts = self.options
            if len(opts) > 25:
                opts = opts[:25]
            for stream in opts:
                s = format_description(stream)
                self._select.add_option(description=s, value=str(
                    stream.itag), label=f"{stream.mime_type}")
        elif self.audio:
            self._select.options.clear()
            for stream in self.options.filter(only_audio=True):
                s = format_description(stream)
                self._select.add_option(label=s, value=str(stream.itag))
        else:
            self._select.options.clear()
            for stream in self.options.filter(progressive=True):
                s = format_description(stream)
                self._select.add_option(description=s, value=str(
                    stream.itag), label=f"{stream.resolution} @{stream.fps}fps")

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="audio only", style=discord.ButtonStyle.red)
    async def _audio_only(self, interaction: discord.Interaction, button: discord.Button):
        self.audio = not self.audio
        if self.audio:
            button.style = discord.ButtonStyle.green
        else:
            button.style = discord.ButtonStyle.red

        if self.audio:
            self._select.options.clear()
            for stream in self.options.filter(only_audio=True):
                s = format_description(stream)
                self._select.add_option(label=s, value=str(stream.itag))
            pass
        else:
            self._select.options.clear()
            for stream in self.options.filter(progressive=True):
                s = format_description(stream)
                self._select.add_option(description=s, value=str(
                    stream.itag), label=f"{stream.resolution} @{stream.fps}fps")

        await interaction.response.edit_message(view=self)

    @discord.ui.select()
    async def _select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if self.all_pts:
            self._select.options.clear()
            for stream in self.options:

                s = format_description(stream)
                self._select.add_option(description=s, value=str(
                    stream.itag), label=f"{stream.mime_type}")
        elif self.audio:
            self._select.options.clear()
            for stream in self.options.filter(only_audio=True):
                s = format_description(stream)
                self._select.add_option(label=s, value=str(stream.itag))
            pass
        else:
            self._select.options.clear()
            for stream in self.options.filter(progressive=True):
                s = format_description(stream)
                self._select.add_option(description=s, value=str(
                    stream.itag), label=f"{stream.resolution} @{stream.fps}fps")
        video = self.options.get_by_itag(int(select.values[0]))
        em = discord.Embed(color=discord.Color.orange(),
                           description=f"[click here to download]({video.url})")
        if self.audio:
            em.description += "\nnote: this is a raw audio file, you'll have to change the file extension to `.mp3` or encode it yourself if it doesn't work"
        await interaction.response.send_message(embed=em, ephemeral=True)


class InteractionSnipeSimplePageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        entry = entries
        content = f'<t:{entry[1]}:d> <t:{entry[1]}:T>\n{entry[0]}'
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)'
            menu.embed.set_footer(text=footer)

        menu.embed.clear_fields()
        num = str(menu.current_page+1)
        if num[-1] == "1":
            num += "st"
        elif num[-1] == "2":
            num += "nd"
        elif num[-1] == "3":
            num += "rd"
        else:
            num += "th"

        menu.embed.add_field(name=f"{num} edit", value=content if (len(
            content) < 1024) else f"{content[:960]}\n\n----REST IS TOO LONG TO DISPLAY----")

        return menu.embed


class InteractionSnipeSimplePages(InteractionRoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(self, entries, *, interaction: discord.Interaction, original, author: discord.User, hidden: bool = False):
        super().__init__(InteractionSnipeSimplePageSource(entries=entries,
                                                          per_page=1), interaction=interaction, hidden=hidden)
        self.embed = discord.Embed(colour=discord.Colour.orange())
        # begins with formatted timestamp + original content
        if author:
            self.embed.set_author(
                name=author, icon_url=author.display_avatar.url)
        self.embed.title = "Original"
        self.embed.description = f"<t:{original[1]}:d> <t:{original[1]}:T>\n{original[0]}\n\n"


class InteractionSimplePages(InteractionRoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(self, entries, *, interaction: discord.Interaction, hidden: bool = False, per_page: int = 12, title=None, description=None, footer=None):
        super().__init__(SimplePageSource(entries, per_page=per_page),
                         interaction=interaction, hidden=hidden)
        self.embed = discord.Embed(colour=discord.Colour.orange(), title=title)
        if description:
            self.embed.add_field(name=description, value="\u200b")
        if footer:
            self.embed.set_footer(text=footer)




class InteractionAvatarPages(InteractionRoboPages):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        elif interaction.user == interaction.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message("This button isn't for you", ephemeral=True)

    def __init__(self, entries, *, interaction: discord.Interaction, author: discord.User, type: str, no_pfp=False, hidden: bool = False):
        super().__init__(AvatarSimplePageSource(entries=entries,
                                                per_page=1), interaction=interaction, hidden=hidden)
        self.embed = discord.Embed(colour=discord.Colour.orange())
        # begins with formatted timestamp + original content
        self.author = author
        self.embed.set_author(name=author, icon_url=author.display_avatar.url)
        if no_pfp:
            self.embed.title = "this user has no server avatar"
            self.embed.description = "Here's the avatar history anyway"
        else:
            self.embed.title = f"{type} avatars history"
    
    def fill_items(self) -> None:
        if not self.compact:
            self.numbered_page.row = 1
            self.stop_pages.row = 1

        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)  # type: ignore
            self.add_item(self.go_to_previous_page)  # type: ignore
            if not self.compact:
                self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            if use_last_and_first:
                self.add_item(self.go_to_last_page)  # type: ignore
            if not self.compact:
                self.add_item(self.numbered_page)  # type: ignore
            self.add_item(self.stop_pages)  # type: ignore
        self.add_item(self.delete_avatar)

    @discord.ui.button(label="Delete from database", style=discord.ButtonStyle.red)
    async def delete_avatar(self, interaction: discord.Interaction, button: discord.Button):
        if self.author != self.interaction.user:
            if interaction.user == interaction.guild.owner:
                pass
            elif interaction.user.guild_permissions.administrator:
                pass
            elif interaction.user.id in interaction.client.owner_ids:
                pass
            else:
                return await interaction.response.send_message("This button isn't for you", ephemeral=True)
        try:
            avatar_url = self.source.entries[self.current_page][0]
            embed = discord.Embed(color=discord.Color.orange(),
                                description="Are you sure you want to delete this avatar?")
            view = AvatarConfirmationView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            await view.wait()
            if not view.value:
                return
            async with interaction.client.db.cursor() as cursor:
                await cursor.execute("DELETE FROM avatars WHERE url = ?", (avatar_url, ))
                await interaction.client.db.commit()
            await interaction.edit_original_message(view=None, embeds=[], content="Done")
        except Exception as e:
            if interaction.response.is_done():
                await interaction.followup.send(str(e))
            else:
                await interaction.response.send_message(str(e), ephemeral=True)





class ChimpButton(discord.ui.Button):
    def __init__(self, *, label: typing.Optional[str] = None, style: discord.ButtonStyle = discord.ButtonStyle.gray, disabled: bool = False, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label=label, disabled=disabled)
        self.x = x
        self.y = y
        self.view: ChimpView
        self.value = 0

    async def end_game(self):
        self.style = discord.ButtonStyle.red
        for button in self.view.children:
            button.disabled = True
            if button.value != 0:
                if button.style == discord.ButtonStyle.green:
                    continue
                button.label = str(button.value)
        self.view.stop()
        self.view.lost = True
        if self.view.previous:
            self.view.message = f"Your record is {self.view.max-1}"
            await self.view.update_record()
        else:
            self.view.message="You lost"

    async def win_game(self):
        self.style = discord.ButtonStyle.green
        self.view.message = "You completed the game"
        self.view.stop()
        await self.view.update_record()

    async def callback(self, interaction: discord.Interaction):
        self.view.timeout=60
        self.view.expires = discord.utils.utcnow() + datetime.timedelta(seconds=self.view.timeout)
        self.disabled = True
        if self.value == 1:
            time_taken = discord.utils.utcnow() - self.view.started
            self.view.previous_time_taken = self.view.time_taken
            self.view.time_taken = time_taken.seconds
            for button in self.view.children:
                button.label = " "
        if self.value == self.view.current:  # guess
            self.style = discord.ButtonStyle.green
            self.view.current = self.view.current+1
            self.label = str(self.value)
            self.view.message = f"You guessed {self.value}/{self.view.max} (You can reply until {discord.utils.format_dt(self.view.expires, 'T')})"
            #await interaction.channel.send(self.view.expires.timestamp())
            if self.view.current == self.view.max+1:
                if self.view.lost:
                    await self.end_game()
                else:
                    self.view.previous=True
                    self.view.max += 1
                    if self.view.max == 26:
                        await self.win_game()
                    else:
                        self.view.initialize_game()
        else:  # wrong button
            await self.end_game()
        await interaction.response.edit_message(view=self.view, content=self.view.message)


class ChimpView(discord.ui.View):
    def __init__(self, amount: int, author: discord.User, bot: AndreiBot, *, timeout: typing.Optional[float] = 90):
        super().__init__(timeout=timeout)
        """This creates the game view and prepares the first game with self.max numbers"""
        self.started = discord.utils.utcnow()
        self.time_taken=0
        self.previous_time_taken = 0
        self.expires = discord.utils.utcnow() + datetime.timedelta(seconds=timeout)
        self.previous = False
        self.board = [[0]*5]*5
        self.author = author
        self.current: int = 1
        self.children: list[ChimpButton]
        self.max: int = amount  # how many numbers
        self.button_coordinates = []
        self.embed: discord.Embed = None
        self.lost = False
        self.message = ""
        self.bot = bot
        self.m: discord.Message = None
        for column in range(1, 6):
            for row in range(1, 6):
                button = ChimpButton(
                    x=column, y=row, label=" ", disabled=True, style=discord.ButtonStyle.gray)
                self.add_item(button)
                self.board[row-1][column-1] = button
        self.initialize_game()

    async def on_timeout(self) -> None:
        for button in self.children:
            button.disabled = True
        if self.previous:
            await self.m.edit(view=self, content=f"I don't know wtf you're doing but you're taking too long to reply, your score is {self.max-1}")
            await self.update_record()
        else:
            await self.m.edit(view=self, content="You got timed out")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.author:
            return True
        await interaction.response.send_message(f"This game is for {self.author} (ID: {self.author.id})", ephemeral=True)

    def initialize_game(self):
        """This edits the board with random coordinates of the buttons and x numbers to guess based on self.max"""
        self.started = discord.utils.utcnow()
        self.timeout = self.max*60
        self.expires = discord.utils.utcnow() + datetime.timedelta(seconds=self.timeout)
        self.message = f"Memorize the numbers on the grid and tap on the first one to start the game (You can reply until {discord.utils.format_dt(self.expires, 'T')})"
        self.current = 1
        for button in self.children:
            button.label = " "
            button.disabled = True
            button.style = discord.ButtonStyle.gray
            button.value = 0
        button_coordinates = []
        for button_number in range(1, self.max+1):
            new_coordinate = (random.randint(
                1, 5), random.randint(1, 5), button_number)
            while (new_coordinate[0], new_coordinate[1]) in [(x[0], x[1]) for x in button_coordinates]:
                new_coordinate = (random.randint(
                    1, 5), random.randint(1, 5), button_number)
            button_coordinates.append(new_coordinate)
        self.button_coordinates = button_coordinates
        for x, y, number in self.button_coordinates:
            for b in self.children:
                if b.x == x and b.y == y:
                    b.label = str(number)
                    b.value = number
                    b.disabled = False
                    b.style = discord.ButtonStyle.blurple
        

    async def update_record(self):
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(f"SELECT * FROM chimps WHERE user = {self.author.id}")
            data = await cursor.fetchone()
            if not data:
                await cursor.execute("INSERT INTO chimps (user, score, time) VALUES (?, ?, ?)", (self.author.id, self.max-1, self.previous_time_taken))
            elif data[1] < self.max-1:
                await cursor.execute(f"DELETE FROM chimps WHERE user = {self.author.id}")
                await self.bot.db.commit()
                await cursor.execute("INSERT INTO chimps (user, score, time) VALUES (?, ?, ?)", (self.author.id, self.max-1, self.previous_time_taken))
            await self.bot.db.commit()
        await self.m.add_reaction("\U0001f3c5")

