import discord
from discord.ext import commands
from discord.ext.commands import Bot
from discord import app_commands, Embed, Interaction, User, ButtonStyle, Member
from discord.ui import Button, View, button
from sqlalchemy import select, delete, update, and_, asc, func
from discord.app_commands import Choice

from math import floor, ceil
from sqlalchemy.ext.asyncio import AsyncSession


from datetime import datetime, timedelta, timezone, date
import random

from db.models import Player, PlayerItem, Item, MarketItem, BuyOrder, SellOrder, Company, Government, CompanyItem, CompanyJoinRequest, GovernmentGDP
from config import TOKEN, GUILD_ID, JOB_SWITCH_COOLDOWN, WORK_COOLDOWN, BUY_ORDER_DURATION, SELL_ORDER_DURATION, GIFT_COOLDOWN
from db.db import get_session
from util import get_hunger_depletion, get_thirst_depletion, use_item, has_item, add_item, remove_item, initialize_market_for_server, add_owed_taxes

class Client(commands.Bot):
    async def on_ready(self):
        print(f'Logged in as {self.user.name}')

    async def setup_hook(self):
        await self.tree.sync(guild=guild_id)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = Client(command_prefix="!", intents=intents)

guild_id = discord.Object(id=GUILD_ID)

@client.tree.command(name="ping", description="Shows the latency of the bot", guild=guild_id)
async def ping(interaction: discord.Interaction):
    print(f"{interaction.user}: /ping")
    ping_embed = discord.Embed(
        title="Ping",
        description="Latency in ms",
        color=discord.Color.yellow()
    )
    ping_embed.add_field(
        name=f"{client.user.name}'s Latency (ms): ",
        value=f"{round(client.latency * 1000)}ms",
        inline=False
    )
    ping_embed.set_footer(
        text=f"Requested by {interaction.user}",
        icon_url=interaction.user.display_avatar.url
    )
    await interaction.response.send_message(embed=ping_embed)

@client.tree.command(name="items", description="Shows all the items and their base values", guild=guild_id)
async def get_items(interaction: discord.Interaction):
    print(f"{interaction.user}: /items")
    await interaction.response.defer(thinking=True, ephemeral=True)

    async for session in get_session():
        result = await session.execute(select(Item))
        items = result.scalars().all()

    if not items:
        await interaction.followup.send("No items found.")
        return

    items_per_page = 10
    max_page = (len(items) - 1) // items_per_page

    def get_page_embed(page: int) -> discord.Embed:
        embed = discord.Embed(
            title=f"Item List (Page {page + 1}/{max_page + 1})",
            description="List of all registered items",
            color=discord.Color.green()
        )
        for item in items[page * items_per_page:(page + 1) * items_per_page]:
            embed.add_field(
                name=item.item_tag,
                value=f"Base Price: {item.base_price}",
                inline=False
            )
        return embed

    class Paginator(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.page = 0

        @discord.ui.button(label="⏮️", style=discord.ButtonStyle.secondary)
        async def first(self, interaction_btn: discord.Interaction, _):
            self.page = 0
            await interaction_btn.response.edit_message(embed=get_page_embed(self.page), view=self)

        @discord.ui.button(label="⬅️", style=discord.ButtonStyle.primary)
        async def previous(self, interaction_btn: discord.Interaction, _):
            if self.page > 0:
                self.page -= 1
                await interaction_btn.response.edit_message(embed=get_page_embed(self.page), view=self)
            else:
                await interaction_btn.response.defer()

        @discord.ui.button(label="➡️", style=discord.ButtonStyle.primary)
        async def next(self, interaction_btn: discord.Interaction, _):
            if self.page < max_page:
                self.page += 1
                await interaction_btn.response.edit_message(embed=get_page_embed(self.page), view=self)
            else:
                await interaction_btn.response.defer()

        @discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary)
        async def last(self, interaction_btn: discord.Interaction, _):
            self.page = max_page
            await interaction_btn.response.edit_message(embed=get_page_embed(self.page), view=self)

    await interaction.followup.send(embed=get_page_embed(0), view=Paginator())


