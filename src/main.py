import discord
from discord.ext import commands
from discord.ext.commands import Bot
from discord import app_commands, Embed, Interaction, User, ButtonStyle, Member
from discord.ui import Button, View, button
from discord.app_commands import Choice
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import uvicorn
import asyncio

from math import floor, ceil
from sqlalchemy.ext.asyncio import AsyncSession
import threading


from datetime import timedelta, date
from time import time


from src.commands import ping, get_items, stats, job, chop, mine, farm, harvest, drink, eat, consume, buy, sell, subsidize, sponsor, roulette
from src.db.models import Player, PlayerItem, Item, MarketItem, BuyOrder, SellOrder, Company, Government, CompanyItem, CompanyJoinRequest, GovernmentGDP
from src.config import TOKEN, GUILD_ID, JOB_SWITCH_COOLDOWN, WORK_COOLDOWN, BUY_ORDER_DURATION, SELL_ORDER_DURATION, GIFT_COOLDOWN, PORT
from src.commands import order_view, order_remove
from src.db.db_calls import (get_item, get_company, get_buy_orders, get_market_item, get_all_items, get_player, \
                             get_own_sell_orders, get_own_buy_orders, get_sell_orders, get_employees,
                             get_company_inventory, \
                             get_producible_items, get_company_item, get_user_join_request, get_item_buy_orders,
                             get_item_sell_orders, \
                             get_government, get_tax_owing_players, get_tax_owing_companies, get_all_gdp_entries,
                             get_join_requests, fire_employees, get_all_companies, get_all_players, \
                             get_player_item, update_player, update_buy_order, update_company, update_company_item,
                             update_company_join_request, delete_company, \
                             update_government, update_government_gdp, update_market_item, update_player_item,
                             update_sell_order, delete_company_item, delete_buy_orders, add_object, delete_sell_orders, delete_join_requests, delete_player_item)
from src.helper.defaults import get_default_market_item, get_default_player, get_default_government
from src.helper.item import add_company_item, add_player_item, has_player_item, use_item
from src.helper.randoms import get_hunger_depletion, get_thirst_depletion
from src.helper.transactions import add_owed_taxes


app = FastAPI()

@app.get("/ping")
def ping():
    return "pong"


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

@client.tree.command(name="items", description="Shows all the items and their base values", guild=guild_id)
async def init_items(interaction: Interaction):
    await interaction.response.defer(thinking=True)
    await get_items(interaction)


@client.tree.command(
    name="stats",
    description="Tells you everything about a user. If no user-id is provided, it will show your stats",
    guild=guild_id
)
@app_commands.describe(user="The stats of the user you wish to see the stats of")
async def init_stats(interaction: Interaction, user: discord.User | discord.Member = None):
    await interaction.response.defer(thinking=True)
    await stats(interaction, user)


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
async def init_job(interaction: Interaction, job_type: app_commands.Choice[str]):
    await interaction.response.defer(thinking=True)
    await job(interaction, job_type)


@client.tree.command(name="chop", description="Used by lumberjacks to chop down trees.", guild=guild_id)
async def init_chop(interaction: Interaction):
    await interaction.response.defer(thinking=True)
    await chop(interaction)


