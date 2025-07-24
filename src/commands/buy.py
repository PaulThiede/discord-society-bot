from discord import Interaction, User, Member, Embed, Color

from datetime import datetime

from src.db.db_calls import get_item, get_player, get_own_buy_orders, get_market_item, get_all_items, get_sell_orders, add_object, update_player, update_buy_order, delete_sell_orders, update_sell_order, update_market_item
from src.helper.defaults import get_default_player, get_default_market_item, get_default_buy_order
from src.helper.item import add_player_item
from src.config import BUY_ORDER_DURATION
from src.helper.transactions import transfer_money, increase_npc_price


async def buy(
    interaction: Interaction,
    item: str,
    unit_price: float,
    amount: int = 1
):

    print(f"{interaction.user}: /buy item: {item}, unit_price: {unit_price}, amount: {amount}")


    if amount <= 0 or unit_price <= 0:
        await interaction.followup.send(
            embed=Embed(
                title="Error!",
                description="Amount and unit price must be greater than 0.",
                color=Color.red()
            ), ephemeral=True
        )
        return

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)



    item_tag = await check_item_exists(interaction, item)
    if not item_tag: return

    player = await get_player(user_id, server_id)

    if not player:
        player = get_default_player(user_id, server_id)
        await add_object(player, "Players")

    if await check_enough_money(interaction, player, item_tag, unit_price, amount): return

    if await check_existing_orders(interaction, user_id, server_id, item_tag, unit_price, amount): return

    await check_market_initialized(server_id, item_tag)

    amount = await handle_player_sell_orders(interaction, player, item_tag, unit_price, amount)

    market_item = await get_market_item(server_id, item_tag)

    if amount > 0 and unit_price >= market_item.max_price and market_item.stockpile > 0:
        amount = await buy_from_npc_market(interaction, player, market_item, amount)


    if amount > 0:
        now = datetime.now()
        new_order = get_default_buy_order(user_id, item_tag, server_id, amount, unit_price,
                                            now + BUY_ORDER_DURATION, False)
        await add_object(new_order, "Buy_Orders")

        await interaction.followup.send(
            embed=Embed(
                title="Buy Order Placed",
                description=f"A buy order for **{amount}x {item_tag}** at **${unit_price:.2f}** has been created.",
                color=Color.green()
            )
        )

async def check_item_exists(interaction, item):
    item_obj = await get_item(item)
    if not item_obj:
        await interaction.followup.send(
            embed=Embed(
                title="Error!",
                description=f"Item **{item}** does not exist.",
                color=Color.red()
            ), ephemeral=True
        )
        return False
    return item_obj.item_tag

async def check_enough_money(interaction, player, item_tag, unit_price, amount):
    if player.money < unit_price * amount:
        await interaction.followup.send(
            embed=Embed(
                title="Not Enough Money!",
                description=f"You are trying to buy **{amount}x {item_tag}** for **${unit_price * amount}**, but you only have **${player.money}**.",
                color=Color.red()
            ), ephemeral=True
        )
        return True
    return False

async def check_existing_orders(interaction, user_id, server_id, item_tag, unit_price, amount):
    now = datetime.now()
    expires_at = now + BUY_ORDER_DURATION

    existing_orders = await get_own_buy_orders(user_id, server_id, item_tag, unit_price, False)

    if len(existing_orders) > 0:
        existing_order = existing_orders[0]
        existing_order.amount += amount
        existing_order.expires_at = expires_at
        await update_buy_order(existing_order)

        await interaction.followup.send(
            embed=Embed(
                title="Buy Order Merged",
                description=(
                    f"Merged your buy orders for **{item_tag}** at **${unit_price}**.\n"
                    f"New total: **{existing_order.amount}x {item_tag}** = **${existing_order.amount * unit_price}**."
                ),
                color=Color.green()
            )
        )
        return True
    return False

async def check_market_initialized(server_id, item_tag):
    if await get_market_item(server_id, item_tag) is None:
        items = await get_all_items()

        for item in items:
            market_item = get_default_market_item(item, server_id)
            await add_object(market_item, "Market_Items")


async def handle_player_sell_orders(interaction, player, item_tag, unit_price, amount):
    fulfilled_total = 0
    total_spent = 0.0

    sell_orders = await get_sell_orders(player.server_id, item_tag, unit_price, datetime.now())

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

        await add_player_item(player.id, player.server_id, item_tag, match_amount)
        await transfer_money(interaction, sell_order, total_price, match_amount, item_tag,
                             "player", "company" if sell_order.is_company else "player", buyer=player)


        if sell_order.amount == match_amount:
            await delete_sell_orders(sell_order.user_id, sell_order.server_id, sell_order.item_tag, sell_order.unit_price)
        else:
            sell_order.amount -= match_amount
            await update_sell_order(sell_order)

        fulfilled_total += match_amount
        total_spent += total_price
        amount -= match_amount

        if amount == 0:
            await interaction.followup.send(
                embed=Embed(
                    title="Buy Order Fulfilled",
                    description=f"You bought **{fulfilled_total}x {item_tag}** from player orders for **${total_spent:.2f}**.",
                    color=Color.green()
                )
            )
            return 0

    if fulfilled_total > 0:
        await interaction.followup.send(
            embed=Embed(
                title="Buy Order Partially Fulfilled",
                description=f"You bought **{fulfilled_total}x {item_tag}** from player orders for **${total_spent:.2f}**.",
                color=Color.green()
            )
        )

    return amount



async def buy_from_npc_market(interaction, player, market_item, amount):
    print("    Trying to buy from NPC market")
    purchasable_amount = min(market_item.stockpile, amount)
    total_price = round(purchasable_amount * market_item.max_price, 2)

    if player.money < total_price:
        await interaction.followup.send(
            embed=Embed(
                title="Buy Order Cancelled",
                description=(
                    f"Insufficient funds to fulfill the rest of the order from the NPC market.\n"
                    f"Required: **${total_price}**, Available: **${player.money}**"
                ),
                color=Color.red()
            )
        )
        return

    player.money -= total_price
    await add_player_item(player.id, player.server_id, market_item.item_tag, purchasable_amount)

    await update_player(player)
    market_item.stockpile -= purchasable_amount

    await update_market_item(market_item)

    await interaction.followup.send(
        embed=Embed(
            title="NPC Market Purchase",
            description=f"You bought **{purchasable_amount}x {market_item.item_tag}** from the NPC market for **${market_item.max_price:.2f}** each. Total: **${total_price:.2f}**.",
            color=Color.green()
        )
    )

    await increase_npc_price(market_item, amount)

    amount -= purchasable_amount
    return amount