@client.tree.command(
    name="stats",
    description="Tells you everything about a user. If no user-id is provided, it will show your stats",
    guild=guild_id
)
@app_commands.describe(user="The stats of the user you wish to see the stats of")
async def stats(interaction: discord.Interaction, user: discord.User | discord.Member = None):
    print(f"{interaction.user}: /stats: {user}")
    await interaction.response.defer(thinking=True)

    target_user = user or interaction.user
    user_id = int(target_user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        result = await session.execute(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            # Standardwerte
            player = Player(
                id=user_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job=None,
                created_at=datetime.utcnow()
            )
            session.add(player)
            await session.commit()

        embed = discord.Embed(
            title=f"Stats for {target_user.display_name}",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Money", value=f"{player.money:.2f}", inline=True)
        embed.add_field(name="Debt", value=f"{player.debt:.2f}", inline=True)
        embed.add_field(name="Health", value=f"{player.health}", inline=True)
        embed.add_field(name="Hunger", value=f"{player.hunger}", inline=True)
        embed.add_field(name="Thirst", value=f"{player.thirst}", inline=True)
        embed.add_field(name="Job", value=player.job or "None", inline=True)
        embed.add_field(name="Taxes Owed", value=f"{player.taxes_owed:.2f}", inline=True)
        embed.set_footer(text=f"User ID: {target_user.id}")

        # Spieler-Inventar abfragen
        result_items = await session.execute(
            select(PlayerItem).where(
                PlayerItem.user_id == user_id,
                PlayerItem.server_id == server_id
            )
        )
        items = result_items.scalars().all()

        if items:
            inventory_lines = []
            for item in items:
                line = f"{item.amount}x {item.item_tag}"
                if item.durability is not None:
                    line += f" (Durability: {item.durability})"
                inventory_lines.append(line)
            inventory_str = "\n".join(inventory_lines)
            embed.add_field(name="Inventory", value=inventory_str, inline=False)
        else:
            embed.add_field(name="Inventory", value="Empty", inline=False)


        await interaction.followup.send(embed=embed)












@client.tree.command(
    name="job",
    description="Used by anyone to change which job they have",
    guild=guild_id
)
@app_commands.describe(job_type="Which job you want to choose")
@app_commands.choices(job_type=[
    app_commands.Choice(name="lumberjack", value="Lumberjack"),
    app_commands.Choice(name="miner", value="Miner"),
    app_commands.Choice(name="farmer", value="Farmer"),
    app_commands.Choice(name="special-job-water", value="Special Job: Water"),
    app_commands.Choice(name="special-job-natural-gas", value="Special Job: Natural Gas"),
    app_commands.Choice(name="special-job-petroleum", value="Special Job: Petroleum"),
    app_commands.Choice(name="worker", value="Worker"),
    app_commands.Choice(name="entrepreneur", value="Entrepreneur"),
    app_commands.Choice(name="jobless", value="")  # Empty string means no job
])
async def job(interaction: discord.Interaction, job_type: app_commands.Choice[str]):
    print(f"{interaction.user}: /job {job_type.value}")
    await interaction.response.defer(thinking=True, ephemeral=False)

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)
    now = datetime.now()


    async for session in get_session():
        result = await session.execute(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )
        player = result.scalar_one_or_none()
        if player:
            if player.job == job_type.value:
                embed = discord.Embed(
                    title="Job Change Failed",
                    description=f"❌ You already have the job **{job_type.value or 'jobless'}**.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return


            if player.job_switch_cooldown_until and player.job_switch_cooldown_until > now:
                cooldown_ts = int(player.job_switch_cooldown_until.timestamp())
                embed = discord.Embed(
                    title="Cooldown Active",
                    description=f"⏳ You can change your job again <t:{cooldown_ts}:R>.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player.job = job_type.value
            player.company_entrepreneur_id = None
            player.job_switch_cooldown_until = now + JOB_SWITCH_COOLDOWN
        else:
            player = Player(
                id=user_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job=job_type.value,
                job_switch_cooldown_until=now + JOB_SWITCH_COOLDOWN,
                created_at=now
            )
            session.add(player)

        await session.commit()

    desc = (
        f"{interaction.user.mention} quit their job and is now jobless."
        if job_type.value == ""
        else f"{interaction.user.mention} changed their job to **{job_type.value}**."
    )

    embed = discord.Embed(
        title="Job Change",
        description=desc,
        color=discord.Color.green()
    )
    embed.set_footer(text=f"User ID: {user_id}")

    await interaction.followup.send(embed=embed)









@client.tree.command(name="chop", description="Used by lumberjacks to chop down trees.", guild=guild_id)
async def chop(interaction: discord.Interaction):
    print(f"{interaction.user}: /chop")
    await interaction.response.defer(thinking=True)

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)
    now = datetime.now()

    async for session in get_session():
        # Player laden
        result = await session.execute(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            await interaction.followup.send(embed=discord.Embed(
                title="Error!",
                description="Player not found. Please start first.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        if player.job != "Lumberjack":
            await interaction.followup.send(embed=discord.Embed(
                title="Error!",
                description="You are not a lumberjack!",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        # Cooldown check
        if player.work_cooldown_until and player.work_cooldown_until > now:
            cooldown_ts = int(player.work_cooldown_until.timestamp())
            await interaction.followup.send(embed=discord.Embed(
                title="Cooldown Active",
                description=f"⏳ You can work again <t:{cooldown_ts}:R>.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        # Werkzeuge prüfen
        has_axe = await has_item(user_id, server_id, "Axe")
        has_chainsaw = await has_item(user_id, server_id, "Chainsaw")
        if not (has_axe or has_chainsaw):
            await interaction.followup.send(embed=discord.Embed(
                title="Error!",
                description="You don't have an axe or chainsaw! How do you expect to chop down trees without it?",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        # Hunger/Thirst prüfen
        if player.hunger <= 0:
            await interaction.followup.send(embed=discord.Embed(
                title="Error!",
                description="You are too hungry to work!",
                color=discord.Color.red()
            ), ephemeral=True)
            return
        if player.thirst <= 0:
            await interaction.followup.send(embed=discord.Embed(
                title="Error!",
                description="You are too thirsty to work!",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        # Ressourcen generieren
        import random
        resource_type = random.choice(["Wood", "Rubber"])

        if has_chainsaw:
            wood_amount = random.randint(2, 6)
            rubber_amount = random.randint(1, 3)
            used_tool = "Chainsaw"
        else:
            wood_amount = random.randint(1, 3)
            rubber_amount = 1
            used_tool = "Axe"

        amount = wood_amount if resource_type == "Wood" else rubber_amount

        # Werkzeug-Haltbarkeit reduzieren
        durability = await use_item(user_id, server_id, used_tool)

        # Items hinzufügen
        await add_item(user_id, server_id, resource_type, amount)

        # Hunger und Durst reduzieren (Beispiel: -5 pro Arbeit)
        old_hunger = player.hunger
        old_thirst = player.thirst
        player.hunger = max(0, player.hunger - get_hunger_depletion())
        player.thirst = max(0, player.thirst - get_thirst_depletion())

        # Cooldown setzen
        player.work_cooldown_until = now + WORK_COOLDOWN

        await session.commit()

        # Antwort-Embed
        embed = discord.Embed(
            title="Success!",
            description=f"You just chopped and gained {amount}x {resource_type}!",
            color=discord.Color.green()
        )
        embed.add_field(name=f"{used_tool} Durability", value=f"{durability} -> {durability-1}")
        embed.add_field(name="Hunger", value=f"{old_hunger} -> {player.hunger}")
        embed.add_field(name="Thirst", value=f"{old_thirst} -> {player.thirst}")

        await interaction.followup.send(embed=embed)









@client.tree.command(name="mine", description="Used by miners to mine resources.", guild=guild_id)
async def mine(interaction: discord.Interaction):
    print(f"{interaction.user}: /mine")
    await interaction.response.defer(thinking=True)

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)
    now = datetime.now()

    async for session in get_session():
        # Spieler laden
        result = await session.execute(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            await interaction.followup.send(embed=discord.Embed(
                title="Error!",
                description="Player not found. Please start first.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        if player.job != "Miner":
            await interaction.followup.send(embed=discord.Embed(
                title="Error!",
                description="You are not a miner!",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        # Cooldown check
        if player.work_cooldown_until and player.work_cooldown_until > now:
            cooldown_ts = int(player.work_cooldown_until.timestamp())
            await interaction.followup.send(embed=discord.Embed(
                title="Cooldown Active",
                description=f"⏳ You can work again <t:{cooldown_ts}:R>.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        # Werkzeuge prüfen
        has_pickaxe = await has_item(user_id, server_id, "Pickaxe")
        has_mining_machine = await has_item(user_id, server_id, "Mining Machine")
        if not (has_pickaxe or has_mining_machine):
            await interaction.followup.send(embed=discord.Embed(
                title="Error!",
                description="You don't have a pickaxe or mining machine! How do you expect to mine resources without it?",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        # Hunger/Thirst prüfen
        if player.hunger <= 0:
            await interaction.followup.send(embed=discord.Embed(
                title="Error!",
                description="You are too hungry to work!",
                color=discord.Color.red()
            ), ephemeral=True)
            return
        if player.thirst <= 0:
            await interaction.followup.send(embed=discord.Embed(
                title="Error!",
                description="You are too thirsty to work!",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        # Ressourcen generieren
        resource = random.randint(0, 3)  # 0=Iron,1=Minerals,2=Coal,3=Phosphorus

        if has_mining_machine:
            iron = random.randint(5, 12)
            minerals = random.randint(3, 6)
            coal = random.randint(5, 12)
            phosphorus = random.randint(7, 15)
            used_tool = "Mining Machine"
        else:
            iron = random.randint(1, 2)
            minerals = 1
            coal = random.randint(1, 2)
            phosphorus = random.randint(1, 4)
            used_tool = "Pickaxe"

        if resource == 0:
            item_tag = "Iron"
            amount = iron
        elif resource == 1:
            item_tag = "Minerals"
            amount = minerals
        elif resource == 2:
            item_tag = "Coal"
            amount = coal
        else:
            item_tag = "Phosphorus"
            amount = phosphorus

        # Werkzeug-Haltbarkeit reduzieren
        durability = await use_item(user_id, server_id, used_tool)

        # Items hinzufügen
        await add_item(user_id, server_id, item_tag, amount)

        # Hunger und Durst reduzieren
        old_hunger = player.hunger
        old_thirst = player.thirst
        player.hunger = max(0, player.hunger - get_hunger_depletion())
        player.thirst = max(0, player.thirst - get_thirst_depletion())

        # Cooldown setzen
        player.work_cooldown_until = now + WORK_COOLDOWN

        await session.commit()

        # Antwort-Embed
        embed = discord.Embed(
            title="Success!",
            description=f"You just mined and gained {amount}x {item_tag}!",
            color=discord.Color.green()
        )
        embed.add_field(name=f"{used_tool} Durability", value=f"{durability} -> {durability-1}")
        embed.add_field(name="Hunger", value=f"{old_hunger} -> {player.hunger}")
        embed.add_field(name="Thirst", value=f"{old_thirst} -> {player.thirst}")

        await interaction.followup.send(embed=embed)










@client.tree.command(name="farm", description="Used by farmers to harvest crops.", guild=guild_id)
@app_commands.describe(item="The item you want to farm")
@app_commands.choices(item=[
    app_commands.Choice(name="grain", value="Grain"),
    app_commands.Choice(name="wool", value="Wool"),
    app_commands.Choice(name="fish", value="Fish"),
    app_commands.Choice(name="leather", value="Leather"),
])
async def farm(interaction: discord.Interaction, item: app_commands.Choice[str] = None):
    print(f"{interaction.user}: /farm {item}")
    await interaction.response.defer(thinking=True)
    now = datetime.now()
    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        result = await session.execute(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )
        player = result.scalar_one_or_none()
        if not player or player.job != "Farmer":
            embed = discord.Embed(
                title="Error!",
                description="You are not a farmer!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if player.hunger <= 0 or player.thirst <= 0:
            embed = discord.Embed(
                title="Error!",
                description="You are too hungry or thirsty to work!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if player.work_cooldown_until and player.work_cooldown_until > now:
            ts = int(player.work_cooldown_until.timestamp())
            embed = discord.Embed(
                title="Cooldown Active",
                description=f"You can work again <t:{ts}:R>.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Tool checks
        has_fertilizer = await has_item(user_id, server_id, "Fertilizer")
        has_tractor = await has_item(user_id, server_id, "Tractor")

        selected = item.value if item else random.choice(["Grain", "Leather", "Fish", "Wool"])

        grain = random.randint(4, 10) if has_tractor else random.randint(1, 5) if has_fertilizer else random.randint(1, 2)
        leather = random.randint(1, 3)
        fish = random.randint(1, 3)
        wool = random.randint(1, 2)

        resources = {
            "Grain": grain,
            "Leather": leather,
            "Fish": fish,
            "Wool": wool
        }

        amount = resources[selected]

        # Apply tool usage
        used_tool = "Tractor" if has_tractor else "Fertilizer" if has_fertilizer else None
        durability = None
        if used_tool:
            durability = await use_item(user_id, server_id, used_tool)

        await add_item(user_id, server_id, selected, amount)

        # Update hunger/thirst/cooldown
        old_hunger = player.hunger
        old_thirst = player.thirst
        player.hunger = max(0, player.hunger - get_hunger_depletion())
        player.thirst = max(0, player.thirst - get_thirst_depletion())
        player.work_cooldown_until = now + WORK_COOLDOWN
        await session.commit()

        # Embed
        embed = discord.Embed(
            title="Success!",
            description=f"You just harvested crops and gained {amount}x {selected}!",
            color=discord.Color.green()
        )
        if used_tool and durability is not None:
            embed.add_field(
                name=f"{used_tool} Durability",
                value=f"{durability} -> {durability-1}"
            )
        embed.add_field(name="Hunger", value=f"{old_hunger} -> {player.hunger}")
        embed.add_field(name="Thirst", value=f"{old_thirst} -> {player.thirst}")

        await interaction.followup.send(embed=embed)









@client.tree.command(name="harvest", description="Used by special jobs to harvest their unique resource.", guild=guild_id)
async def harvest(interaction: discord.Interaction):
    print(f"{interaction.user}: /harvest")
    await interaction.response.defer(thinking=True)
    now = datetime.now()
    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        result = await session.execute(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )
        player = result.scalar_one_or_none()

        if not player or player.job not in ["Special Job: Water", "Special Job: Natural Gas", "Special Job: Petroleum"]:
            embed = discord.Embed(
                title="Error!",
                description="You are not a special job!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if player.hunger <= 0 or player.thirst <= 0:
            embed = discord.Embed(
                title="Error!",
                description="You are too hungry or thirsty to work!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if player.work_cooldown_until and player.work_cooldown_until > now:
            ts = int(player.work_cooldown_until.timestamp())
            embed = discord.Embed(
                title="Cooldown Active",
                description=f"You can work again <t:{ts}:R>.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Werkzeuglogik + Ressourcenlogik
        job_tool_map = {
            "Special Job: Water": "Water Cleaning",
            "Special Job: Natural Gas": "Gas Pipeline",
            "Special Job: Petroleum": "Oil Drilling Machine"
        }
        item_tag_map = {
            "Special Job: Water": "Water",
            "Special Job: Natural Gas": "Natural Gas",
            "Special Job: Petroleum": "Petroleum"
        }

        job_name = player.job
        item_tag = item_tag_map[job_name]
        tool_name = job_tool_map[job_name]
        has_tool = await has_item(user_id, server_id, tool_name)

        amount = random.randint(1, 3) if has_tool else 1
        await add_item(user_id, server_id, item_tag, amount)

        old_hunger = player.hunger
        old_thirst = player.thirst
        player.hunger = max(0, player.hunger - get_hunger_depletion())
        player.thirst = max(0, player.thirst - get_thirst_depletion())
        player.work_cooldown_until = now + WORK_COOLDOWN
        await session.commit()

        embed = discord.Embed(
            title="Success!",
            description=f"You just harvested your special resources and gained {amount}x {item_tag}!",
            color=discord.Color.green()
        )
        if has_tool:
            durability = await use_item(user_id, server_id, tool_name)
            embed.add_field(name=f"{tool_name} Durability", value=f"{durability} -> {durability-1}")

        embed.add_field(name="Hunger", value=f"{old_hunger} -> {player.hunger}")
        embed.add_field(name="Thirst", value=f"{old_thirst} -> {player.thirst}")

        await interaction.followup.send(embed=embed)











@client.tree.command(name="drink", description="Consumes 1 water from your inventory and fills up your thirst bar.", guild=guild_id)
async def drink(interaction: discord.Interaction):
    print(f"{interaction.user}: /drink")
    await interaction.response.defer(thinking=True)
    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        result = await session.execute(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            embed = discord.Embed(
                title="Error!",
                description="You don't have a character yet.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if player.thirst >= 100:
            embed = discord.Embed(
                title="Error!",
                description="Your thirst bar is completely full! There is no need to drink!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        has_water = await has_item(user_id, server_id, "Water")
        if not has_water:
            embed = discord.Embed(
                title="Error!",
                description="You don't have any water!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await remove_item(user_id, server_id, "Water", 1)
        player.thirst = 100
        await session.commit()

        embed = discord.Embed(
            title="Success!",
            description="You just consumed one water! Your thirst bar is now full again!",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)










@client.tree.command(name="eat", description="Consumes 1 grocery from your inventory and fills up your hunger bar.", guild=guild_id)
async def eat(interaction: discord.Interaction):
    print(f"{interaction.user}: /eat")
    await interaction.response.defer(thinking=True)
    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        result = await session.execute(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            embed = discord.Embed(
                title="Error!",
                description="You don't have a character yet.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if player.hunger >= 100:
            embed = discord.Embed(
                title="Error!",
                description="Your hunger bar is completely full! There is no need to eat!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        has_groceries = await has_item(user_id, server_id, "Grocery")
        if not has_groceries:
            embed = discord.Embed(
                title="Error!",
                description="You don't have any groceries!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await remove_item(user_id, server_id, "Grocery", 1)
        player.hunger = 100
        await session.commit()

        embed = discord.Embed(
            title="Success!",
            description="You just consumed one grocery! Your hunger bar is now full again!",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)









@client.tree.command(
    name="consume",
    description="Consumes an item from the inventory and applies the corresponding effects",
    guild=guild_id
)
@app_commands.describe(item="The item you want to consume")
@app_commands.choices(item=[
    app_commands.Choice(name="Water", value="Water"),
    app_commands.Choice(name="Grocery", value="Grocery"),
    app_commands.Choice(name="Fish", value="Fish")
])
async def consume(interaction: discord.Interaction, item: app_commands.Choice[str]):
    print(f"{interaction.user}: /consume {item.value}")
    await interaction.response.defer(ephemeral=True, thinking=True)

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)
    item_tag = item.value

    async for session in get_session():
        result = await session.execute(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            embed = discord.Embed(
                title="Error!",
                description="You don't have a character yet!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        result = await session.execute(
            select(PlayerItem).where(
                PlayerItem.user_id == user_id,
                PlayerItem.server_id == server_id,
                func.lower(PlayerItem.item_tag) == item.lower()
            )
        )
        player_item = result.scalar_one_or_none()

        if not player_item or player_item.amount < 1:
            embed = discord.Embed(
                title="Error!",
                description=f"You don't have {item_tag}!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        hunger = player.hunger
        thirst = player.thirst
        success_embed = None

        if item_tag == "Water":
            if thirst >= 100:
                embed = discord.Embed(
                    title="Error!",
                    description="Your thirst bar is completely full! There is no need to drink!",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                return
            player.thirst = 100
            await remove_item(user_id, server_id, "Water", 1)
            success_embed = discord.Embed(
                title="Success!",
                description="You just consumed one water! Your thirst bar is now full again!",
                color=discord.Color.green()
            )

        elif item_tag == "Grocery":
            if hunger >= 100:
                embed = discord.Embed(
                    title="Error!",
                    description="Your hunger bar is completely full! There is no need to eat!",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                return
            player.hunger = 100
            await remove_item(user_id, server_id, "Grocery", 1)
            success_embed = discord.Embed(
                title="Success!",
                description="You just consumed one grocery! Your hunger bar is now full again!",
                color=discord.Color.green()
            )

        elif item_tag == "Fish":
            if hunger >= 100 and thirst >= 100:
                embed = discord.Embed(
                    title="Error!",
                    description="Your thirst and hunger bar are completely full! There is no need to consume fish!",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                return
            player.hunger = min(hunger + 15, 100)
            player.thirst = min(thirst + 5, 100)
            await remove_item(user_id, server_id, "Fish", 1)
            success_embed = discord.Embed(
                title="Success!",
                description=f"You just consumed one fish!\nThirst bar: {player.thirst}%\nHunger bar: {player.hunger}%",
                color=discord.Color.green()
            )

        session.add(player)
        await session.commit()

        if success_embed:
            await interaction.followup.send(embed=success_embed)








@client.tree.command(
    name="buy",
    description="Buys items by placing a buy order.",
    guild=guild_id
)
@app_commands.describe(
    item="The item you want to buy",
    unit_price="Maximum price you're willing to pay per unit",
    amount="How many you want to buy (default: 1)"
)
async def buy(
    interaction: discord.Interaction,
    item: str,
    unit_price: float,
    amount: int = 1
):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /buy item: {item}, unit_price: {unit_price}, amount: {amount}")

    if amount <= 0 or unit_price <= 0:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error!",
                description="Amount and unit price must be greater than 0.",
                color=discord.Color.red()
            ), ephemeral=True
        )
        return

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        # Item prüfen
        item_obj = await session.scalar(select(Item).where(func.lower(Item.item_tag) == item.lower()))
        if not item_obj:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description=f"Item **{item}** does not exist.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return
        item_tag = item_obj.item_tag

        # Player laden oder erstellen
        player = await session.scalar(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )
        if not player:
            player = Player(id=user_id, server_id=server_id, money=100.0, debt=0.0, hunger=100, thirst=100, health=100, job=None, created_at=datetime.now())
            session.add(player)
            await session.commit()

        if player.money < unit_price * amount:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Not Enough Money!",
                    description=f"You are trying to buy **{amount}x {item_tag}** for **${unit_price * amount}**, but you only have **${player.money}**.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Bestehende BuyOrder checken
        now = datetime.now()
        expires_at = now + BUY_ORDER_DURATION

        existing_order = await session.scalar(
            select(BuyOrder).where(
                BuyOrder.user_id == user_id,
                BuyOrder.item_tag == item_tag,
                BuyOrder.server_id == server_id,
                BuyOrder.unit_price == unit_price,
                BuyOrder.is_company == False,
            )
        )

        if existing_order:
            existing_order.amount += amount
            existing_order.expires_at = expires_at
            await session.commit()

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Buy Order Merged",
                    description=(
                        f"Merged your buy orders for **{item_tag}** at **${unit_price}**.\n"
                        f"New total: **{existing_order.amount}x {item_tag}** = **${existing_order.amount * unit_price}**."
                    ),
                    color=discord.Color.green()
                )
            )
            return

        # Markt initialisieren, falls nötig
        market_entry = await session.scalar(
            select(MarketItem).where(MarketItem.item_tag == item_tag, MarketItem.server_id == server_id)
        )
        if not market_entry:
            await initialize_market_for_server(server_id)
            market_entry = await session.scalar(
                select(MarketItem).where(MarketItem.item_tag == item_tag, MarketItem.server_id == server_id)
            )

        # SELL-Orders finden
        fulfilled_total = 0
        total_spent = 0.0

        sell_orders = (await session.execute(
            select(SellOrder).where(
                SellOrder.item_tag == item_tag,
                SellOrder.server_id == server_id,
                SellOrder.unit_price <= unit_price,
                SellOrder.expires_at > now
            ).order_by(SellOrder.unit_price.asc())
        )).scalars().all()

        for sell_order in sell_orders:
            if player.money < sell_order.unit_price:
                break

            match_amount = min(amount, sell_order.amount)
            total_price = round(match_amount * sell_order.unit_price, 2)

            if player.money < total_price:
                match_amount = int(player.money // sell_order.unit_price)
                total_price = round(match_amount * sell_order.unit_price, 2)

            if match_amount <= 0:
                break

            # Geld abziehen
            player.money -= total_price
            await add_item(user_id, server_id, item_tag, match_amount)

            if sell_order.is_company:
                company = await session.scalar(
                    select(Company).where(
                        Company.entrepreneur_id == sell_order.user_id,
                        Company.server_id == server_id
                    )
                )
                if company:
                    company.capital += total_price
                    await add_owed_taxes(user_id=company.entrepreneur_id, server_id=server_id,
                                         amount=total_price, is_company=True)
                else:
                    await session.delete(sell_order)
                    await session.commit()
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Sell Order Removed",
                            description="The company for one of the sell orders no longer exists. Sell order removed.",
                            color=discord.Color.orange()
                        )
                    )
                    continue
            else:
                seller = await session.scalar(
                    select(Player).where(Player.id == sell_order.user_id, Player.server_id == server_id)
                )
                if seller:
                    seller.money += total_price
                    await add_owed_taxes(user_id=seller.id, server_id=server_id,
                                         amount=total_price, is_company=False)
                    try:
                        user_obj = await interaction.client.fetch_user(sell_order.user_id)
                        await user_obj.send(embed=discord.Embed(
                            title="Sell Order Fulfilled",
                            description=f"Your sell order for **{match_amount}x {item_tag}** was fulfilled for **${total_price:.2f}**.",
                            color=discord.Color.green()
                        ))
                    except discord.Forbidden:
                        pass

            if sell_order.amount == match_amount:
                await session.delete(sell_order)
            else:
                sell_order.amount -= match_amount

            fulfilled_total += match_amount
            total_spent += total_price
            amount -= match_amount

            await session.commit()



            if amount == 0:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Buy Order Fulfilled",
                        description=f"You bought **{fulfilled_total}x {item_tag}** from player orders for **${total_spent:.2f}**.",
                        color=discord.Color.green()
                    )
                )
                return

        if fulfilled_total > 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Buy Order Partially Fulfilled",
                    description=f"You bought **{fulfilled_total}x {item_tag}** from player orders for **${total_spent:.2f}**.",
                    color=discord.Color.green()
                )
            )

        # NPC-Markt?
        if amount > 0 and unit_price >= market_entry.max_price and market_entry.stockpile > 0:
            print("    Trying to buy from NPC market")
            purchasable_amount = min(market_entry.stockpile, amount)
            total_price = round(purchasable_amount * market_entry.max_price, 2)

            if player.money < total_price:
                await interaction.user.send(
                    embed=discord.Embed(
                        title="Buy Order Cancelled",
                        description=(
                            f"Insufficient funds to fulfill the rest of the order from the NPC market.\n"
                            f"Required: **${total_price}**, Available: **${player.money}**"
                        ),
                        color=discord.Color.red()
                    )
                )
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Order Cancelled",
                        description="You didn't have enough money for the NPC purchase. Check DMs.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                await session.commit()
                return

            player.money -= total_price
            await add_item(user_id, server_id, item_tag, purchasable_amount)
            market_entry.stockpile -= purchasable_amount



            await session.commit()

            await interaction.followup.send(
                embed=discord.Embed(
                    title="NPC Market Purchase",
                    description=f"You bought **{purchasable_amount}x {item_tag}** from the NPC market for **${market_entry.max_price:.2f}** each. Total: **${total_price:.2f}**.",
                    color=discord.Color.green()
                )
            )

            # Preis anpassen
            factor = 1 + 0.005 * purchasable_amount
            market_entry.min_price = round(market_entry.min_price * factor, 2)
            market_entry.max_price = round(market_entry.max_price * factor, 2)
            return

        # Nicht vollständig erfüllt → neue BuyOrder anlegen
        if amount > 0:
            new_order = BuyOrder(
                user_id=user_id,
                item_tag=item_tag,
                server_id=server_id,
                amount=amount,
                unit_price=unit_price,
                expires_at=expires_at,
                is_company=False
            )
            session.add(new_order)
            await session.commit()

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Buy Order Placed",
                    description=f"A buy order for **{amount}x {item_tag}** at **${unit_price:.2f}** has been created.",
                    color=discord.Color.green()
                )
            )











@client.tree.command(
    name="sell",
    description="Sell items by placing a sell order.",
    guild=guild_id
)
@app_commands.describe(
    item="The item you want to sell",
    unit_price="Price you're selling for per unit",
    amount="How many you want to sell (default: 1)"
)
async def sell(
    interaction: discord.Interaction,
    item: str,
    unit_price: float,
    amount: int = 1
):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /sell item:{item}, unit_price:{unit_price}, amount:{amount}")

    if amount <= 0 or unit_price <= 0:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error!",
                description="Amount and unit price must be greater than 0.",
                color=discord.Color.red()
            ), ephemeral=True
        )
        return

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        now = datetime.now()
        expires_at = now + SELL_ORDER_DURATION

        # Item prüfen
        item_obj = await session.scalar(select(Item).where(func.lower(Item.item_tag) == item.lower()))
        if not item_obj:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description=f"Item **{item}** does not exist.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return
        item_tag = item_obj.item_tag

        # Player prüfen
        player = await session.scalar(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )
        if not player:
            player = Player(id=user_id, server_id=server_id, money=100.0, debt=0.0, hunger=100, thirst=100, health=100, job=None, created_at=datetime.now())
            session.add(player)
            await session.commit()

        # Inventar prüfen
        inv_item = await session.scalar(
            select(PlayerItem).where(
                PlayerItem.user_id == user_id,
                PlayerItem.server_id == server_id,
                PlayerItem.item_tag == item_tag
            )
        )
        if not inv_item or inv_item.amount < amount:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description=f"You don't have enough **{item_tag}**.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Bestehende SellOrder checken
        now = datetime.now()
        expires_at = now + SELL_ORDER_DURATION

        existing_order = await session.scalar(
            select(SellOrder).where(
                SellOrder.user_id == user_id,
                SellOrder.item_tag == item_tag,
                SellOrder.server_id == server_id,
                SellOrder.unit_price == unit_price,
                SellOrder.is_company == False,
            )
        )

        if existing_order:
            existing_order.amount += amount
            existing_order.expires_at = expires_at
            await session.commit()

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Sell Order Merged",
                    description=(
                        f"Merged your sell orders for **{item_tag}** at **${unit_price}**.\n"
                        f"New total: **{existing_order.amount}x {item_tag}** = **${existing_order.amount * unit_price}**."
                    ),
                    color=discord.Color.green()
                )
            )
            return

        # Abziehen
        inv_item.amount -= amount
        if inv_item.amount <= 0:
            await session.delete(inv_item)

        await session.commit()

        # Buy Orders abrufen
        buy_orders = (await session.execute(
            select(BuyOrder).where(
                BuyOrder.item_tag == item_tag,
                BuyOrder.server_id == server_id,
                BuyOrder.unit_price >= unit_price,
                BuyOrder.expires_at > now
            ).order_by(BuyOrder.unit_price.desc())
        )).scalars().all()

        total_sold = 0
        total_earned = 0.0

        for buy_order in buy_orders:
            if total_sold >= amount:
                break

            buyer_money = None
            company = None

            if buy_order.is_company:
                company = await session.scalar(
                    select(Company).where(
                        Company.entrepreneur_id == buy_order.user_id,
                        Company.server_id == server_id
                    )
                )
                if not company:
                    await session.delete(buy_order)
                    continue
                buyer_money = company.capital
            else:
                buyer = await session.scalar(
                    select(Player).where(
                        Player.id == buy_order.user_id,
                        Player.server_id == server_id
                    )
                )
                if not buyer:
                    continue
                buyer_money = buyer.money

            if buyer_money < unit_price:
                continue

            sell_qty = min(buy_order.amount, amount - total_sold)
            total_price = round(sell_qty * unit_price, 2)

            if buyer_money < total_price:
                sell_qty = int(buyer_money // unit_price)
                total_price = round(sell_qty * unit_price, 2)

            if sell_qty <= 0:
                continue

            # Validierung + Transaktion
            if buy_order.is_company:
                company_result = await session.execute(
                    select(Company).where(
                        Company.entrepreneur_id == buy_order.user_id,
                        Company.server_id == server_id
                    )
                )
                company = company_result.scalar_one_or_none()

                if not company:
                    # Firma existiert nicht mehr → Order löschen, Verkauf überspringen
                    await session.delete(buy_order)
                    continue

                if company.capital < total_price:
                    continue  # Firma hat nicht genug Geld → überspringen

                # Transaktion Firma → Verkäufer
                company.capital -= total_price
                player.money += total_price
                await add_owed_taxes(user_id=player.id, server_id=server_id,
                                     amount=total_price, is_company=False)
                await add_item(buy_order.user_id, server_id, item_tag, sell_qty, is_company=True)

            else:
                # Käufer prüfen
                buyer_result = await session.execute(
                    select(Player).where(
                        Player.id == buy_order.user_id,
                        Player.server_id == server_id
                    )
                )
                buyer = buyer_result.scalar_one_or_none()
                if not buyer or buyer.money < total_price:
                    continue

                # Transaktion Käufer → Verkäufer
                buyer.money -= total_price
                player.money += total_price
                await add_owed_taxes(user_id=player.id, server_id=server_id,
                                     amount=total_price, is_company=False)
                await add_item(buy_order.user_id, server_id, item_tag, sell_qty)

            # Buy Order anpassen oder löschen
            buy_order.amount -= sell_qty
            if buy_order.amount <= 0:
                await session.delete(buy_order)

            total_sold += sell_qty
            total_earned += total_price

            embed = discord.Embed(
                title="Buy Order Fulfilled",
                description=f"Your buy order of **{sell_qty}x {item_tag}** at **${unit_price:.2f}** each was successful (Total: **${total_price:.2f}**).",
                color=discord.Color.green()
            )
            try:
                buyer_user = await interaction.client.fetch_user(buy_order.user_id)
                await buyer_user.send(embed=embed)
            except discord.Forbidden:
                pass

        # NPC-Markt
        if total_sold < amount:
            remaining = amount - total_sold
            market_entry = await session.scalar(
                select(MarketItem).where(
                    MarketItem.item_tag == item_tag,
                    MarketItem.server_id == server_id
                )
            )
            if not market_entry:
                await initialize_market_for_server(server_id)
                market_entry = await session.scalar(
                    select(MarketItem).where(
                        MarketItem.item_tag == item_tag,
                        MarketItem.server_id == server_id
                    )
                )

            if unit_price <= market_entry.min_price and market_entry.stockpile >= remaining:
                npc_sell_qty = remaining
                price = market_entry.min_price
                total_price = round(npc_sell_qty * price, 2)

                player.money += total_price
                market_entry.stockpile += npc_sell_qty
                await add_owed_taxes(user_id=player.id, server_id=server_id,
                                     amount=total_price, is_company=False)



                total_sold += npc_sell_qty
                total_earned += total_price

                await interaction.followup.send(
                    embed=discord.Embed(
                        title="NPC Market Sale",
                        description=(f"You sold **{npc_sell_qty}x {item_tag}** to the NPC market for **${price:.2f}** each (Total: **${total_price:.2f}**)."),
                        color=discord.Color.green()
                    )
                )

                # Preis leicht senken
                factor = 1 - (0.005 * npc_sell_qty)
                market_entry.max_price = round(market_entry.max_price * factor, 2)
                market_entry.min_price = round(market_entry.min_price * factor, 2)



                await session.commit()
                return

        if total_sold < amount:
            rest = amount - total_sold
            new_order = SellOrder(
                user_id=user_id,
                item_tag=item_tag,
                server_id=server_id,
                amount=rest,
                unit_price=unit_price,
                expires_at=expires_at,
                is_company=False
            )
            session.add(new_order)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Sell Order Placed",
                    description=f"Your sell order for **{rest}x {item_tag}** at **${unit_price:.2f}** has been created.",
                    color=discord.Color.green()
                )
            )

        if total_sold > 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Player Market Sale",
                    description=f"You sold **{total_sold}x {item_tag}** for **${total_earned:.2f}** total.",
                    color=discord.Color.green()
                )
            )

        await session.commit()










# CommandGroup Definition
class OrderCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="order", description="Manage your market orders")

    @app_commands.command(name="view", description="View buy and sell orders")
    @app_commands.describe(user="(Optional) View orders of another user")
    async def view(self, interaction: discord.Interaction, user: discord.User | None = None):
        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /order view user:{user}")

        target_user = user or interaction.user
        user_id = int(target_user.id)
        server_id = int(interaction.guild.id)
        now = datetime.now()

        async for session in get_session():
            buy_orders = (await session.execute(
                select(BuyOrder).where(
                    BuyOrder.user_id == user_id,
                    BuyOrder.server_id == server_id,
                    BuyOrder.expires_at > now
                ).order_by(BuyOrder.item_tag, BuyOrder.unit_price)
            )).scalars().all()

            sell_orders = (await session.execute(
                select(SellOrder).where(
                    SellOrder.user_id == user_id,
                    SellOrder.server_id == server_id,
                    SellOrder.expires_at > now
                ).order_by(SellOrder.item_tag, SellOrder.unit_price)
            )).scalars().all()

            embed = discord.Embed(
                title=f"{target_user.display_name}'s Active Orders",
                color=discord.Color.yellow()
            )

            if buy_orders:
                embed.add_field(
                    name="Buy Orders",
                    value="\n".join([
                        f"{'🏭 ' if o.is_company else ''}"
                        f"{o.amount}x {o.item_tag} @ ${o.unit_price:.2f} "
                        f"(expires <t:{int(o.expires_at.timestamp())}:R>)"
                        for o in buy_orders
                    ]),
                    inline=False
                )
            else:
                embed.add_field(name="Buy Orders", value="None", inline=False)

            if sell_orders:
                embed.add_field(
                    name="Sell Orders",
                    value="\n".join([
                        f"{'🏭 ' if o.is_company else ''}"
                        f"{o.amount}x {o.item_tag} @ ${o.unit_price:.2f} "
                        f"(expires <t:{int(o.expires_at.timestamp())}:R>)"
                        for o in sell_orders
                    ]),
                    inline=False
                )
            else:
                embed.add_field(name="Sell Orders", value="None", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=(user is None))

    @app_commands.command(name="remove", description="Remove one or multiple orders")
    @app_commands.describe(
        item_tag="The item tag of the order(s) to remove",
        price="(Optional) Only remove order at this exact price"
    )
    async def remove(self, interaction: discord.Interaction, item_tag: str, price: float | None = None):
        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /order remove item_tag:{item_tag}, price:{price}")

        user_id = int(interaction.user.id)
        server_id = int(interaction.guild.id)

        async for session in get_session():
            # Erst alle passenden SellOrders laden
            sell_orders = (await session.execute(
                select(SellOrder).where(
                    SellOrder.user_id == user_id,
                    SellOrder.server_id == server_id,
                    SellOrder.item_tag == item_tag,
                    SellOrder.unit_price == price if price is not None else True
                )
            )).scalars().all()

            # Items zurückgeben
            total_returned = 0
            for order in sell_orders:
                if order.is_company:
                    # Gib Items der Firma zurück
                    company = await session.scalar(select(Company).where(
                        Company.entrepreneur_id == user_id,
                        Company.server_id == server_id
                    ))
                    if company:
                        await add_item(
                            user_id=user_id,
                            server_id=server_id,
                            item_tag=item_tag,
                            amount=order.amount,
                            is_company=True
                        )
                else:
                    # Gib Items dem Spieler zurück
                    await add_item(
                        user_id=user_id,
                        server_id=server_id,
                        item_tag=item_tag,
                        amount=order.amount,
                        is_company=False
                    )
                total_returned += order.amount

            # Dann alle passenden BuyOrders löschen
            deleted_buy = await session.execute(
                delete(BuyOrder)
                .where(
                    BuyOrder.user_id == user_id,
                    BuyOrder.server_id == server_id,
                    BuyOrder.item_tag == item_tag,
                    BuyOrder.unit_price == price if price is not None else True
                )
            )

            # Und alle passenden SellOrders löschen
            deleted_sell = await session.execute(
                delete(SellOrder)
                .where(
                    SellOrder.user_id == user_id,
                    SellOrder.server_id == server_id,
                    SellOrder.item_tag == item_tag,
                    SellOrder.unit_price == price if price is not None else True
                )
            )

            await session.commit()

            if deleted_buy.rowcount == 0 and deleted_sell.rowcount == 0:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description=f"No matching orders found for `{item_tag}`{' at $' + str(price) if price else ''}.",
                        color=discord.Color.red()
                    )
                )
            else:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Orders Removed",
                        description=f"Deleted **{deleted_buy.rowcount}** buy order(s) and **{deleted_sell.rowcount}** sell order(s) for `{item_tag}`{' at $' + str(price) if price else ''}.\n"
                                    f"Returned **{total_returned}x {item_tag}** to your inventory.",
                        color=discord.Color.green()
                    )
                )


class CompanyGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="company", description="Used to do certain actions in the company you're working in")

    @app_commands.command(name="sell", description="Sell ONE item from the company stockpile to the market")
    @app_commands.describe(
        item="The item you want to sell",
        unit_price="Price you're selling for per unit",
    )
    async def company_sell(
            self,
            interaction: discord.Interaction,
            item: str,
            unit_price: float,
            amount: int = 1
    ):

        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /company sell item:{item}, unit_price:{unit_price}, amount:{amount}")


        if amount <= 0 or unit_price <= 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description="Amount and Unit price must be greater than 0.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return
        
        if amount > 10:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description="You may not sell more than 10 items at once.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        user_id = int(interaction.user.id)
        server_id = int(interaction.guild.id)



        async for session in get_session():

            # Item prüfen
            item_obj = await session.scalar(select(Item).where(func.lower(Item.item_tag) == item.lower()))
            if not item_obj:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description=f"Item **{item}** does not exist.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                return
            item_tag = item_obj.item_tag

            # Company prüfen
            company = await session.scalar(
                select(Company).where(Company.entrepreneur_id == user_id, Company.server_id == server_id)
            )
            if not company:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="You Don't Own A Company!",
                        description=f"To use /company commands, you need to own a company first. Try using /company create.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                return

            # Inventar prüfen
            inv_item = await session.scalar(
                select(CompanyItem).where(
                    CompanyItem.company_entrepreneur_id == user_id,
                    CompanyItem.server_id == server_id,
                    CompanyItem.item_tag == item_tag
                )
            )
            if not inv_item or inv_item.amount < amount:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description=f"Your company doesn't have enough **{item_tag}**.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                return

            result = await session.execute(
                select(Player).where(Player.id == user_id, Player.server_id == server_id)
            )
            player = result.scalar_one_or_none()
            if not player or player.job != "Entrepreneur":
                embed = discord.Embed(
                    title="Error!",
                    description="You are not an entrepreneur!",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if player.hunger <= 0 or player.thirst <= 0:
                embed = discord.Embed(
                    title="Error!",
                    description="You are too hungry or thirsty to work!",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if player.hunger <= amount * 5 or player.thirst <= amount * 7.5:
                embed = discord.Embed(
                    title="Error!",
                    description=f"To sell {amount} items, you need at least {5 * amount} hunger and {7.5 * amount} thirst.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            now = datetime.now()

            if player.work_cooldown_until and player.work_cooldown_until > now:
                ts = int(player.work_cooldown_until.timestamp())
                embed = discord.Embed(
                    title="Cooldown Active",
                    description=f"You can work again <t:{ts}:R>.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Abziehen
            inv_item.amount -= amount
            if inv_item.amount <= 0:
                await session.delete(inv_item)

            # Update hunger/thirst/cooldown
            old_hunger = player.hunger
            old_thirst = player.thirst
            player.hunger = max(0, player.hunger - amount * get_hunger_depletion())
            player.thirst = max(0, player.thirst - amount * get_thirst_depletion())
            player.work_cooldown_until = now + WORK_COOLDOWN
            await session.commit()

            # Bestehende SellOrder checken
            now = datetime.now()
            expires_at = now + BUY_ORDER_DURATION

            existing_order = await session.scalar(
                select(SellOrder).where(
                    SellOrder.user_id == user_id,
                    SellOrder.item_tag == item_tag,
                    SellOrder.server_id == server_id,
                    SellOrder.unit_price == unit_price,
                    SellOrder.is_company == True
                )
            )

            if existing_order:
                print("Merging orders")
                existing_order.amount += amount
                existing_order.expires_at = expires_at
                await session.commit()
                embed = discord.Embed(
                    title="Company Sell Order Merged",
                    description=(
                        f"Merged your company sell orders for **{item_tag}** at **${unit_price}**.\n"
                        f"New total: **{existing_order.amount}x {item_tag}** = **${existing_order.amount * unit_price}**."
                    ),
                    color=discord.Color.green()
                )
                embed.add_field(name="Hunger", value=f"{old_hunger} -> {player.hunger}")
                embed.add_field(name="Thirst", value=f"{old_thirst} -> {player.thirst}")
                await interaction.followup.send(embed=embed)
                return


            # Abziehen
            inv_item.amount -= amount
            if inv_item.amount <= 0:
                await session.delete(inv_item)

            # Buy Orders abrufen
            buy_orders = (await session.execute(
                select(BuyOrder).where(
                    BuyOrder.item_tag == item_tag,
                    BuyOrder.server_id == server_id,
                    BuyOrder.unit_price >= unit_price,
                    BuyOrder.expires_at > now
                ).order_by(BuyOrder.unit_price.desc())
            )).scalars().all()

            total_sold = 0
            total_earned = 0.0






            for buy_order in buy_orders:
                if total_sold >= amount:
                    break

                buyer_money = None
                company_seller = None


                sell_qty = min(buy_order.amount, amount - total_sold)
                total_price = round(sell_qty * unit_price, 2)

                # Validierung + Transaktion
                if buy_order.is_company:
                    company_result = await session.execute(
                        select(Company).where(
                            Company.entrepreneur_id == buy_order.user_id,
                            Company.server_id == server_id
                        )
                    )
                    company_buyer = company_result.scalar_one_or_none()

                    if not company_buyer:
                        # Firma existiert nicht mehr → Order löschen, Verkauf überspringen
                        await session.delete(buy_order)
                        continue

                    if company_buyer.capital < total_price:
                        continue  # Firma hat nicht genug Geld → überspringen

                    # Transaktion Firma → Verkäufer
                    company_buyer.capital -= total_price
                    company.capital += total_price
                    await add_owed_taxes(user_id=company.entrepreneur_id, server_id=server_id,
                                         amount=total_price, is_company=True)
                    await add_item(buy_order.user_id, server_id, item_tag, sell_qty, True)

                else:
                    # Käufer prüfen
                    buyer_result = await session.execute(
                        select(Player).where(
                            Player.id == buy_order.user_id,
                            Player.server_id == server_id
                        )
                    )
                    buyer = buyer_result.scalar_one_or_none()
                    if not buyer or buyer.money < total_price:
                        continue



                    if buyer.money < total_price:
                        sell_qty = int(buyer.money // unit_price)
                        total_price = round(sell_qty * unit_price, 2)

                    if sell_qty <= 0:
                        continue

                    # Transaktion Käufer → Verkäufer
                    buyer.money -= total_price
                    company.capital += total_price
                    await add_owed_taxes(user_id=company.entrepreneur_id, server_id=server_id,
                                         amount=total_price, is_company=True)
                    await add_item(buy_order.user_id, server_id, item_tag, sell_qty)

                # Buy Order anpassen oder löschen
                buy_order.amount -= sell_qty
                if buy_order.amount <= 0:
                    await session.delete(buy_order)

                total_sold += sell_qty
                total_earned += total_price

                embed = discord.Embed(
                    title="Buy Order Fulfilled",
                    description=f"Your buy order of **{sell_qty}x {item_tag}** at **${unit_price:.2f}** each was successful (Total: **${total_price:.2f}**).",
                    color=discord.Color.green()
                )
                try:
                    buyer_user = await interaction.client.fetch_user(buy_order.user_id)
                    await buyer_user.send(embed=embed)
                except discord.Forbidden:
                    pass

            # NPC-Markt
            if total_sold < amount:
                remaining = amount - total_sold
                market_entry = await session.scalar(
                    select(MarketItem).where(
                        MarketItem.item_tag == item_tag,
                        MarketItem.server_id == server_id
                    )
                )
                if not market_entry:
                    await initialize_market_for_server(server_id)
                    market_entry = await session.scalar(
                        select(MarketItem).where(
                            MarketItem.item_tag == item_tag,
                            MarketItem.server_id == server_id
                        )
                    )

                if unit_price <= market_entry.min_price and market_entry.stockpile >= remaining:
                    npc_sell_qty = remaining
                    price = market_entry.min_price
                    total_price = round(npc_sell_qty * price, 2)

                    company.capital += total_price
                    market_entry.stockpile += npc_sell_qty
                    await add_owed_taxes(user_id=company.entrepreneur_id, server_id=server_id,
                                         amount=total_price, is_company=True)

                    total_sold += npc_sell_qty
                    total_earned += total_price
                    embed = discord.Embed(
                        title="NPC Market Sale",
                        description=(
                            f"You sold **{npc_sell_qty}x {item_tag}** to the NPC market for **${price:.2f}** each (Total: **${total_price:.2f}**)."),
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Hunger", value=f"{old_hunger} -> {player.hunger}")
                    embed.add_field(name="Thirst", value=f"{old_thirst} -> {player.thirst}")
                    await interaction.followup.send(embed=embed)

                    # Preis leicht senken
                    factor = 1 - (0.005 * npc_sell_qty)
                    market_entry.max_price = round(market_entry.max_price * factor, 2)
                    market_entry.min_price = round(market_entry.min_price * factor, 2)

                    await session.commit()
                    return

            if total_sold < amount:
                print("Creating new Sell Order")
                rest = amount - total_sold
                new_order = SellOrder(
                    user_id=user_id,
                    item_tag=item_tag,
                    server_id=server_id,
                    amount=rest,
                    unit_price=unit_price,
                    expires_at=expires_at,
                    is_company=True
                )
                session.add(new_order)
                embed = discord.Embed(
                        title="Company Sell Order Placed",
                        description=f"Your sell order for **{rest}x {item_tag}** at **${unit_price:.2f}** has been created.",
                        color=discord.Color.green()
                    )
                embed.add_field(name="Hunger", value=f"{old_hunger} -> {player.hunger}")
                embed.add_field(name="Thirst", value=f"{old_thirst} -> {player.thirst}")
                await interaction.followup.send(embed=embed)

            if total_sold > 0:
                embed = discord.Embed(
                    title="Company Player Market Sale",
                    description=f"You sold **{total_sold}x {item_tag}** for **${total_earned:.2f}** total.",
                    color=discord.Color.green()
                )
                embed.add_field(name="Hunger", value=f"{old_hunger} -> {player.hunger}")
                embed.add_field(name="Thirst", value=f"{old_thirst} -> {player.thirst}")
                await interaction.followup.send(embed=embed)

            await session.commit()

    @app_commands.command(name="buy", description="Buy items from the market")
    @app_commands.describe(
        item="The item you want to buy",
        unit_price="Maximum price you're willing to pay per unit",
        amount="How many you want to buy (default: 1)"
    )
    async def company_buy(
            self,
            interaction: discord.Interaction,
            item: str,
            unit_price: float,
            amount: int = 1
    ):
        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /company buy item: {item}, unit_price: {unit_price}, amount: {amount}")

        if amount <= 0 or unit_price <= 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description="Amount and unit price must be greater than 0.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        user_id = int(interaction.user.id)
        server_id = int(interaction.guild.id)
        async for session in get_session():
            try:
                # Item prüfen
                item_obj = await session.scalar(select(Item).where(func.lower(Item.item_tag) == item.lower()))
                if not item_obj:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Error!",
                            description=f"Item **{item}** does not exist.",
                            color=discord.Color.red()
                        ), ephemeral=True
                    )
                    return
                item_tag = item_obj.item_tag

                # Company laden
                company = await session.scalar(
                    select(Company).where(Company.entrepreneur_id == user_id, Company.server_id == server_id)
                )
                if not company:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="You Don't Own A Company!",
                            description=f"To use /company commands, you need to own a company first. Try using /company create.",
                            color=discord.Color.red()
                        ), ephemeral=True
                    )
                    return

                if company.capital < unit_price * amount:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Not Enough Money!",
                            description=f"You are trying to buy **{amount}x {item_tag}** for **${(unit_price * amount):.2f}**, but your company only has **${company.capital:.2f}**.",
                            color=discord.Color.red()
                        ), ephemeral=True
                    )
                    return

                # Bestehende BuyOrder checken
                now = datetime.now()
                expires_at = now + BUY_ORDER_DURATION

                existing_order = await session.scalar(
                    select(BuyOrder).where(
                        BuyOrder.user_id == user_id,
                        BuyOrder.item_tag == item_tag,
                        BuyOrder.server_id == server_id,
                        BuyOrder.unit_price == unit_price,
                        BuyOrder.is_company == True
                    )
                )

                if existing_order:
                    existing_order.amount += amount
                    existing_order.expires_at = expires_at
                    await session.commit()

                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Company Buy Order Merged",
                            description=(
                                f"Merged your company buy orders for **{item_tag}** at **${unit_price}**.\n"
                                f"New total: **{existing_order.amount}x {item_tag}** = **${existing_order.amount * unit_price}**."
                            ),
                            color=discord.Color.green()
                        )
                    )
                    return

                # Markt initialisieren, falls nötig
                market_entry = await session.scalar(
                    select(MarketItem).where(MarketItem.item_tag == item_tag, MarketItem.server_id == server_id)
                )
                if not market_entry:
                    await initialize_market_for_server(server_id)
                    market_entry = await session.scalar(
                        select(MarketItem).where(MarketItem.item_tag == item_tag, MarketItem.server_id == server_id)
                    )

                # SELL-Orders finden
                fulfilled_total = 0
                total_spent = 0.0

                sell_orders = (await session.execute(
                    select(SellOrder).where(
                        SellOrder.item_tag == item_tag,
                        SellOrder.server_id == server_id,
                        SellOrder.unit_price <= unit_price,
                        SellOrder.expires_at > now
                    ).order_by(SellOrder.unit_price.asc())
                )).scalars().all()

                for sell_order in sell_orders:
                    if company.capital < sell_order.unit_price:
                        break

                    match_amount = min(amount, sell_order.amount)
                    total_price = round(match_amount * sell_order.unit_price, 2)

                    if company.capital < total_price:
                        match_amount = int(company.capital // sell_order.unit_price)
                        total_price = round(match_amount * sell_order.unit_price, 2)

                    if match_amount <= 0:
                        break

                    # Geld abziehen
                    company.capital -= total_price
                    await add_item(user_id, server_id, item_tag, match_amount, True)

                    if sell_order.is_company:
                        company_seller = await session.scalar(
                            select(Company).where(
                                Company.entrepreneur_id == sell_order.user_id,
                                Company.server_id == server_id
                            )
                        )
                        if company_seller:
                            company_seller.capital += total_price
                            await add_owed_taxes(user_id=company_seller.entrepreneur_id, server_id=server_id, amount=total_price, is_company=True)

                        else:
                            await session.delete(sell_order)
                            await session.commit()
                            await interaction.followup.send(
                                embed=discord.Embed(
                                    title="Sell Order Removed",
                                    description="The company for one of the sell orders no longer exists. Sell order removed.",
                                    color=discord.Color.orange()
                                )
                            )
                            continue
                    else:
                        seller = await session.scalar(
                            select(Player).where(Player.id == sell_order.user_id, Player.server_id == server_id)
                        )
                        if seller:
                            seller.money += total_price
                            await add_owed_taxes(user_id=seller.id, server_id=server_id,
                                                 amount=total_price, is_company=False)
                            try:
                                user_obj = await interaction.client.fetch_user(sell_order.user_id)
                                await user_obj.send(embed=discord.Embed(
                                    title="Sell Order Fulfilled",
                                    description=f"Your sell order for **{match_amount}x {item_tag}** was fulfilled for **${total_price:.2f}**.",
                                    color=discord.Color.green()
                                ))
                            except discord.Forbidden:
                                pass

                    if sell_order.amount == match_amount:
                        await session.delete(sell_order)
                    else:
                        sell_order.amount -= match_amount

                    fulfilled_total += match_amount
                    total_spent += total_price
                    amount -= match_amount

                    await session.commit()

                    if amount == 0:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="Company Buy Order Fulfilled",
                                description=f"You bought **{fulfilled_total}x {item_tag}** from player orders for **${total_spent:.2f}**.",
                                color=discord.Color.green()
                            )
                        )
                        return

                if fulfilled_total > 0:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Buy Order Partially Fulfilled",
                            description=f"You bought **{fulfilled_total}x {item_tag}** from player orders for **${total_spent:.2f}**.",
                            color=discord.Color.green()
                        )
                    )

                # NPC-Markt?
                if amount > 0 and unit_price >= market_entry.max_price and market_entry.stockpile > 0:
                    purchasable_amount = min(market_entry.stockpile, amount)
                    total_price = round(purchasable_amount * market_entry.max_price, 2)

                    if company.capital < total_price:
                        await interaction.user.send(
                            embed=discord.Embed(
                                title="Company Buy Order Cancelled",
                                description=(
                                    f"Insufficient funds to fulfill the rest of the order from the NPC market.\n"
                                    f"Required: **${total_price}**, Available: **${company.capital}**"
                                ),
                                color=discord.Color.red()
                            )
                        )
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="Order Cancelled",
                                description="You didn't have enough money for the NPC purchase. Check DMs.",
                                color=discord.Color.red()
                            ), ephemeral=True
                        )
                        await session.commit()
                        return

                    company.capital -= total_price
                    await add_item(user_id, server_id, item_tag, purchasable_amount, is_company=True)
                    market_entry.stockpile -= purchasable_amount



                    await session.commit()

                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="NPC Market Purchase",
                            description=f"You bought **{purchasable_amount}x {item_tag}** from the NPC market for **${(total_price/purchasable_amount):.2f}** each. Total: **${total_price:.2f}**.",
                            color=discord.Color.green()
                        )
                    )

                    # Preis anpassen
                    factor = 1 + 0.005 * purchasable_amount
                    market_entry.min_price = round(market_entry.min_price * factor, 2)
                    market_entry.max_price = round(market_entry.max_price * factor, 2)
                    return

                # Nicht vollständig erfüllt → neue BuyOrder anlegen
                if amount > 0:
                    new_order = BuyOrder(
                        user_id=user_id,
                        item_tag=item_tag,
                        server_id=server_id,
                        amount=amount,
                        unit_price=unit_price,
                        expires_at=expires_at,
                        is_company=True
                    )
                    session.add(new_order)
                    await session.commit()

                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Company Buy Order Placed",
                            description=f"A buy order for **{amount}x {item_tag}** at **${unit_price:.2f}** has been created.",
                            color=discord.Color.green()
                        )
                    )
            except Exception as e:
                await session.rollback()
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Internal Bot Error Occured",
                        description=e,
                        color=discord.Color.green()
                    )
                )


    @app_commands.command(
        name="info",
        description="View important info about your company."
    )
    async def info(self, interaction: discord.Interaction):
        print(f"{interaction.user}: /company info")
        await interaction.response.defer(thinking=True)

        target_user = interaction.user
        user_id = int(target_user.id)
        server_id = int(interaction.guild.id)

        async for session in get_session():
            # Primär: Firma direkt durch Eigentum suchen
            company = await session.scalar(
                select(Company).where(
                    Company.entrepreneur_id == user_id,
                    Company.server_id == server_id
                )
            )

            if not company:
                # Sekundär: prüfen, ob Spieler Arbeiter einer Firma ist
                player = await session.scalar(
                    select(Player).where(
                        Player.id == user_id,
                        Player.server_id == server_id
                    )
                )

                if not player or player.company_entrepreneur_id is None:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="No Company Found",
                            description="You don't own a company and you're not employed by one.",
                            color=discord.Color.red()
                        ), ephemeral=True
                    )
                    return

                # Firma über Arbeitgeber-ID laden
                company = await session.scalar(
                    select(Company).where(
                        Company.entrepreneur_id == player.company_entrepreneur_id,
                        Company.server_id == server_id
                    )
                )

                if not company:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Error",
                            description="The company you're working for could not be found.",
                            color=discord.Color.red()
                        ), ephemeral=True
                    )
                    return

                # Eigentümer (für Anzeige im Footer)
                target_user = await interaction.client.fetch_user(player.company_entrepreneur_id)

            # Embed bauen
            embed = discord.Embed(
                title=f"**{company.name}**" if company.name != "" else f"Company of **{target_user.name}**",
                color=discord.Color.yellow()
            )
            embed.add_field(name="Capital", value=f"${company.capital:.2f}", inline=True)
            embed.add_field(name="Wage", value=f"${company.wage:.2f}", inline=True)
            embed.add_field(name="Taxes Owed", value=f"${company.taxes_owed:.2f}", inline=True)
            embed.add_field(name="Producible Items",
                            value=company.producible_items.replace(",", ", ") if company.producible_items else "None",
                            inline=True)

            embed.set_footer(text=f"Entrepreneur: {target_user.name}")

            # Company-Mitarbeiter abfragen
            result_players = await session.execute(
                select(Player).where(
                    Player.company_entrepreneur_id == company.entrepreneur_id,
                    Player.server_id == server_id
                )
            )
            players = result_players.scalars().all()

            if players:
                employee_lines = []
                for player in players:
                    discord_player = await interaction.client.fetch_user(player.id)
                    line = f"{discord_player.name}"

                    employee_lines.append(line)
                employees_string = "\n".join(employee_lines)
                embed.add_field(name="Employees", value=employees_string, inline=False)
            else:
                embed.add_field(name="Employees", value="None", inline=False)

            # Company-Join-Anfragen abfragen
            result_requests = await session.execute(
                select(CompanyJoinRequest).where(
                    CompanyJoinRequest.company_entrepreneur_id == company.entrepreneur_id,
                    CompanyJoinRequest.server_id == server_id
                )
            )
            requests = result_requests.scalars().all()

            if requests:
                request_lines = []
                for request in requests:
                    discord_request = await interaction.client.fetch_user(request.user_id)
                    line = f"{discord_request.name}"

                    request_lines.append(line)
                requests_string = "\n".join(request_lines)
                embed.add_field(name="Join Requests", value=requests_string, inline=False)
            else:
                embed.add_field(name="Join Requests", value="None", inline=False)

            # Company-Inventar abfragen
            result_items = await session.execute(
                select(CompanyItem).where(
                    CompanyItem.company_entrepreneur_id == company.entrepreneur_id,
                    CompanyItem.server_id == server_id
                )
            )
            items = result_items.scalars().all()

            if items:
                inventory_lines = []
                for item in items:
                    line = f"{item.amount}x {item.item_tag}"
                    inventory_lines.append(line)
                inventory_str = "\n".join(inventory_lines)
                embed.add_field(name="Inventory", value=inventory_str, inline=False)
            else:
                embed.add_field(name="Inventory", value="Empty", inline=False)

            await interaction.followup.send(embed=embed)

    @app_commands.command(name="deposit", description="Deposit money to the company account")
    @app_commands.describe(value="The amount of money you want to deposit")
    async def deposit(self, interaction: discord.Interaction, value: float):
        print(f"{interaction.user}: /company deposit {value}")
        await interaction.response.defer(thinking=True)

        if value <= 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Invalid Amount",
                    description="Deposit amount must be greater than 0.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        user_id = int(interaction.user.id)
        server_id = int(interaction.guild.id)

        async for session in get_session():
            # Player prüfen
            player = await session.scalar(
                select(Player).where(Player.id == user_id, Player.server_id == server_id)
            )
            if not player:
                player = Player(
                    id=user_id,
                    server_id=server_id,
                    money=100.0,
                    debt=0.0,
                    hunger=100,
                    thirst=100,
                    health=100,
                    job=None,
                    created_at=datetime.now()
                )
                session.add(player)
                await session.commit()

            # Firma prüfen
            company = await session.scalar(
                select(Company).where(
                    Company.entrepreneur_id == user_id,
                    Company.server_id == server_id
                )
            )
            if not company:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="You Don't Own A Company!",
                        description=f"To use /company commands, you need to own a company first. Try using /company create.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                return

            # Geld prüfen
            if player.money < value:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Insufficient Funds",
                        description=f"You only have ${player.money:.2f}, but tried to deposit ${value:.2f}.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                return

            # Überweisung
            player.money -= value
            company.capital += value

            await session.commit()

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Deposit Successful",
                    description=f"✅ You deposited **${value:.2f}** into your company **{company.name}**",
                    color=discord.Color.green()
                )
            )

    @app_commands.command(name="withdraw", description="Withdraw money from the company account")
    @app_commands.describe(value="The amount of money you want to withdraw")
    async def withdraw(self, interaction: discord.Interaction, value: float):
        await interaction.response.defer(thinking=True)

        if value <= 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Invalid Amount",
                    description="Withdraw amount must be greater than 0.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        user_id = int(interaction.user.id)
        server_id = int(interaction.guild.id)

        async for session in get_session():
            # Player prüfen
            player = await session.scalar(
                select(Player).where(Player.id == user_id, Player.server_id == server_id)
            )
            if not player:
                player = Player(
                    id=user_id,
                    server_id=server_id,
                    money=100.0,
                    debt=0.0,
                    hunger=100,
                    thirst=100,
                    health=100,
                    job=None,
                    created_at=datetime.now()
                )
                session.add(player)
                await session.commit()

            # Firma prüfen
            company = await session.scalar(
                select(Company).where(
                    Company.entrepreneur_id == user_id,
                    Company.server_id == server_id
                )
            )
            if not company:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="You Don't Own A Company!",
                        description=f"To use /company commands, you need to own a company first. Try using /company create.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                return

            # Kapital prüfen
            if company.capital < value:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Insufficient Capital",
                        description=f"The company only has **${company.capital:.2f}**, but you tried to withdraw **${value:.2f}**.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                return

            # Überweisung
            company.capital -= value
            player.money += value

            await session.commit()

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Withdrawal Successful",
                    description=f"✅ You withdrew **${value:.2f}** from **{company.name}**'s account.",
                    color=discord.Color.green()
                )
            )

    @app_commands.command(name="create", description="Create a company if you don't have a job. Costs $1000")
    @app_commands.describe(name="The name of the company you want to create")
    async def create(self, interaction: discord.Interaction, name: str):
        print(f"{interaction.user}: /company withdraw {name}")
        await interaction.response.defer(thinking=True)

        user_id = int(interaction.user.id)
        server_id = int(interaction.guild.id)

        async for session in get_session():
            # Player laden oder erstellen
            player = await session.scalar(
                select(Player).where(Player.id == user_id, Player.server_id == server_id)
            )
            if not player:
                player = Player(
                    id=user_id,
                    server_id=server_id,
                    money=100.0,
                    debt=0.0,
                    hunger=100,
                    thirst=100,
                    health=100,
                    job=None,
                    created_at=datetime.now()
                )
                session.add(player)
                await session.commit()

            # Check: Hat bereits eine Firma?
            existing = await session.scalar(
                select(Company).where(
                    Company.entrepreneur_id == user_id,
                    Company.server_id == server_id
                )
            )
            if existing:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description="You already own a company.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                return

            # Check: Hat der Spieler bereits einen Job?
            if player.job:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description="You already have a job. To create a company, first quit your job using /job jobless.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                return

            # Check: Hat der Spieler genug Geld?
            if player.money < 1000:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Not Enough Money",
                        description="You need **$1000** to start a company.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                return



            # Geld abziehen
            player.money -= 1000

            # Firma erstellen
            company = Company(
                entrepreneur_id=user_id,
                server_id=server_id,
                name=name,
                capital=900.0,
                wage=100.0,
                producible_items="",  # optional später anpassen
                created_at=datetime.now(),
                taxes_owed=0
            )
            player.job = "Entrepreneur"
            session.add(company)

            await session.commit()

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Company Created",
                    description=f"✅ You successfully created the company **{name}**!",
                    color=discord.Color.green()
                )
            )

    @app_commands.command(name="disband", description="Disband your company (admins can disband others)")
    @app_commands.describe(user="The user whose company to disband (admins only)")
    async def disband(self, interaction: discord.Interaction, user: discord.Member | None = None):
        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /company disband {user}")

        executor_id = int(interaction.user.id)
        target_user = user or interaction.user
        target_user_id = int(target_user.id)
        server_id = int(interaction.guild.id)

        async for session in get_session():
            # Adminrechte prüfen, wenn Fremdfirma
            if user:
                gov = await session.scalar(select(Government).where(Government.id == server_id))
                if not gov:
                    gov = Government(
                        id=server_id,
                        created_at=datetime.utcnow,
                        taxrate=0.1,
                        interest_rate=0.3,
                        treasury=0,
                        governing_role=None,
                        admin_role=None
                    )
                    session.add(gov)
                    session.commit()

                roles = [role.id for role in interaction.user.roles]
                if gov.governing_role not in roles and gov.admin_role not in roles:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Error!",
                            description=f"You don't have permission to disband other companies.",
                            color=discord.Color.red()
                        ), ephemeral=True
                    )
                    return

            # Firma prüfen
            company = await session.scalar(
                select(Company).where(
                    Company.entrepreneur_id == target_user_id,
                    Company.server_id == server_id
                )
            )
            if not company:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description=f"{target_user.display_name} doesn't own a company.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                return

            # Player-Objekt holen und Job leeren
            player = await session.scalar(
                select(Player).where(
                    Player.id == target_user_id,
                    Player.server_id == server_id
                )
            )
            if player:
                player.job = ""

            player.money += company.capital

            # CompanyItems übertragen
            company_items = (await session.execute(
                select(CompanyItem).where(
                    CompanyItem.company_entrepreneur_id == target_user_id,
                    CompanyItem.server_id == server_id
                )
            )).scalars().all()

            for item in company_items:
                await add_item(
                    user_id=target_user_id,
                    server_id=server_id,
                    item_tag=item.item_tag,
                    amount=item.amount,
                    is_company=False
                )
                await session.delete(item)

            # Alle Spieler entkoppeln, die bei der Company angestellt waren
            await session.execute(
                update(Player)
                .where(
                    Player.company_entrepreneur_id == target_user_id,
                    Player.server_id == server_id
                )
                .values(company_entrepreneur_id=None, job="")
            )

            # Firma löschen
            await session.delete(company)
            await session.commit()

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Company Disbanded",
                    description=f"✅ Company **{company.name}** was disbanded.\nItems and remaining resources have been transferred to {target_user.display_name}.",
                    color=discord.Color.green()
                )
            )