@client.tree.command(name="mine", description="Used by miners to mine resources.", guild=guild_id)
async def init_mine(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await mine(interaction)


@client.tree.command(name="farm", description="Used by farmers to harvest crops.", guild=guild_id)
@app_commands.describe(item="The item you want to farm")
@app_commands.choices(item=[
    app_commands.Choice(name="grain", value="Grain"),
    app_commands.Choice(name="wool", value="Wool"),
    app_commands.Choice(name="fish", value="Fish"),
    app_commands.Choice(name="leather", value="Leather"),
])
async def init_farm(interaction: Interaction, item: app_commands.Choice[str] = None):
    await interaction.response.defer(thinking=True)
    await farm(interaction, item)


@client.tree.command(name="harvest", description="Used by special jobs to harvest their unique resource.", guild=guild_id)
async def init_harvest(interaction: Interaction):
    await interaction.response.defer(thinking=True)
    await harvest(interaction)


@client.tree.command(name="drink", description="Consumes 1 water from your inventory and fills up your thirst bar.", guild=guild_id)
async def init_drink(interaction: Interaction):
    await interaction.response.defer(thinking=True)
    await drink(interaction)


@client.tree.command(name="eat", description="Consumes 1 grocery from your inventory and fills up your hunger bar.", guild=guild_id)
async def init_eat(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await eat(interaction)


@client.tree.command(
    name="consume",
    description="Consumes an item from the inventory and applies the corresponding effects",
    guild=guild_id
)
@app_commands.describe(item="The item you want to consume")
@app_commands.choices(item=[
    app_commands.Choice(name="water", value="Water"),
    app_commands.Choice(name="grocery", value="Grocery"),
    app_commands.Choice(name="fish", value="Fish")
])
async def init_consume(interaction: discord.Interaction, item: app_commands.Choice[str]):
   await interaction.response.defer(thinking=True)
   await consume(interaction, item)


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
async def init_buy(
    interaction: discord.Interaction,
    item: str,
    unit_price: float = -1.0,
    amount: int = 1):
    await interaction.response.defer(thinking=True)
    await buy(interaction, item, unit_price, amount)


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
async def init_sell(
    interaction: discord.Interaction,
    item: str,
    unit_price: float = -1.0, # Used for when you just want to sell it at the npc price
    amount: int = 1):
    await interaction.response.defer(thinking=True)
    await sell(interaction, item, unit_price, amount)

# CommandGroup Definition
class OrderCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="order", description="Manage your market orders")

    @app_commands.command(name="view", description="View buy and sell orders")
    @app_commands.describe(user="(Optional) View orders of another user")
    async def init_view(self, interaction: discord.Interaction, user: discord.User | None = None):
        await interaction.response.defer(thinking=True)
        await order_view(interaction, user)

    @app_commands.command(name="remove", description="Remove one or multiple orders")
    @app_commands.describe(
        item_tag="The item tag of the order(s) to remove",
        price="(Optional) Only remove order at this exact price"
    )
    async def init_remove(self, interaction: discord.Interaction, item_tag: str, price: float | None = None):
        await interaction.response.defer(thinking=True)
        await order_remove(interaction, item_tag, price)

class CompanyGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="company", description="Used to do certain actions in the company you're working in")


    @app_commands.command(name="sell", description="Sell items from the company stockpile to the market")
    @app_commands.describe(
        item="The item you want to sell",
        unit_price="Price you're selling for per unit",
    )
    async def company_sell(
            self,
            interaction: discord.Interaction,
            item: str,
            unit_price: float = -1.0,
            amount: int = 1
    ):

        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /company sell item:{item}, unit_price:{unit_price}, amount:{amount}")

        if (amount <= 0 or unit_price <= 0) and unit_price != -1:
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


        # Item prüfen
        item_obj = await get_item(item)
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
        company = await get_company(user_id, server_id)
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
        inv_item = await get_company_item(user_id, server_id, item_tag)
        if not inv_item or inv_item.amount < amount:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description=f"Your company doesn't have enough **{item_tag}**.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return
        

        player = await get_player(user_id, server_id)
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
        await update_company_item(inv_item)
        if inv_item.amount <= 0:
            await delete_company_item(company.entrepreneur_id, inv_item.item_tag, server_id)

        # Update hunger/thirst/cooldown
        old_hunger = player.hunger
        old_thirst = player.thirst
        player.hunger = max(0, player.hunger - amount * get_hunger_depletion())
        player.thirst = max(0, player.thirst - amount * get_thirst_depletion())
        player.work_cooldown_until = now + WORK_COOLDOWN
        await update_player(player)

        # Markt initialisieren, falls nötig
        market_entry = await get_market_item(server_id, item_tag)
        if not market_entry:
            items = await get_all_items()

            for item in items:
                market_item = get_default_market_item(item, server_id)
                await add_object(market_item, "Market_Items")

        market_entry = await get_market_item(server_id, item_tag)

        if unit_price == -1:
            total_sold = 0
            total_earned = 0.0
            npc_sell_qty = amount
            price = market_entry.min_price
            total_price = round(npc_sell_qty * price, 2)

            company.capital += total_price
            await update_company(company)
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
            market_entry.max_price = market_entry.max_price * factor, 2
            market_entry.min_price = market_entry.min_price * factor, 2

            await update_market_item(market_entry)
            return


        # Bestehende SellOrder checken
        now = datetime.now()

        existing_orders = await get_own_sell_orders(user_id, server_id, item_tag, unit_price, is_company=True)

        if len(existing_orders) > 0:
            existing_order = existing_orders[0]
            print("Merging orders")
            existing_order.amount += amount
            await update_sell_order(existing_order)
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
        



        # Buy Orders abrufen
        buy_orders = await get_buy_orders(server_id, item_tag, unit_price, now)

        total_sold = 0
        total_earned = 0.0

        for buy_order in buy_orders:
            if total_sold >= amount:
                break


            sell_qty = min(buy_order.amount, amount - total_sold)
            total_price = sell_qty * unit_price

            # Validierung + Transaktion
            if buy_order.is_company:
                company_buyer = await get_company(buy_order.user_id, server_id)

                if not company_buyer:
                    # Firma existiert nicht mehr → Order löschen, Verkauf überspringen
                    await delete_buy_orders(buy_order)
                    continue

                if company_buyer.capital < total_price:
                    continue  # Firma hat nicht genug Geld → überspringen

                # Transaktion Firma → Verkäufer
                company_buyer.capital -= total_price
                company.capital += total_price
                await add_owed_taxes(user_id=company.entrepreneur_id, server_id=server_id,
                                     amount=total_price, is_company=True)
                await add_company_item(buy_order.user_id, server_id, item_tag, sell_qty, True)

            else:
                buyer = await get_player(buy_order.user_id, server_id)
                if not buyer or buyer.money < total_price:
                    continue



                if buyer.money < total_price:
                    sell_qty = int(buyer.money // unit_price)
                    total_price = sell_qty * unit_price

                if sell_qty <= 0:
                    continue

                # Transaktion Käufer → Verkäufer
                buyer.money -= total_price
                company.capital += total_price
                await add_owed_taxes(user_id=company.entrepreneur_id, server_id=server_id,
                                     amount=total_price, is_company=True)
                await add_player_item(buy_order.user_id, server_id, item_tag, sell_qty)

            # Buy Order anpassen oder löschen
            buy_order.amount -= sell_qty
            if buy_order.amount <= 0:
                await delete_buy_orders(buy_order.user_id, buy_order.server_id, buy_order.item_tag)

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
            

            if unit_price <= market_entry.min_price:
                npc_sell_qty = remaining
                price = market_entry.min_price
                total_price = npc_sell_qty * price

                company.capital += total_price
                await update_company(company)
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
                market_entry.max_price = market_entry.max_price * factor
                market_entry.min_price = market_entry.min_price * factor

                await update_market_item(market_entry)
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
                is_company=True
            )
            await add_object(new_order, "Sell_Orders")
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
            unit_price: float = -1.0,
            amount: int = 1
    ):
        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /company buy item: {item}, unit_price: {unit_price}, amount: {amount}")

        if (amount <= 0 or unit_price <= 0) and unit_price != -1:
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

        # Item prüfen
        item_obj = await get_item(item)
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
        company = await get_company(user_id, server_id)
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
        

        # Markt initialisieren, falls nötig
        market_entry = await get_market_item(server_id, item_tag)
        if not market_entry:
            items = await get_all_items()

            for item in items:
                market_item = get_default_market_item(item, server_id)
                await add_object(market_item, "Market_Items")

        market_entry = await get_market_item(server_id, item_tag)

        if unit_price == -1:
            if market_entry.stockpile <= 0:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description=f"**{item_tag}** is out of stock.",
                        color=discord.Color.red()
                    ), ephemeral=True
                )
                return
        

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
                return

            company.capital -= total_price
            await add_company_item(user_id, server_id, item_tag, purchasable_amount)
            market_entry.stockpile -= purchasable_amount



            await update_company(company)
            await update_market_item(market_entry)

            await interaction.followup.send(
                embed=discord.Embed(
                    title="NPC Market Purchase",
                    description=f"You bought **{purchasable_amount}x {item_tag}** from the NPC market for **${(total_price/purchasable_amount):.2f}** each. Total: **${total_price:.2f}**.",
                    color=discord.Color.green()
                )
            )

            # Preis anpassen
            factor = 1 + 0.005 * purchasable_amount
            market_entry.min_price = market_entry.min_price * factor
            market_entry.max_price = market_entry.max_price * factor
            await update_market_item(market_entry)
            return

        # Bestehende BuyOrder checken
        now = datetime.now()

        existing_orders = await get_own_buy_orders(user_id, server_id, item_tag, unit_price, is_company=True)

        if len(existing_orders) > 0:
            existing_order = existing_orders[0]
            existing_order.amount += amount
            await update_buy_order(existing_order)

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

        


        # SELL-Orders finden
        fulfilled_total = 0
        total_spent = 0.0

        sell_orders = await get_sell_orders(server_id, item_tag, unit_price, now)


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
            await add_company_item(user_id, server_id, item_tag, match_amount)
            await update_company(company)


            if sell_order.is_company:
                company_seller = await get_company(sell_order.user_id, server_id)
                if company_seller:
                    company_seller.capital += total_price
                    await add_owed_taxes(user_id=company_seller.entrepreneur_id, server_id=server_id, amount=total_price, is_company=True)


                else:
                    await delete_sell_orders(sell_order.user_id, sell_order.server_id, sell_order.item_tag)
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Sell Order Removed",
                            description="The company for one of the sell orders no longer exists. Sell order removed.",
                            color=discord.Color.orange()
                        )
                    )
                    continue
            else:
                seller = await get_player(sell_order.user_id, server_id)
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
                await delete_sell_orders(sell_order.user_id, sell_order.server_id, sell_order.item_tag)
            else:
                sell_order.amount -= match_amount

            fulfilled_total += match_amount
            total_spent += total_price
            amount -= match_amount

            await update_sell_order(sell_order)

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
                return

            company.capital -= total_price
            await add_company_item(user_id, server_id, item_tag, purchasable_amount)
            market_entry.stockpile -= purchasable_amount



            await update_company(company)
            await update_market_item(market_entry)

            await interaction.followup.send(
                embed=discord.Embed(
                    title="NPC Market Purchase",
                    description=f"You bought **{purchasable_amount}x {item_tag}** from the NPC market for **${(total_price/purchasable_amount):.2f}** each. Total: **${total_price:.2f}**.",
                    color=discord.Color.green()
                )
            )

            # Preis anpassen
            factor = 1 + 0.005 * purchasable_amount
            market_entry.min_price = market_entry.min_price * factor
            market_entry.max_price = market_entry.max_price * factor
            await update_market_item(market_entry)
            return

        # Nicht vollständig erfüllt → neue BuyOrder anlegen
        if amount > 0:
            new_order = BuyOrder(
                user_id=user_id,
                item_tag=item_tag,
                server_id=server_id,
                amount=amount,
                unit_price=unit_price,
                is_company=True
            )
            await add_object(new_order, "Buy_Order")

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Company Buy Order Placed",
                    description=f"A buy order for **{amount}x {item_tag}** at **${unit_price:.2f}** has been created.",
                    color=discord.Color.green()
                )
            )


    @app_commands.command(
        name="info",
        description="View important info about your company."
    )
    async def info(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /company info")
        

        target_user = interaction.user
        user_id = int(target_user.id)
        server_id = int(interaction.guild.id)

 
        # Primär: Firma direkt durch Eigentum suchen
        company = await get_company(user_id, server_id)

        if not company:
            # Sekundär: prüfen, ob Spieler Arbeiter einer Firma ist
            player = await get_player(user_id, server_id)

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
            company = await get_company(player.company_entrepreneur_id, server_id)

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
        players = await get_employees(company.entrepreneur_id, server_id)

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
        requests = await get_join_requests(company.entrepreneur_id, server_id)

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

        items = await get_company_inventory(company.entrepreneur_id, server_id)

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
        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /company deposit {value}")

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

        # Player prüfen
        player = await get_player(user_id, server_id)
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
            await add_object(player, "Players")

        # Firma prüfen
        company = await get_company(user_id, server_id)
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

        await update_player(player)
        await update_company(company)

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

        # Player prüfen
        player = await get_player(user_id, server_id)
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
            await add_object(player, "Players")

        # Firma prüfen
        company = await get_company(user_id, server_id)
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

        await update_player(player)
        await update_company(company)

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
        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /company create {name}")

        user_id = int(interaction.user.id)
        server_id = int(interaction.guild.id)

        print("company_create test 1")

        # Player laden oder erstellen
        player = await get_player(user_id, server_id)
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
            await add_object(player, "Players")

        print("company_create test 2")
            
        # Check: Hat bereits eine Firma?
        existing = await get_company(user_id, server_id)
        if existing:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description="You already own a company.",
                    color=discord.Color.red()
                ), ephemeral=True
            )
            return
        
        print("company_create test 3")

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

        print("company_create test 4")


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
            taxes_owed=0,
            worksteps=""
        )
        player.job = "Entrepreneur"
        await add_object(company, "Companies")
        await update_player(player)

        print("company_create test 5")

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

        target_user = user or interaction.user
        target_user_id = int(target_user.id)
        server_id = int(interaction.guild.id)

        # Adminrechte prüfen, wenn Fremdfirma
        if user:
            gov = await get_government(server_id)
            if not gov:
                gov = get_default_government(server_id)
                await add_object(gov, "Government")

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
        company = await get_company(target_user_id, server_id)
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
        player = await get_player(target_user_id, server_id)
        if player:
            player.job = ""

        player.money += company.capital

        # CompanyItems übertragen
        company_items = await get_company_inventory(target_user_id, server_id)

        for item in company_items:
            await add_player_item(
                user_id=target_user_id,
                server_id=server_id,
                item_tag=item.item_tag,
                amount=item.amount,
            )
            await delete_company_item(company_entrepreneur_id=target_user_id, item_tag=item.item_tag, server_id=server_id)

        # Alle Spieler entkoppeln, die bei der Company angestellt waren
        await fire_employees(target_user_id, server_id)

        # Firma löschen
        await delete_company(target_user_id, server_id)

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

    company = await get_company(user_id, server_id)

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


    producible_tags = set(await get_producible_items())

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
    await update_company(company)

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
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /work {item}", flush=True)

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    player = await get_player(user_id, server_id)
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
    company = await get_company(player.company_entrepreneur_id, server_id)
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
    has_tool = await has_player_item(user_id, server_id, "Tool")
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
    await update_player(player)
    await update_company(company)
    await add_owed_taxes(user_id=player.id, server_id=server_id,
                            amount=company.wage, is_company=False)
    
    item_obj = await get_item(item)
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

    ingredients = {}
    if item_obj.ingredients:
        for entry in item_obj.ingredients.split(","):
            name, qty = entry.split(":")
            ingredients[name] = int(qty)

    # Wenn Worksteps = 0, dann Ressourcen prüfen und verbrauchen
    if worksteps_list[item_index] <= 0:
        for tag, required_amount in ingredients.items():
            company_item = await get_company_item(company.entrepreneur_id, server_id, tag)
            if not company_item or company_item.amount < required_amount:
                await interaction.followup.send(embed=discord.Embed(
                    title="Not enough resources!",
                    description=f"You need: " + ", ".join(f"{v}x {k}" for k, v in ingredients.items()),
                    color=discord.Color.red()
                ), ephemeral=True)
                return

        # Ressourcen abziehen
        for tag, required_amount in ingredients.items():
            company_item = await get_company_item(company.entrepreneur_id, server_id, tag)
            company_item.amount -= required_amount
            await update_company_item(company_item)

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

    await update_company(company)
    await update_player(player)

    embed = discord.Embed(color=discord.Color.green())

    if worksteps_list[item_index] <= 0:
        # Item wurde fertiggestellt
        await add_company_item(user_id=company.entrepreneur_id, server_id=server_id, item_tag=item, amount=1)
        embed.title = "Item Produced!"
        embed.description = f"You produced **1x {item}** for your company."
    else:
        embed.title = "Work Step Completed"
        embed.description = f"You worked on **{item}**. {worksteps_list[item_index]} steps remaining."
    embed.add_field(name="Money", value=f"${(player.money - company.wage):.2f} + ${company.wage:.2f} -> ${player.money:.2f}")
    embed.add_field(name=f"Tool Durability", value=f"{durability} -> {durability - 1}")
    embed.add_field(name="Hunger", value=f"{old_hunger} -> {player.hunger}")
    embed.add_field(name="Thirst", value=f"{old_thirst} -> {player.thirst}")

    await interaction.followup.send(embed=embed)