@client.tree.command(
    name="setitems",
    description="RESETS WORK PROGRESS: Used by entrepreneurs to set what items the workers can produce. ",
    guild=guild_id
)
@app_commands.describe(
    item1="The first item you wish your company to produce",
    item2="The second item you wish your company to produce",
    item3="The third item you wish your company to produce",
    item4="The fourth item you wish your company to produce",
    item5="The fifth item you wish your company to produce"
)
async def setitems(interaction: discord.Interaction, item1: str, item2: str = "", item3: str = "", item4: str = "", item5: str = ""):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /setitems {item1} {item2} {item3} {item4} {item5}")
    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        company = await session.scalar(
            select(Company).where(
                Company.entrepreneur_id == user_id,
                Company.server_id == server_id
            )
        )

        if not company:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="You Don't Own A Company!",
                    description=f"To use /company commands, you need to own a company first. Try using /company create.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        input_items = [item1, item2, item3, item4, item5]
        raw_tags = []
        for item in input_items:
            if item != "":
                raw_tags.append(item)


        result = await session.execute(select(Item.item_tag).where(Item.producible == True))
        producible_tags = {row[0] for row in result.all()}

        # Validieren
        valid_tags = []
        invalid_tags = []
        for tag in raw_tags:
            if tag in producible_tags:
                valid_tags.append(tag)
            else:
                invalid_tags.append(tag)

        if invalid_tags:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Invalid Items",
                    description="These items are not producible: " + ", ".join(invalid_tags),
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Als String speichern
        company.producible_items = ",".join(valid_tags)
        company.worksteps = "0,0,0,0,0"
        await session.commit()

    await interaction.followup.send(
            embed=discord.Embed(
                title="Producible Items set!",
                description=f"The workers of your company can now produce " + ", ".join(valid_tags),
                color=discord.Color.green()
            )
        )











@client.tree.command(
    name="work",
    description="Used by workers to produce a certain item, if the ingredients are available.",
    guild=guild_id
)
@app_commands.describe(item="The item you want to produce")
async def work(interaction: discord.Interaction, item: str):
    print(f"{interaction.user}: /work {item}")
    await interaction.response.defer(thinking=True)

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        player = await session.scalar(select(Player).where(Player.id == user_id, Player.server_id == server_id))
        if not player or not player.job or player.job == "":
            await interaction.followup.send(
                embed=discord.Embed(title="Not Employed", description="You're not part of any company. Use /join <user-id> to request to join a player's company.", color=discord.Color.red()),
                ephemeral=True
            )
            return

        if player.job == "Entrepreneur":
            await interaction.followup.send(
                embed=discord.Embed(title="You Are The Entrepreneur", description="Only workers of your company can do /work. They can request to join your company using /join and you can accept them using /hire.",
                                    color=discord.Color.red()),
                ephemeral=True
            )
            return
        company = await session.scalar(select(Company).where(Company.entrepreneur_id == player.company_entrepreneur_id, Company.server_id == server_id))
        if not company:
            await interaction.followup.send(
                embed=discord.Embed(title="Company Missing", description="Your company does not exist anymore.", color=discord.Color.red()),
                ephemeral=True
            )
            return

        if player.hunger <= 0 or player.thirst <= 0:
            await interaction.followup.send(
                embed=discord.Embed(title="Too Exhausted", description="You are too hungry or thirsty to work!", color=discord.Color.red()),
                ephemeral=True
            )
            return

        now = datetime.now()

        # Cooldown check
        if player.work_cooldown_until and player.work_cooldown_until > now:
            cooldown_ts = int(player.work_cooldown_until.timestamp())
            await interaction.followup.send(embed=discord.Embed(
                title="Cooldown Active",
                description=f"⏳ You can work again <t:{cooldown_ts}:R>.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        # Werkzeuge prüfen
        has_tool = await has_item(user_id, server_id, "Tool")
        if not has_tool:
            await interaction.followup.send(embed=discord.Embed(
                title="Error!",
                description="You don't have a tool! How do you expect to work in a factory without it?",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        if company.capital < company.wage:
            await interaction.followup.send(embed=discord.Embed(
                title="Not Enough Company Capital",
                description="The Company does not have enough money to pay you, so why should you work?",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        company.capital -= company.wage
        player.money += company.wage
        await add_owed_taxes(user_id=player.id, server_id=server_id,
                             amount=company.wage, is_company=False)


        item_obj = await session.scalar(select(Item).where(func.lower(Item.item_tag) == item.lower()))
        if not item_obj or not item_obj.producible:
            await interaction.followup.send(
                embed=discord.Embed(title="Invalid Item", description=f"The item can't be produced.", color=discord.Color.red()),
                ephemeral=True
            )
            return

        allowed_tags = company.producible_items.split(",") if company.producible_items else []
        worksteps_list = [int(x) for x in (company.worksteps.split(",") if company.worksteps else ["0"] * 5)]

        if item not in allowed_tags:
            await interaction.followup.send(embed=discord.Embed(
                title="Error!",
                description="Your company does not allow you to produce this item.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        item_index = allowed_tags.index(item)
        item_obj = await session.scalar(select(Item).where(func.lower(Item.item_tag) == item.lower()))

        ingredients = {}
        if item_obj.ingredients:
            for entry in item_obj.ingredients.split(","):
                name, qty = entry.split(":")
                ingredients[name] = int(qty)

        # Wenn Worksteps = 0, dann Ressourcen prüfen und verbrauchen
        if worksteps_list[item_index] <= 0:
            for tag, required_amount in ingredients.items():
                company_item = await session.scalar(select(CompanyItem).where(
                    CompanyItem.company_entrepreneur_id == company.entrepreneur_id,
                    CompanyItem.server_id == server_id,
                    CompanyItem.item_tag == tag
                ))
                if not company_item or company_item.amount < required_amount:
                    await interaction.followup.send(embed=discord.Embed(
                        title="Not enough resources!",
                        description=f"You need: " + ", ".join(f"{v}x {k}" for k, v in ingredients.items()),
                        color=discord.Color.red()
                    ), ephemeral=True)
                    return

            # Ressourcen abziehen
            for tag, required_amount in ingredients.items():
                company_item = await session.scalar(select(CompanyItem).where(
                    CompanyItem.company_entrepreneur_id == company.entrepreneur_id,
                    CompanyItem.server_id == server_id,
                    CompanyItem.item_tag == tag
                ))
                company_item.amount -= required_amount

            worksteps_list[item_index] = item_obj.worksteps or 1  # Fallback auf 1

        # Workstep abziehen
        worksteps_list[item_index] -= 1
        company.worksteps = ",".join(str(x) for x in worksteps_list)

        # Werkzeug-Haltbarkeit reduzieren
        durability = await use_item(user_id, server_id, "Tool")

        # Update hunger/thirst/cooldown
        old_hunger = player.hunger
        old_thirst = player.thirst
        player.hunger = max(0, player.hunger - get_hunger_depletion())
        player.thirst = max(0, player.thirst - get_thirst_depletion())
        player.work_cooldown_until = now + WORK_COOLDOWN

        await session.commit()

        embed = discord.Embed(color=discord.Color.green())

        if worksteps_list[item_index] <= 0:
            # Item wurde fertiggestellt
            await add_item(user_id=company.entrepreneur_id, server_id=server_id, item_tag=item, amount=1,
                           is_company=True)
            embed.title = "Item Produced!"
            embed.description = f"You produced **1x {item}** for your company."
        else:
            embed.title = "Work Step Completed"
            embed.description = f"You worked on **{item}**. {worksteps_list[item_index]} steps remaining."
        embed.add_field(name="Money", value=f"${(player.money - company.wage):.2f} -> ${company.wage:.2f} -> ${player.money:.2f}")
        embed.add_field(name=f"Tool Durability", value=f"{durability} -> {durability - 1}")
        embed.add_field(name="Hunger", value=f"{old_hunger} -> {player.hunger}")
        embed.add_field(name="Thirst", value=f"{old_thirst} -> {player.thirst}")

        await interaction.followup.send(embed=embed)
        await session.commit()





@client.tree.command(
    name="join",
    description="Use this to ask to join a company",
    guild=guild_id
)
@app_commands.describe(user="The user who owns the company that you want to join")
async def join(interaction: discord.Interaction, user: discord.Member):
    print(f"{interaction.user}: /join {user}")
    await interaction.response.defer(thinking=True)

    requester_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)
    entrepreneur_id = int(user.id)

    if requester_id == entrepreneur_id:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error!",
                description="You cannot request to join your own company.",
                color=discord.Color.red()
            ), ephemeral=True
        )
        return

    async for session in get_session():
        # Check if requester is already in a company
        existing_company = await session.scalar(
            select(Player).where(
                Player.id == requester_id,
                Player.company_entrepreneur_id != None
            )
        )
        if existing_company:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description="You are already working in a company. Leave it first using `/job jobless`.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Check if target user owns a company
        company = await session.scalar(
            select(Company).where(
                Company.entrepreneur_id == entrepreneur_id,
                Company.server_id == server_id
            )
        )
        if not company:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description=f"{user.display_name} does not own a company.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Check for existing join request
        existing_request = await session.scalar(
            select(CompanyJoinRequest).where(
                CompanyJoinRequest.user_id == requester_id,
                CompanyJoinRequest.server_id == server_id,
                CompanyJoinRequest.company_entrepreneur_id == entrepreneur_id
            )
        )
        if existing_request:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Already Requested",
                    description=f"You have already requested to join **{company.name}**.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Create join request
        join_request = CompanyJoinRequest(
            user_id=requester_id,
            server_id=server_id,
            company_entrepreneur_id=entrepreneur_id
        )
        session.add(join_request)
        await session.commit()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Request Sent!",
                description=f"You have requested to join **{company.name}**. The entrepreneur will need to accept you.",
                color=discord.Color.green()
            )
        )







@client.tree.command(
    name="hire",
    description="Use this to accept users into your company",
    guild=guild_id
)
@app_commands.describe(user="The user you want to accept into your company")
async def hire(interaction: discord.Interaction, user: discord.Member):
    print(f"{interaction.user}: /hire {user}")
    await interaction.response.defer(thinking=True)

    entrepreneur_id = int(interaction.user.id)
    target_user_id = int(user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        # Existiert die Firma?
        company = await session.scalar(
            select(Company).where(
                Company.entrepreneur_id == entrepreneur_id,
                Company.server_id == server_id
            )
        )
        if not company:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="You don't own a company.",
                    description="Use `/company create` to create one.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Hat der Spieler eine Join-Request gestellt?
        request = await session.scalar(
            select(CompanyJoinRequest).where(
                CompanyJoinRequest.user_id == target_user_id,
                CompanyJoinRequest.server_id == server_id,
                CompanyJoinRequest.company_entrepreneur_id == entrepreneur_id
            )
        )
        if not request:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="No Join Request Found",
                    description=f"{user.display_name} has not requested to join your company. They must first use /join to request to join you.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Spielerobjekt holen oder erstellen
        player = await session.scalar(
            select(Player).where(Player.id == target_user_id, Player.server_id == server_id)
        )
        if not player:
            player = Player(
                id=target_user_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job=None,
                created_at=datetime.utcnow()
            )
            session.add(player)

        # Spieler zur Firma hinzufügen
        player.job = "Worker"
        player.company_entrepreneur_id = entrepreneur_id

        # Join-Request löschen
        await session.delete(request)
        await session.commit()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Worker Hired",
                description=f"✅ {user.display_name} is now part of your company.",
                color=discord.Color.green()
            )
        )





@client.tree.command(
    name="marketinfo",
    description="Used by anyone to receive information about the market.",
    guild=guild_id
)
@app_commands.describe(item="The item you want to see the info of")
async def marketinfo(interaction: discord.Interaction, item: str):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /marketinfo {item}")
    server_id = int(interaction.guild.id)

    async for session in get_session():
        # MarketItem abrufen
        market_entry = await session.scalar(
            select(MarketItem).where(
                func.lower(MarketItem.item_tag) == item.lower(),
                MarketItem.server_id == server_id
            )
        )
        if not market_entry:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Item Not Found",
                    description=f"The item **{item}** was not found in the market.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # BuyOrders abrufen
        buy_orders = (await session.execute(
            select(BuyOrder).where(
                func.lower(BuyOrder.item_tag) == item.lower(),
                BuyOrder.server_id == server_id,
                BuyOrder.expires_at > datetime.utcnow()
            ).order_by(BuyOrder.unit_price.desc())
        )).scalars().all()

        # SellOrders abrufen
        sell_orders = (await session.execute(
            select(SellOrder).where(
                func.lower(SellOrder.item_tag) == item.lower(),
                SellOrder.server_id == server_id,
                SellOrder.expires_at > datetime.utcnow()
            ).order_by(SellOrder.unit_price.asc())
        )).scalars().all()

        async def format_order(order):
            user = await interaction.client.fetch_user(order.user_id)
            type_label = "🏭 " if order.is_company else ""
            return f"{type_label}{order.amount}x @ ${order.unit_price:.2f} ({user.name})"

        # Embed erstellen
        embed = discord.Embed(
            title=f"Market Info – {market_entry.item_tag}",
            color=discord.Color.gold()
        )
        embed.add_field(name="NPC Sell Price", value=f"${market_entry.min_price:.2f}", inline=True)
        embed.add_field(name="NPC Buy Price", value=f"${market_entry.max_price:.2f}", inline=True)
        embed.add_field(name="Stockpile", value=str(market_entry.stockpile), inline=True)

        if buy_orders:
            embed.add_field(
                name="Buy Orders (sorted by price ↓)",
                value="\n".join([await format_order(o) for o in buy_orders[:10]]),
                inline=False
            )
        else:
            embed.add_field(name="Buy Orders", value="None", inline=False)

        if sell_orders:
            embed.add_field(
                name="Sell Orders (sorted by price ↑)",
                value="\n".join([await format_order(o) for o in sell_orders[:10]]),
                inline=False
            )
        else:
            embed.add_field(name="Sell Orders", value="None", inline=False)

        await interaction.followup.send(embed=embed)







@client.tree.command(
    name="gift",
    description="Gift money to another player ($10,000 max, 1h cooldown).",
    guild=guild_id
)
@app_commands.describe(
    user="The user you want to gift money to",
    value="The amount of money you want to gift"
)
async def gift(interaction: discord.Interaction, user: discord.Member, value: float):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /gift {user} {value}")
    if value <= 0:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Invalid Amount",
                description="You must gift a positive amount.",
                color=discord.Color.red()
            ), ephemeral=True
        )
        return

    if value > 10000:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Limit Exceeded",
                description="You can only gift up to $10,000 at a time.",
                color=discord.Color.red()
            ), ephemeral=True
        )
        return

    sender_id = int(interaction.user.id)
    receiver_id = int(user.id)
    server_id = int(interaction.guild.id)

    if sender_id == receiver_id:
        await interaction.followup.send(
            embed=discord.Embed(
                title="No Self-Gifting",
                description="You can't gift money to yourself.",
                color=discord.Color.red()
            ), ephemeral=True
        )
        return

    async for session in get_session():
        now = datetime.utcnow()

        # Sender prüfen
        sender = await session.scalar(select(Player).where(
            Player.id == sender_id,
            Player.server_id == server_id
        ))

        if not sender:
            sender = Player(
                id=sender_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job="",
                created_at=datetime.utcnow()
            )
            session.add(sender)

        if sender.gift_cooldown_until and sender.gift_cooldown_until > now:
            remaining = sender.gift_cooldown_until - now
            minutes = int(remaining.total_seconds() // 60)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="On Cooldown",
                    description=f"You can gift money again in **{minutes} minutes**.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        if sender.money < value:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Insufficient Funds",
                    description="You don't have enough money to send this gift.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Empfänger prüfen
        receiver = await session.scalar(select(Player).where(
            Player.id == receiver_id,
            Player.server_id == server_id
        ))

        if not receiver:
            receiver = Player(
                id=receiver_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job="",
                created_at=datetime.utcnow()
            )
            session.add(receiver)

        # Transaktion durchführen
        sender.money -= value
        receiver.money += value
        sender.gift_cooldown_until = now + GIFT_COOLDOWN

        await session.commit()

    await interaction.followup.send(
        embed=discord.Embed(
            title="Gift Sent!",
            description=f"You gifted **${value:,.2f}** to **{user.display_name}**.",
            color=discord.Color.green()
        )
    )






@client.tree.command(
    name="loan",
    description="Take a loan of up to $10,000. Loans have dynamic interest (set by the server government).",
    guild=guild_id
)
@app_commands.describe(
    value="The amount of money you want to loan"
)
async def loan(interaction: discord.Interaction, value: int):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /loan {value}")

    if value <= 0:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Invalid Amount",
                description="You must loan a positive amount.",
                color=discord.Color.red()
            ), ephemeral=True
        )
        return

    if value > 10_000:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Too Much",
                description="You can loan at most $10,000 at a time.",
                color=discord.Color.red()
            ), ephemeral=True
        )
        return

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        # Player prüfen oder erstellen
        player = await session.scalar(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )

        if not player:
            player = Player(
                id=user_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job="",
                created_at=datetime.utcnow()
            )
            session.add(player)
            session.commit()

        if player.debt >= 100_000:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Debt Limit Reached",
                    description="You already owe $100,000 or more. No more loans.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Zinsrate aus Government abfragen
        government = await session.scalar(select(Government).where(Government.id == server_id))
        if not government:
            government = Government(
                id=server_id,
                created_at = datetime.utcnow,
                taxrate = 0.1,
                interest_rate = 0.3,
                treasury = 0,
                governing_role = None,
                admin_role = None
            )
            session.add(government)
            session.commit()

        interest_rate = government.interest_rate or 0.10  # Fallback auf 10 %, falls None
        interest_amount = round(value * (1 + interest_rate), 2)

        # Geld & Schulden setzen
        player.money += value
        player.debt += interest_amount

        await session.commit()

    await interaction.followup.send(
        embed=discord.Embed(
            title="Loan Approved",
            description=(
                f"You received **${value:,.2f}**.\n"
                f"Your debt increased by **${interest_amount:,.2f}** "
                f"(Interest rate: {interest_rate * 100:.2f}%)."
            ),
            color=discord.Color.green()
        )
    )