@client.tree.command(
    name="join",
    description="Use this to ask to join a company",
    guild=guild_id
)
@app_commands.describe(user="The user who owns the company that you want to join")
async def join(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /join {user}")

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
    

    # Check if requester is already in a company
    player = await get_player(requester_id, server_id)
    if player is None:
        player = get_default_player(requester_id, server_id)
        await add_object(player, "Players")


    if player.company_entrepreneur_id is not None:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error!",
                description="You are already working in a company. Leave it first using `/job jobless`.",
                color=discord.Color.red()
            ), ephemeral=True
        )
        return

    # Check if target user owns a company
    company = await get_company(entrepreneur_id, server_id)
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
    existing_request = await get_user_join_request(entrepreneur_id, server_id, requester_id)
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
    await add_object(join_request, "Company_Join_Requests")

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
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /hire {user}")

    entrepreneur_id = int(interaction.user.id)
    target_user_id = int(user.id)
    server_id = int(interaction.guild.id)

    # Existiert die Firma?
    company = await get_company(entrepreneur_id, server_id)
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
    request = await get_user_join_request(entrepreneur_id, server_id, target_user_id)
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
    player = await get_player(target_user_id, server_id)
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
        await add_object(player, "Players")

    # Spieler zur Firma hinzufügen
    player.job = "Worker"
    player.company_entrepreneur_id = entrepreneur_id

    # Join-Request löschen
    await delete_join_requests(entrepreneur_id, player.id, server_id)
    await update_player(player)

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

    # MarketItem abrufen
    market_entry = await get_market_item(server_id, item)
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

    now = datetime.now()

    # BuyOrders abrufen
    buy_orders = await get_item_buy_orders(server_id, market_entry.item_tag, now)

    # SellOrders abrufen
    sell_orders = await get_item_sell_orders(server_id, market_entry.item_tag, now)

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

    now = datetime.utcnow()

    # Sender prüfen
    sender = await get_player(sender_id, server_id)

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
            created_at=datetime.utcnow(),
            company_entrepreneur_id=None,
            taxes_owed=0,
            work_cooldown_until=None,
            job_switch_cooldown_until=None,
            company_creation_cooldown_until=None,
            gift_cooldown_until=None
        )
        await add_object(sender, "Players")

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
    receiver = await get_player(receiver_id, server_id)

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
        await add_object(receiver, "Players")

    # Transaktion durchführen
    sender.money -= value
    receiver.money += value
    sender.gift_cooldown_until = now + GIFT_COOLDOWN

    await update_player(sender)
    await update_player(receiver)

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

    # Player prüfen oder erstellen
    player = await get_player(user_id, server_id)
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
        await add_object(player, "Players")

    if player.debt > 0:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Debt Limit Reached",
                description="You can't take out loans while you still have debt",
                color=discord.Color.red()
            ), ephemeral=True
        )
        return

    # Zinsrate aus Government abfragen
    government = await get_government(server_id)
    if not government:
        government = get_default_government(server_id)
        await add_object(government, "Government")

    interest_rate = government.interest_rate or 0.30  # Fallback auf 30 %, falls None
    interest_amount = round(value * (1 + interest_rate), 2)

    # Geld & Schulden setzen
    player.money += value
    player.debt += interest_amount

    await update_player(player)

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
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /paydebt {value}")

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

    player = await get_player(user_id, server_id)

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
        await add_object(player, "Players")

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

    await update_player(player)

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
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /setmoney {user} {value}")

    server_id = int(interaction.guild.id)
    executor_roles = [role.id for role in interaction.user.roles]

    # Check government
    gov = await get_government(server_id)
    if not gov:
        gov = get_default_government(server_id)
        await add_object(gov, "Government")

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
    player = await get_player(user_id, server_id)

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
        await add_object(player, "Players")

    # Apply money/debt
    if value >= 0:
        player.money = value
        player.debt = 0.0
    else:
        player.money = 0.0
        player.debt = abs(value)

    await update_player(player)

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
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /addmoney {user} {value}")

    server_id = int(interaction.guild.id)
    user_id = int(user.id)
    executor_roles = [role.id for role in interaction.user.roles]

    gov = await get_government(server_id)
    if not gov:
        gov = get_default_government(server_id)
        await add_object(gov, "Government")

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
    player = await get_player(user_id, server_id)

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
        await add_object(player, "Players")

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

    await update_player(player)

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
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /setsupply item:{item}, value:{value}")

    server_id = int(interaction.guild.id)
    user_roles = [role.id for role in interaction.user.roles]

    gov = await get_government(server_id)
    if not gov:
        gov = get_default_government(server_id)
        await add_object(gov, "Government")

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

    market_item = await get_market_item(server_id, item)

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
    await update_market_item(market_item)

    await interaction.followup.send(
        embed=discord.Embed(
            title="Stockpile Updated",
            description=f"Stockpile of `{market_item.item_tag}` has been set to **{value}**.",
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

    gov = await get_government(server_id)
    if not gov:
        gov = get_default_government(server_id)
        await add_object(gov, "Government")

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

    market_item = await get_market_item(server_id, item)

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
    await update_market_item(market_item)

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
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /setdebt {user} {value}")

    server_id = int(interaction.guild.id)
    user_roles = [role.id for role in interaction.user.roles]
    target_user_id = int(user.id)

    gov = await get_government(server_id)
    if not gov:
        gov = get_default_government(server_id)
        await add_object(gov, "Government")

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

    player = await get_player(target_user_id, server_id)

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
        await add_object(player, "Players")

    new_debt = max(0, value)  # Negative Werte zu 0 machen
    player.debt = new_debt
    await update_player(player)

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

    # Government prüfen und ggf. Default anlegen
    gov = await get_government(server_id)
    if not gov:
        gov = get_default_government(server_id)
        await add_object(gov, "Government")

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
    player = await get_player(target_user_id, server_id)
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
        await add_object(player, "Players")

    # Debt anpassen, darf nicht < 0 sein
    player.debt = max(0, player.debt + value)
    await update_player(player)

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

    # Government prüfen und ggf. anlegen
    gov = await get_government(server_id)
    if not gov:
        gov = get_default_government(server_id)
        await add_object(gov, "Government")

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
    player = await get_player(target_user_id, server_id)
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
        await add_object(player, "Players")

    # Prüfen, ob Item existiert
    item_obj = await get_item(item)
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
    await add_player_item(target_user_id, server_id, item, amount)

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

    # Government prüfen und ggf. anlegen
    gov = await get_government(server_id)
    if not gov:
        gov = get_default_government(server_id)
        await add_object(gov, "Government")

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
    player = await get_player(target_user_id, server_id)
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
        await add_object(player, "Players")

    # PlayerItem abrufen
    player_item = await get_player_item(target_user_id, server_id,  item)
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
    await update_player_item(player_item)

    # Item löschen, wenn amount 0
    if player_item.amount <= 0:
        await delete_player_item(target_user_id, player_item.item_tag, server_id)


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
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /bailout {user}")

    server_id = int(interaction.guild.id)
    target_user_id = int(user.id)
    user_roles = [role.id for role in interaction.user.roles]

    # Government laden oder erstellen
    gov = await get_government(server_id)
    if not gov:
        gov = get_default_government(server_id)
        await add_object(gov, "Government")

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
    player = await get_player(target_user_id, server_id)
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
        await add_object(player, "Players")

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

    await update_player(player)
    await update_government(gov)

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
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /leaderboard")

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    players = await get_all_players(server_id)

    companies = await get_all_companies(server_id)

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

    server_id = int(interaction.guild.id)

    # Fetch item
    item_obj = await get_item(item)

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

    total_cost = 0.0
    lines = []

    for entry in item_obj.ingredients.split(","):
        tag, amount_str = entry.split(":")
        amount = int(amount_str)

        # Fetch market price
        market_entry = await get_market_item(server_id, tag)

        price = market_entry.max_price if market_entry else 0.0
        cost = price * amount
        total_cost += cost

        lines.append(f"• {amount}x {tag}:  ${cost:.2f}")
    lines.append(f"**Worksteps: {item_obj.worksteps}**")

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
async def buymaterials(interaction: discord.Interaction, item: str, amount: int = 1, buy_price: float = 1.0):
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
                ), color=discord.Color.red()
            ), ephemeral = True
        )
        return

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    # Company check
    company = await get_company(user_id, server_id)
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
    item_data = await get_item(item)
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

        market_item = await get_market_item(server_id, tag)
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
            existing_order = await get_own_buy_orders(user_id, server_id, tag, unit_price, is_company=True)

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
                )
                await add_object(new_order, "Buy_Orders")
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
        await update_company(company)

        for tag, qty, _, _ in purchases:
            ci = await get_company_item(user_id, server_id, tag)
            if ci:
                ci.amount += qty
                await update_company_item(ci)
            else:
                new_item = CompanyItem(
                    server_id=server_id,
                    company_entrepreneur_id=user_id,
                    item_tag=tag,
                    amount=qty
                )
                await add_object(new_item, "Company_Items")

        # Stock reduzieren und Preise leicht anpassen
        for tag, qty, unit_price, _ in purchases:
            mi = await get_market_item(server_id, tag)
            if mi:
                mi.stockpile -= qty
                mi.min_price = round(mi.min_price * 1.005, 2)
                mi.max_price = round(mi.max_price * 1.005, 2)

        await update_market_item(mi)

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
        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /tax view")
        
        server_id = interaction.guild.id

        players = await get_tax_owing_players(server_id)

        companies = await get_tax_owing_companies(server_id)

        lines = []

        for company in companies:
            owner = await interaction.client.fetch_user(company.entrepreneur_id)
            lines.append(f"🏭 **{owner.display_name}**'s company owes ${company.taxes_owed:.2f}")

        for player in players:
            user = await interaction.client.fetch_user(player.id)
            lines.append(f"🧍 **{user.display_name}** owes ${player.taxes_owed:.2f}")

        

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

        player = await get_player(user_id, server_id)
        if not player:
            # Standardwerte
            player = get_default_player()
            await add_object(player, "Players")

        company = await get_company(user_id, server_id)
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
            await update_company(company)

        if player.taxes_owed > 0 and amount > 0:
            pay = min(player.taxes_owed, player.money, amount)
            player.taxes_owed -= pay
            player.money -= pay
            paid += pay
            msg += f"🧍 Paid ${pay:.2f} in personal taxes."
            await update_player(player)

        # ➕ Regierung laden und Geld in die Treasury
        gov = await get_government(server_id)
        if not gov:
            gov = get_default_government(server_id)
            await add_object(government, "Government")

        gov.treasury += paid

        await update_government(gov)

        if paid == 0:
            await interaction.followup.send(embed=discord.Embed(
                title="No Money",
                description="You don't have any money, so you can't pay any taxes.",
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
        await interaction.response.defer(thinking=True)
        print(f"{interaction.user}: /tax rate {amount}")
        server_id = interaction.guild.id
        user_roles = [r.id for r in interaction.user.roles]

        gov = await get_government(server_id)
        if not gov:
            gov = get_default_government(server_id)
            await add_object(gov, "Government")

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
        await update_government(gov)

        await interaction.followup.send(embed=discord.Embed(
            title="Tax Rate Updated",
            description=f"📊 The new tax rate is **{amount * 100:.1f}%**.",
            color=discord.Color.green()
        ))



@client.tree.command(name="government", description="Shows information about the current government.")
@app_commands.guilds(guild_id)
async def government(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /government")
    server_id = interaction.guild.id

    gov = await get_government(server_id)

    if not gov:
        gov = get_default_government(server_id)
        await add_object(gov, "Government")

    # Rollen auflösen
    guild = interaction.guild
    governing_role = discord.utils.get(guild.roles, id=gov.governing_role) if gov.governing_role else None
    admin_role = discord.utils.get(guild.roles, id=gov.admin_role) if gov.admin_role else None

    embed = discord.Embed(
        title="Government Overview",
        color=discord.Color.yellow()
    )
    dt = datetime.fromisoformat(gov.created_at)
    embed.add_field(name="📅 Created At", value=dt.strftime("%d.%m.%Y %H:%M UTC"), inline=False)
    embed.add_field(name="💸 Tax Rate", value=f"{gov.taxrate * 100:.2f}%", inline=True)
    embed.add_field(name="🏦 Interest Rate", value=f"{gov.interest_rate * 100:.2f}%", inline=True)
    embed.add_field(name="💰 Treasury", value=f"${gov.treasury:,.2f}", inline=False)
    embed.add_field(name="🎲 Gambling Pool", value=f"${gov.gambling_pool:,.2f}", inline=False)
    embed.add_field(name="🎓 Governing Role", value=governing_role.mention if governing_role else "None", inline=True)
    embed.add_field(name="🔧 Admin Role", value=admin_role.mention if admin_role else "None", inline=True)


    # GDP der letzten 7 Tage holen
    today = date.today()
    seven_days_ago = today - timedelta(days=6)

    gdp_entries = await get_all_gdp_entries(server_id, seven_days_ago)


    if gdp_entries:
        gdp_text = ""
        for entry in gdp_entries:
            entry_date = (
                datetime.fromisoformat(entry.date).date()
                if isinstance(entry.date, str)
                else entry.date
            )
            day_label = "📅 Today" if entry_date == today else entry_date.strftime("%d.%m.%Y")
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

    company = await get_company(user_id, server_id)

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
    await update_company(company)

    await interaction.followup.send(
        embed=discord.Embed(
            title="Wage Updated",
            description=f"The wage for your company is now set to **${amount:.2f}**.",
            color=discord.Color.green()
        )
    )




@client.tree.command(name="subsidize", description="Used by government officials to subsidize certain companies", guild=guild_id)
@app_commands.describe(user="The user who's company you want to subsidize", amount="The amount of money you want to give that company")
async def init_subsidize(interaction: discord.Interaction, user: discord.User | discord.Member, amount: int):
    await interaction.response.defer(thinking=True)
    await subsidize(interaction, user, amount)

@client.tree.command(name="sponsor", description="Used by government officials to sponsor gambling", guild=guild_id)
@app_commands.describe(amount="The amount of money you want to put into the gambling pool.")
async def init_sponsor(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(thinking=True)
    await sponsor(interaction, amount)


@client.tree.command(name="roulette", description="Bet money on red or black!", guild=guild_id)
@app_commands.describe(
    color="Choose your color",
    amount="How much do you want to bet?"
)
@app_commands.choices(color=[
    app_commands.Choice(name="red", value="red"),
    app_commands.Choice(name="black", value="black"),
])
async def init_roulette(interaction: discord.Interaction, color: app_commands.Choice[str], amount: float):
    await interaction.response.defer(thinking=True)
    await roulette(interaction, color.value, amount)


# Registrierung
client.tree.add_command(OrderCommandGroup(), guild=guild_id)
client.tree.add_command(CompanyGroup(), guild=guild_id)
client.tree.add_command(TaxCommandGroup(), guild=guild_id)

client.run(TOKEN)

#@app.on_event("startup")
#async def startup_event():
#    import asyncio
#    asyncio.create_task(client.start(TOKEN))