@client.tree.command(
    name="paydebt",
    description="Used by anyone to pay back debt using their money.",
    guild=guild_id
)
@app_commands.describe(
    value="The amount of money you want to pay back"
)
async def paydebt(interaction: discord.Interaction, value: float):
    print(f"{interaction.user}: /paydebt {value}")
    await interaction.response.defer(thinking=True)

    if value <= 0:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Invalid Amount",
                description="You must pay back a positive amount.",
                color=discord.Color.red()
            ), ephemeral=True
        )
        return

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        player = await session.scalar(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )

        if not player:
            player = Player(
                id=user_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job="",
                created_at=datetime.utcnow()
            )
            session.add(player)
            session.commit()

        if player.debt <= 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="No Debt",
                    description="You don't have any debt to pay off.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        if player.money < value:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Insufficient Funds",
                    description=f"You don't have enough money to pay ${value:,.2f}.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        actual_payment = min(value, player.debt)

        player.money -= actual_payment
        player.debt -= actual_payment

        await session.commit()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Debt Payment Successful",
                description=f"You paid **${actual_payment:,.2f}** toward your debt.",
                color=discord.Color.green()
            )
        )






@client.tree.command(
    name="setmoney",
    description="Sets the money of a user. A negative value corresponds to debt.",
    guild=guild_id
)
@app_commands.describe(
    user="The user you want to modify the money of",
    value="The amount of money you want the user to have"
)
async def setmoney(interaction: discord.Interaction, user: discord.Member, value: float):
    print(f"{interaction.user}: /setmoney {user} {value}")
    await interaction.response.defer(thinking=True)

    server_id = int(interaction.guild.id)
    executor_roles = [role.id for role in interaction.user.roles]

    async for session in get_session():
        # Check government
        gov = await session.scalar(select(Government).where(Government.id == server_id))
        if not gov:
            gov = Government(
                id=server_id,
                created_at=datetime.utcnow,
                taxrate=0.1,
                interest_rate=0.3,
                treasury=0,
                governing_role=None,
                admin_role=None
            )
            session.add(gov)
            session.commit()

        # Check ONLY for admin_role
        if gov.admin_role not in executor_roles:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Unauthorized",
                    description="Only users with the admin role can use this command.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Get player
        user_id = int(user.id)
        player = await session.scalar(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )

        if not player:
            player = Player(
                id=user_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job="",
                created_at=datetime.utcnow()
            )
            session.add(player)
            session.commit()

        # Apply money/debt
        if value >= 0:
            player.money = value
            player.debt = 0.0
        else:
            player.money = 0.0
            player.debt = abs(value)

        await session.commit()

    await interaction.followup.send(
        embed=discord.Embed(
            title="Money Set",
            description=f"Set {user.display_name}'s money to **${value:,.2f}**.",
            color=discord.Color.green()
        )
    )






@client.tree.command(
    name="addmoney",
    description="Adds money to a user. Can be negative.",
    guild=guild_id
)
@app_commands.describe(
    user="The user you want to modify the money of",
    value="The amount of money you want to add to the user"
)
async def addmoney(interaction: discord.Interaction, user: discord.Member, value: float):
    print(f"{interaction.user}: /addmoney {user} {value}")
    await interaction.response.defer(thinking=True)

    server_id = int(interaction.guild.id)
    user_id = int(user.id)
    executor_roles = [role.id for role in interaction.user.roles]

    async for session in get_session():
        gov = await session.scalar(select(Government).where(Government.id == server_id))
        if not gov:
            gov = Government(
                id=server_id,
                created_at=datetime.utcnow,
                taxrate=0.1,
                interest_rate=0.3,
                treasury=0,
                governing_role=None,
                admin_role=None
            )
            session.add(gov)
            session.commit()

        if gov.admin_role not in executor_roles:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Unauthorized",
                    description="Only users with the admin role can use this command.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Player holen oder erstellen
        player = await session.scalar(
            select(Player).where(Player.id == user_id, Player.server_id == server_id)
        )

        if not player:
            player = Player(
                id=user_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job="",
                created_at=datetime.utcnow()
            )
            session.add(player)

        if value >= 0:
            player.money += value
        else:
            # Erst von Geld abziehen, falls nicht genug → Rest zu Schulden
            abs_val = abs(value)
            if player.money >= abs_val:
                player.money -= abs_val
            else:
                remainder = abs_val - player.money
                player.money = 0.0
                player.debt += remainder

        await session.commit()

    await interaction.followup.send(
        embed=discord.Embed(
            title="Money Updated",
            description=f"Updated {user.display_name}'s balance by **${value:,.2f}**.",
            color=discord.Color.green()
        )
    )


@client.tree.command(
    name="setsupply",
    description="Sets the supply of an item in the marketplace. Must be positive or 0.",
    guild=guild_id
)
@app_commands.describe(
    item="The item you want to modify the stockpile of",
    value="The stockpile you want the item to have"
)
async def setsupply(interaction: discord.Interaction, item: str, value: int):
    print(f"{interaction.user}: /setsupply item:{item}, value:{value}")
    await interaction.response.defer(thinking=True)

    server_id = int(interaction.guild.id)
    user_roles = [role.id for role in interaction.user.roles]

    async for session in get_session():
        gov = await session.scalar(select(Government).where(Government.id == server_id))
        if not gov:
            ov = Government(
                id=server_id,
                created_at=datetime.utcnow,
                taxrate=0.1,
                interest_rate=0.3,
                treasury=0,
                governing_role=None,
                admin_role=None
            )
            session.add(gov)
            session.commit()

        if gov.admin_role not in user_roles:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Permission denied",
                    description="You need admin rights to use this command.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        if value < 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error",
                    description="The stockpile value must be zero or positive.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        market_item = await session.scalar(
            select(MarketItem).where(
                func.lower(MarketItem.item_tag) == item.lower(),
                MarketItem.server_id == server_id
            )
        )

        if not market_item:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error",
                    description=f"Item `{item}` not found in the market for this server.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        market_item.stockpile = value
        await session.commit()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Stockpile Updated",
                description=f"Stockpile of `{item}` has been set to **{value}**.",
                color=discord.Color.green()
            )
        )


@client.tree.command(
    name="setprice",
    description="Sets the price of an item in the marketplace. Must be positive.",
    guild=guild_id
)
@app_commands.describe(
    item="The item you want to modify the price of",
    min_price="The minimum price you want the item to have",
    max_price="The maximum price you want the item to have"
)
async def setprice(interaction: discord.Interaction, item: str, min_price: float, max_price: float):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /setprice item:{item}, min_price:{min_price}, max_price:{max_price}")

    server_id = int(interaction.guild.id)
    user_roles = [role.id for role in interaction.user.roles]

    if min_price < 0 or max_price < 0:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error",
                description="Prices must be positive.",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return
    if max_price < min_price:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error",
                description="Max price must be greater or equal to min price.",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return

    async for session in get_session():
        gov = await session.scalar(select(Government).where(Government.id == server_id))
        if not gov:
            gov = Government(
                id=server_id,
                created_at=datetime.utcnow,
                taxrate=0.1,
                interest_rate=0.3,
                treasury=0,
                governing_role=None,
                admin_role=None
            )
            session.add(gov)
            session.commit()

        if gov.admin_role not in user_roles:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Permission denied",
                    description="You need admin rights to use this command.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        market_item = await session.scalar(
            select(MarketItem).where(
                func.lower(MarketItem.item_tag) == item.lower(),
                MarketItem.server_id == server_id
            )
        )

        if not market_item:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error",
                    description=f"Item `{item}` not found in the market for this server.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        market_item.min_price = min_price
        market_item.max_price = max_price
        await session.commit()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Prices Updated",
                description=f"Prices for `{item}` set to min: **{min_price:.2f}**, max: **{max_price:.2f}**.",
                color=discord.Color.green()
            )
        )




@client.tree.command(
    name="setdebt",
    description="Sets the debt of a user.",
    guild=guild_id
)
@app_commands.describe(
    user="The user you want to modify the debt of",
    value="The amount of debt you want the user to have. Negative amounts are nullified."
)
async def setdebt(interaction: discord.Interaction, user: discord.Member, value: float):
    print(f"{interaction.user}: /setdebt {user} {value}")
    await interaction.response.defer(thinking=True)

    server_id = int(interaction.guild.id)
    user_roles = [role.id for role in interaction.user.roles]
    target_user_id = int(user.id)

    async for session in get_session():
        gov = await session.scalar(select(Government).where(Government.id == server_id))
        if not gov:
            gov = Government(
                id=server_id,
                created_at=datetime.utcnow(),
                taxrate=0.1,
                interest_rate=0.3,
                treasury=0,
                governing_role=None,
                admin_role=None
            )
            session.add(gov)
            await session.commit()

        if gov.admin_role not in user_roles:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Permission denied",
                    description="You need admin rights to use this command.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        player = await session.scalar(
            select(Player).where(
                Player.id == target_user_id,
                Player.server_id == server_id
            )
        )

        if not player:
            player = Player(
                id=target_user_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job="",
                created_at=datetime.utcnow()
            )
            session.add(player)

        new_debt = max(0, value)  # Negative Werte zu 0 machen
        player.debt = new_debt
        await session.commit()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Debt Updated",
                description=f"Debt of {user.display_name} has been set to ${new_debt:.2f}.",
                color=discord.Color.green()
            )
        )






from datetime import datetime

@client.tree.command(
    name="adddebt",
    description="Adds debt to a user. Use negative numbers to remove debt.",
    guild=guild_id
)
@app_commands.describe(
    user="The user you want to modify the debt of",
    value="The amount of debt you want to add to the user"
)
async def adddebt(interaction: discord.Interaction, user: discord.Member, value: float):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /adddebt {user} {value}")

    server_id = int(interaction.guild.id)
    user_roles = [role.id for role in interaction.user.roles]
    target_user_id = int(user.id)

    async for session in get_session():
        # Government prüfen und ggf. Default anlegen
        gov = await session.scalar(select(Government).where(Government.id == server_id))
        if not gov:
            gov = Government(
                id=server_id,
                created_at=datetime.utcnow(),
                taxrate=0.1,
                interest_rate=0.3,
                treasury=0,
                governing_role=None,
                admin_role=None
            )
            session.add(gov)
            await session.commit()

        # Rechte prüfen
        if gov.admin_role not in user_roles:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Permission denied",
                    description="You need admin rights to use this command.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Player laden oder anlegen
        player = await session.scalar(
            select(Player).where(
                Player.id == target_user_id,
                Player.server_id == server_id
            )
        )
        if not player:
            player = Player(
                id=target_user_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job="",
                created_at=datetime.utcnow()
            )
            session.add(player)

        # Debt anpassen, darf nicht < 0 sein
        player.debt = max(0, player.debt + value)
        await session.commit()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Debt Updated",
                description=f"Debt of {user.display_name} is now ${player.debt:.2f}.",
                color=discord.Color.green()
            )
        )






@client.tree.command(
    name="additem",
    description="Adds an item to a user. If no amount is specified, one item is added.",
    guild=guild_id
)
@app_commands.describe(
    user="The user you want to give an item",
    item="Which item is added to the user",
    amount="How many items are added to the user"
)
async def additem(interaction: discord.Interaction, user: discord.Member, item: str, amount: int = 1):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /additem user:{user} item:{item}, amount:{amount}")

    server_id = int(interaction.guild.id)
    user_roles = [role.id for role in interaction.user.roles]
    target_user_id = int(user.id)

    async for session in get_session():
        # Government prüfen und ggf. anlegen
        gov = await session.scalar(select(Government).where(Government.id == server_id))
        if not gov:
            gov = Government(
                id=server_id,
                created_at=datetime.utcnow(),
                taxrate=0.1,
                interest_rate=0.3,
                treasury=0,
                governing_role=None,
                admin_role=None
            )
            session.add(gov)
            await session.commit()

        # Rechte prüfen (Adminrolle)
        if gov.admin_role not in user_roles:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Permission denied",
                    description="You need admin rights to use this command.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Player laden oder anlegen
        player = await session.scalar(
            select(Player).where(
                Player.id == target_user_id,
                Player.server_id == server_id
            )
        )
        if not player:
            player = Player(
                id=target_user_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job="",
                created_at=datetime.utcnow()
            )
            session.add(player)
            await session.commit()

        # Prüfen, ob Item existiert und produzierbar ist (optional, falls nötig)
        item_obj = await session.scalar(select(Item).where(func.lower(Item.item_tag) == item.lower()))
        if not item_obj:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error",
                    description=f"Item '{item}' does not exist.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Item hinzufügen - nur Player Items, kein Company Item hier
        await add_item(target_user_id, server_id, item, amount, is_company=False)

        await session.commit()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Item Added",
                description=f"Added {amount}x '{item}' to {user.display_name}.",
                color=discord.Color.green()
            )
        )





@client.tree.command(
    name="removeitem",
    description="Removes an item from a user. If no amount is specified, one item is removed.",
    guild=guild_id
)
@app_commands.describe(
    user="The user you want to remove an item from",
    item="Which item is removed from the user",
    amount="How many items are removed from the user"
)
async def removeitem(interaction: discord.Interaction, user: discord.Member, item: str, amount: int = 1):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /removeitem user:{user}, item:{item}, amount:{amount}")

    server_id = int(interaction.guild.id)
    user_roles = [role.id for role in interaction.user.roles]
    target_user_id = int(user.id)

    async for session in get_session():
        # Government prüfen und ggf. anlegen
        gov = await session.scalar(select(Government).where(Government.id == server_id))
        if not gov:
            gov = Government(
                id=server_id,
                created_at=datetime.utcnow(),
                taxrate=0.1,
                interest_rate=0.3,
                treasury=0,
                governing_role=None,
                admin_role=None
            )
            session.add(gov)
            await session.commit()

        # Rechte prüfen (Adminrolle)
        if gov.admin_role not in user_roles:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Permission denied",
                    description="You need admin rights to use this command.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Player laden oder anlegen
        player = await session.scalar(
            select(Player).where(
                Player.id == target_user_id,
                Player.server_id == server_id
            )
        )
        if not player:
            player = Player(
                id=target_user_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job="",
                created_at=datetime.utcnow()
            )
            session.add(player)
            await session.commit()

        # PlayerItem abrufen
        player_item = await session.scalar(
            select(PlayerItem).where(
                PlayerItem.user_id == target_user_id,
                PlayerItem.server_id == server_id,
                func.lower(PlayerItem.item_tag) == item.lower()
            )
        )
        if not player_item or player_item.amount <= 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error",
                    description=f"User does not have any '{item}'.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return

        # Menge anpassen
        remove_amount = min(amount, player_item.amount)
        player_item.amount -= remove_amount

        # Item löschen, wenn amount 0
        if player_item.amount <= 0:
            await session.delete(player_item)

        await session.commit()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Item Removed",
                description=f"Removed {remove_amount}x '{item}' from {user.display_name}.",
                color=discord.Color.green()
            )
        )





@client.tree.command(
    name="bailout",
    description="Used to reduce the debt of specific users to 0 using the government's treasury.",
    guild=guild_id
)
@app_commands.describe(
    user="Which user will be bailouted."
)
async def bailout(interaction: discord.Interaction, user: discord.Member):
    print(f"{interaction.user}: /bailout {user}")
    await interaction.response.defer(thinking=True)

    server_id = int(interaction.guild.id)
    executor_id = int(interaction.user.id)
    target_user_id = int(user.id)
    user_roles = [role.id for role in interaction.user.roles]

    async for session in get_session():
        # Government laden oder erstellen
        gov = await session.scalar(select(Government).where(Government.id == server_id))
        if not gov:
            gov = Government(
                id=server_id,
                created_at=datetime.utcnow(),
                taxrate=0.1,
                interest_rate=0.3,
                treasury=0,
                governing_role=None,
                admin_role=None
            )
            session.add(gov)
            await session.commit()

        # Rollenprüfung
        if not gov.governing_role or gov.governing_role not in user_roles:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Permission Denied",
                    description="You must have the governing role to use this command.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Player laden oder erstellen
        player = await session.scalar(
            select(Player).where(
                Player.id == target_user_id,
                Player.server_id == server_id
            )
        )
        if not player:
            player = Player(
                id=target_user_id,
                server_id=server_id,
                money=100.0,
                debt=0.0,
                hunger=100,
                thirst=100,
                health=100,
                job="",
                created_at=datetime.utcnow()
            )
            session.add(player)
            await session.commit()

        if player.debt <= 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="No Action Needed",
                    description=f"{user.display_name} has no debt to bail out.",
                    color=discord.Color.yellow()
                ),
                ephemeral=True
            )
            return

        if gov.treasury <= 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Insufficient Treasury Funds",
                    description="The government treasury is empty and cannot be used for a bailout.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Tilgungslogik
        if gov.treasury >= player.debt:
            cleared_debt = player.debt
            gov.treasury -= player.debt
            player.debt = 0.0
        else:
            cleared_debt = gov.treasury
            player.debt -= gov.treasury
            gov.treasury = 0.0

        await session.commit()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Bailout Executed",
                description=(
                    f"💰 {user.display_name} was bailed out with ${cleared_debt:.2f}.\n"
                    f"📉 Remaining debt: ${player.debt:.2f}\n"
                    f"🏛️ Treasury balance: ${gov.treasury:.2f}"
                ),
                color=discord.Color.green()
            )
        )






class LeaderboardView(View):
    def __init__(self, entries, current_user_id, per_page=10):
        super().__init__(timeout=60)
        self.entries = entries
        self.current_user_id = current_user_id
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = ceil(len(entries) / per_page)
        self.message = None

    def get_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        embed = Embed(title="💰 Net Worth Leaderboard", color=0xFFD700)
        for idx, (user_id, name, networth) in enumerate(self.entries[start:end], start=start + 1):
            display = f"**{name}**" if user_id == self.current_user_id else name
            embed.add_field(name=f"#{idx}", value=f"{display}: ${networth:,.2f}", inline=False)

        # Footer with user position
        rank = next((i + 1 for i, (uid, _, _) in enumerate(self.entries) if uid == self.current_user_id), None)
        embed.set_footer(text=f"Your position: #{rank}" if rank else "You are not ranked.")
        return embed

    async def update_message(self):
        if self.message:
            await self.message.edit(embed=self.get_embed(), view=self)

    @button(label="⏮", style=ButtonStyle.grey)
    async def go_first(self, interaction: Interaction, _):
        self.current_page = 0
        await self.update_message()
        await interaction.response.defer()

    @button(label="⬅", style=ButtonStyle.blurple)
    async def go_back(self, interaction: Interaction, _):
        if self.current_page > 0:
            self.current_page -= 1
        await self.update_message()
        await interaction.response.defer()

    @button(label="➡", style=ButtonStyle.blurple)
    async def go_next(self, interaction: Interaction, _):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        await self.update_message()
        await interaction.response.defer()

    @button(label="⏭", style=ButtonStyle.grey)
    async def go_last(self, interaction: Interaction, _):
        self.current_page = self.total_pages - 1
        await self.update_message()
        await interaction.response.defer()

# Slash Command
@client.tree.command(name="leaderboard", description="Shows who owns the most networth.", guild = guild_id)
async def leaderboard(interaction: Interaction):
    print(f"{interaction.user}: /leaderboard")
    await interaction.response.defer(thinking=True)

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        player_rows = await session.execute(
            select(Player).where(Player.server_id == server_id)
        )
        players = player_rows.scalars().all()

        company_rows = await session.execute(
            select(Company).where(Company.server_id == server_id)
        )
        companies = company_rows.scalars().all()

        player_data = {p.id: {"money": p.money, "debt": p.debt, "capital": 0.0} for p in players}
        for c in companies:
            if c.entrepreneur_id in player_data:
                player_data[c.entrepreneur_id]["capital"] += c.capital

        entries = []
        for uid, data in player_data.items():
            net = data["money"] + data["capital"] - data["debt"]
            try:
                user = await interaction.client.fetch_user(uid)
                name = user.display_name if hasattr(user, "display_name") else user.name
            except:
                name = f"User {uid}"
            entries.append((uid, name, net))

        entries.sort(key=lambda x: x[2], reverse=True)

        view = LeaderboardView(entries, user_id)
        view.message = await interaction.followup.send(embed=view.get_embed(), view=view)







@client.tree.command(
    name="ingredients",
    description="Shows you which ingredients you need for a certain item",
    guild=guild_id
)
@app_commands.describe(item="The item you want to see the ingredients of")
async def ingredients(interaction: Interaction, item: str):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /ingredients {item}")

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        # Fetch item
        result = await session.execute(select(Item).where(func.lower(Item.item_tag) == item.lower()))
        item_obj = result.scalar_one_or_none()

        if not item_obj:
            await interaction.followup.send(
                embed=Embed(
                    title="Item Not Found",
                    description=f"No item with tag `{item}` was found.",
                    color=0xFF0000
                ),
                ephemeral=True
            )
            return

        if not item_obj.ingredients:
            await interaction.followup.send(
                embed=Embed(
                    title=f"{item_obj.item_tag} has no ingredients",
                    description="This item is either not producible or doesn't require any components.",
                    color=0xFF0000
                ),
                ephemeral=True
            )
            return

        ingredients_list = []
        total_cost = 0.0
        lines = []

        for entry in item_obj.ingredients.split(","):
            tag, amount_str = entry.split(":")
            amount = int(amount_str)

            # Fetch market price
            market_entry = await session.scalar(
                select(MarketItem).where(
                    MarketItem.item_tag == tag,
                    MarketItem.server_id == server_id
                )
            )

            price = market_entry.max_price if market_entry else 0.0
            cost = price * amount
            total_cost += cost

            lines.append(f"• {amount}x {tag}:  ${cost:.2f}")

        embed = Embed(
            title=f"Ingredients for {item_obj.item_tag}",
            description="\n".join(lines),
            color=0xFFFF00
        )

        embed.add_field(
            name="Material Cost (NPC Market)",
            value=f"${total_cost:.2f}",
            inline=False
        )

        await interaction.followup.send(embed=embed)


@client.tree.command(
    name="buymaterials",
    description="Used by entrepreneurs to try to buy all necessary ingredients of an item",
    guild=guild_id
)
@app_commands.describe(
    item="The item you want to buy the ingredients of",
    amount="How many times you want to be able to produce that item",
    buy_price="0 = min price, 1 = max price. Values in between = Buy Orders"
)
async def buymaterials(interaction: discord.Interaction, item: str, amount: int = 1, buy_price: float = 0.5):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /buymaterials item:{item}, amount:{amount}, buy_price:{buy_price}")

    if buy_price < 0 or buy_price > 1:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Invalid Buy Price",
                description=(
                    "Buy_Price must be a value >= 0 and <= 1. "
                    "It represents the percentage between min_price and max_price. "
                    "I.e. 0 = min_price, 1 = max_price, 0.5 = middle"
                ), color=discord.Color.red(), ephemeral = True
            )
        )
        return

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    async for session in get_session():
        # Company check
        company = await session.scalar(select(Company).where(
            Company.entrepreneur_id == user_id,
            Company.server_id == server_id
        ))
        if not company:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="You don't own a company",
                    description=(
                        "The /buymaterials command is only used by companies to buy the required materials for items. "
                        "You must first create a company using /company create."
                    ), color=discord.Color.red()
                ), ephemeral = True
            )
            return

        # Item + ingredients
        item_data = await session.scalar(select(Item).where(func.lower(Item.item_tag) == item.lower()))
        if not item_data or not item_data.ingredients:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Invalid Item",
                    description=(
                        f"**{item}** is invalid or not producible."
                    ), color=discord.Color.red()
                ), ephemeral = True
            )
            return

        ingredients = item_data.ingredients.split(",")
        purchases = []
        total_cost = 0.0
        buy_orders_created = []
        npc_purchase = False

        for ing in ingredients:
            tag, qty_str = ing.split(":")
            qty = int(qty_str) * amount

            market_item = await session.scalar(select(MarketItem).where(
                MarketItem.item_tag == tag,
                MarketItem.server_id == server_id
            ))
            if not market_item:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Item does not exist",
                        description=(
                            "No market entry for `{tag}`"
                            "It represents the percentage between min_price and max_price. "
                            "I.e. 0 = min_price, 1 = max_price, 0.5 = middle"
                        ), color=discord.Color.red()
                    ), ephemeral = True
                )
                return

            if buy_price == 1 and market_item.stockpile >= qty and market_item.max_price > 0:
                # NPC purchase
                npc_purchase = True

                unit_price = market_item.max_price
                cost = unit_price * qty
                purchases.append((tag, qty, unit_price, cost))
                total_cost += cost

            else:
                # Buy order
                unit_price = market_item.min_price + (market_item.max_price - market_item.min_price) * buy_price

                # Combine with existing order (if any)
                existing_order = await session.scalar(select(BuyOrder).where(
                    BuyOrder.user_id == user_id,
                    BuyOrder.server_id == server_id,
                    BuyOrder.item_tag == tag,
                    BuyOrder.unit_price == unit_price,
                    BuyOrder.is_company == True
                ))
                if existing_order:
                    existing_order.amount += qty
                else:
                    new_order = BuyOrder(
                        user_id=user_id,
                        server_id=server_id,
                        item_tag=tag,
                        unit_price=unit_price,
                        amount=qty,
                        is_company=True,
                        expires_at=datetime.utcnow() + BUY_ORDER_DURATION
                    )
                    session.add(new_order)
                    buy_orders_created.append((tag, qty, unit_price))

        # Wenn direkt gekauft wird → Kapital abziehen & Items hinzufügen
        if npc_purchase:
            if company.capital < total_cost:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Not Enough Capital",
                        description=(
                            f"❌ Not enough company capital (${company.capital:.2f}, needed: ${total_cost:.2f})"
                        ), color=discord.Color.red()
                    ), ephemeral=True
                )
                return

            company.capital -= total_cost

            for tag, qty, _, _ in purchases:
                ci = await session.scalar(select(CompanyItem).where(
                    CompanyItem.server_id == server_id,
                    CompanyItem.company_entrepreneur_id == user_id,
                    CompanyItem.item_tag == tag
                ))
                if ci:
                    ci.amount += qty
                else:
                    session.add(CompanyItem(
                        server_id=server_id,
                        company_entrepreneur_id=user_id,
                        item_tag=tag,
                        amount=qty
                    ))

            # Stock reduzieren und Preise leicht anpassen
            for tag, qty, unit_price, _ in purchases:
                mi = await session.scalar(select(MarketItem).where(
                    MarketItem.item_tag == tag,
                    MarketItem.server_id == server_id
                ))
                if mi:
                    mi.stockpile -= qty
                    mi.min_price = round(mi.min_price * 1.005, 2)
                    mi.max_price = round(mi.max_price * 1.005, 2)

            await session.commit()

            # Embed für NPC-Kauf
            embed = discord.Embed(
                title="✅ Materials Purchased",
                description=f"Purchased all ingredients for **{amount}x {item}** from NPC.",
                color=discord.Color.green()
            )
            for tag, qty, unit_price, cost in purchases:
                embed.add_field(name=tag, value=f"{qty}x @ ${unit_price:.2f} = ${cost:.2f}", inline=False)
            embed.add_field(name="Total Cost", value=f"${total_cost:.2f}", inline=False)

            await interaction.followup.send(embed=embed)

        else:
            # Embed für Buy Orders
            await session.commit()
            embed = discord.Embed(
                title="🛒 Buy Orders Created",
                description=f"Created Buy Orders to buy ingredients for **{amount}x {item}**.",
                color=discord.Color.blurple()
            )
            for tag, qty, unit_price in buy_orders_created:
                embed.add_field(name=tag, value=f"{qty}x @ ${unit_price:.2f}", inline=False)

            await interaction.followup.send(embed=embed)




class TaxCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="tax", description="Different commands for managing taxes.")
    @app_commands.command(name="view", description="View all outstanding taxes")
    async def view(self, interaction: discord.Interaction):
        print(f"{interaction.user}: /tax view")
        await interaction.response.defer(thinking=True)
        server_id = interaction.guild.id

        async for session in get_session():
            players = (await session.execute(
                select(Player).where(Player.server_id == server_id, Player.taxes_owed > 0)
            )).scalars().all()

            companies = (await session.execute(
                select(Company).where(Company.server_id == server_id, Company.taxes_owed > 0)
            )).scalars().all()

            lines = []

            for player in players:
                user = await interaction.client.fetch_user(player.id)
                lines.append(f"🧍 **{user.display_name}** owes ${player.taxes_owed:.2f}")

            for company in companies:
                owner = await interaction.client.fetch_user(company.entrepreneur_id)
                lines.append(f"🏭 **{owner.display_name}**'s company owes ${company.taxes_owed:.2f}")

            if not lines:
                content = "✅ Nobody owes taxes right now!"
            else:
                content = "\n".join(lines)

            await interaction.followup.send(embed=discord.Embed(
                title="Outstanding Taxes",
                description=content,
                color=discord.Color.gold()
            ))

    @app_commands.command(name="pay", description="Pay your personal or company taxes")
    @app_commands.describe(amount="Amount to pay (optional)")
    async def pay(self, interaction: discord.Interaction, amount: float = None):
        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /tax pay {amount}")
        server_id = interaction.guild.id
        user_id = interaction.user.id

        async for session in get_session():
            player = await session.scalar(select(Player).where(Player.id == user_id, Player.server_id == server_id))
            if not player:
                # Standardwerte
                player = Player(
                    id=user_id,
                    server_id=server_id,
                    money=100.0,
                    debt=0.0,
                    hunger=100,
                    thirst=100,
                    health=100,
                    job=None,
                    created_at=datetime.utcnow()
                )
                session.add(player)
                await session.commit()

            company = await session.scalar(
                select(Company).where(Company.entrepreneur_id == user_id, Company.server_id == server_id))
            total_personal = player.taxes_owed
            total_company = company.taxes_owed if company else 0
            total_owed = total_personal + total_company

            if total_owed <= 0:
                await interaction.followup.send("You have no taxes to pay.")
                return

            if amount is None:
                amount = total_owed

            paid = 0
            msg = ""

            if company and company.taxes_owed > 0 and amount > 0:
                pay = min(company.taxes_owed, company.capital, amount)
                company.taxes_owed -= pay
                company.capital -= pay
                paid += pay
                amount -= pay
                msg += f"🏭 Paid ${pay:.2f} in company taxes.\n"

            if player.taxes_owed > 0 and amount > 0:
                pay = min(player.taxes_owed, player.money, amount)
                player.taxes_owed -= pay
                player.money -= pay
                paid += pay
                msg += f"🧍 Paid ${pay:.2f} in personal taxes."

            # ➕ Regierung laden und Geld in die Treasury
            gov = await session.scalar(select(Government).where(Government.id == server_id))
            if not gov:
                gov = Government(
                    id=server_id,
                    created_at=datetime.utcnow(),
                    taxrate=0.1,
                    interest_rate=0.3,
                    treasury=0,
                    governing_role=None,
                    admin_role=None
                )
                session.add(gov)

            gov.treasury += paid

            await session.commit()

            if paid == 0:
                await interaction.followup.send(embed=discord.Embed(
                    title="Not Enough Money",
                    description="You don't have enough money to pay any taxes.",
                    color=discord.Color.red()
                ))
            else:
                await interaction.followup.send(embed=discord.Embed(
                    title="Taxes Paid",
                    description=msg,
                    color=discord.Color.green()
                ))

    @app_commands.command(name="rate", description="Set the tax rate (governing role required)")
    @app_commands.describe(amount="New tax rate (0 to 1)")
    async def rate(self, interaction: discord.Interaction, amount: float):
        print(f"{interaction.user}: /tax rate {amount}")
        await interaction.response.defer(thinking=True)
        server_id = interaction.guild.id
        user_roles = [r.id for r in interaction.user.roles]

        async for session in get_session():
            gov = await session.scalar(select(Government).where(Government.id == server_id))
            if not gov:
                gov = Government(
                    id=server_id,
                    created_at=datetime.utcnow(),
                    taxrate=0.1,
                    interest_rate=0.3,
                    treasury=0,
                    governing_role=None,
                    admin_role=None
                )
                session.add(gov)
                await session.commit()

            if gov.governing_role not in user_roles:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Permission Denied",
                        description="You don't have permission to change the tax rate.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            if not (0 <= amount <= 1):
                await interaction.followup.send("Tax rate must be between 0 and 1.", ephemeral=True)
                return

            gov.taxrate = amount
            await session.commit()

            await interaction.followup.send(embed=discord.Embed(
                title="Tax Rate Updated",
                description=f"📊 The new tax rate is **{amount * 100:.1f}%**.",
                color=discord.Color.blue()
            ))



@client.tree.command(name="government", description="Shows information about the current government.")
@app_commands.guilds(guild_id)
async def government(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    server_id = interaction.guild.id

    async for session in get_session():
        gov = await session.scalar(select(Government).where(Government.id == server_id))

        if not gov:
            gov = Government(
                id=server_id,
                created_at=datetime.utcnow(),
                taxrate=0.1,
                interest_rate=0.3,
                treasury=0,
                governing_role=None,
                admin_role=None
            )
            session.add(gov)
            await session.commit()

        # Rollen auflösen
        guild = interaction.guild
        governing_role = discord.utils.get(guild.roles, id=gov.governing_role) if gov.governing_role else None
        admin_role = discord.utils.get(guild.roles, id=gov.admin_role) if gov.admin_role else None

        embed = discord.Embed(
            title="Government Overview",
            color=discord.Color.yellow()
        )
        embed.add_field(name="📅 Created At", value=gov.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=False)
        embed.add_field(name="💸 Tax Rate", value=f"{gov.taxrate * 100:.2f}%", inline=True)
        embed.add_field(name="🏦 Interest Rate", value=f"{gov.interest_rate * 100:.2f}%", inline=True)
        embed.add_field(name="💰 Treasury", value=f"${gov.treasury:,.2f}", inline=False)
        embed.add_field(name="🎓 Governing Role", value=governing_role.mention if governing_role else "None", inline=True)
        embed.add_field(name="🔧 Admin Role", value=admin_role.mention if admin_role else "None", inline=True)

        # GDP der letzten 7 Tage holen
        today = date.today()
        seven_days_ago = today - timedelta(days=6)

        gdp_entries = (
            await session.execute(
                select(GovernmentGDP)
                .where(
                    GovernmentGDP.server_id == server_id,
                    GovernmentGDP.date >= seven_days_ago
                )
                .order_by(GovernmentGDP.date)
            )
        ).scalars().all()

        if gdp_entries:
            gdp_text = ""
            for entry in gdp_entries:
                day_label = "📅 Today" if entry.date == today else entry.date.strftime("%a %Y-%m-%d")
                gdp_text += f"{day_label}: ${entry.gdp_value:,.2f}\n"
            embed.add_field(name="📊 GDP (Last 7 Days)", value=gdp_text, inline=False)

        await interaction.followup.send(embed=embed)



@client.tree.command(name="help", description="Displays the most useful commands.", guild=guild_id)
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Help Menu",
        description="Here are some of the most important commands to get started.",
        color=discord.Color.blurple()
    )

    # Wichtigste Commands zuerst
    embed.add_field(
        name="🚀 Getting Started",
        value=(
            "`/work` – Work for your company and produce items\n"
            "`/buy` – Place a buy order on the market\n"
            "`/sell` – Place a sell order on the market\n"
            "`/gift` – Give money to another user\n"
            "`/loan` – Take a loan with interest\n"
            "`/paydebt` – Pay back your debt\n"
        ),
        inline=False
    )

    # Wirtschaft/Handel
    embed.add_field(
        name="💰 Economy",
        value=(
            "`/marketinfo` – View market details of an item\n"
            "`/orders` – View your current market orders\n"
            "`/buymaterials` – Buy materials for production\n"
            "`/ingredients` – See what you need to craft an item\n"
            "`/leaderboard` – See who has the most net worth\n"
        ),
        inline=False
    )

    # Unternehmen
    embed.add_field(
        name="🏭 Company",
        value=(
            "`/company create` – Start your own company\n"
            "`/setitems` – Define what your workers can produce\n"
            "`/join` – Request to join a company\n"
            "`/hire` – Accept someone into your company\n"
            "`/disband` – Disband your company\n"
        ),
        inline=False
    )

    # Regierung
    embed.add_field(
        name="🏛️ Government",
        value=(
            "`/government` – Show government info\n"
            "`/tax view` – See unpaid taxes\n"
            "`/tax pay` – Pay your taxes\n"
            "`/bailout` – Use treasury to reduce someone's debt\n"
        ),
        inline=False
    )

    # Admin
    embed.add_field(
        name="🛠️ Admin",
        value=(
            "`/setmoney`, `/addmoney` – Modify user money\n"
            "`/setdebt`, `/adddebt` – Modify user debt\n"
            "`/setprice`, `/setsupply` – Control NPC market\n"
            "`/additem`, `/removeitem` – Grant or remove items\n"
            "`/tax rate` – Change tax rate\n"
        ),
        inline=False
    )

    embed.set_footer(text="Use Tab to autocomplete command names. For full documentation, ask an admin.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@client.tree.command(
    name="wage",
    description="Change the wage paid to your workers.",
    guild=guild_id
)
@app_commands.describe(
    amount="The new wage (must be ≥ 0)"
)
async def wage(interaction: discord.Interaction, amount: float):
    await interaction.response.defer(thinking=True)

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    if amount < 0:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error!",
                description="Wage must be 0 or higher.",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return

    async for session in get_session():
        company = await session.scalar(
            select(Company).where(
                Company.entrepreneur_id == user_id,
                Company.server_id == server_id
            )
        )

        if not company:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="You Don't Own A Company!",
                    description="You must own a company to set the wage.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        company.wage = amount
        await session.commit()

    await interaction.followup.send(
        embed=discord.Embed(
            title="Wage Updated",
            description=f"The wage for your company is now set to **${amount:.2f}**.",
            color=discord.Color.green()
        )
    )



# Registrierung
client.tree.add_command(OrderCommandGroup(), guild=guild_id)
client.tree.add_command(CompanyGroup(), guild=guild_id)
client.tree.add_command(TaxCommandGroup(), guild=guild_id)



client.run(TOKEN)