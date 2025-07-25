from discord import Interaction, User, Member, Embed, Color

from datetime import datetime

from src.db.db_calls import get_item, get_player, get_own_buy_orders, get_market_item, get_all_items, get_sell_orders, \
    get_player_item, get_own_sell_orders, get_buy_orders, add_object, update_sell_order, delete_buy_orders, update_market_item, update_buy_order, update_player
from src.helper.defaults import get_default_player, get_default_market_item, get_default_buy_order, \
    get_default_sell_order
from src.helper.item import add_player_item, remove_player_item
from src.config import SELL_ORDER_DURATION
from src.helper.transactions import transfer_money, increase_npc_price, add_owed_taxes


async def sell(
    interaction: Interaction,
    item: str,
    unit_price: float = -1.0, # Used for when you just want to sell it at the npc price
    amount: int = 1
):
    print(f"{interaction.user}: /sell item: {item}, unit_price: {unit_price}, amount: {amount}")

    if (amount <= 0 or unit_price <= 0) and unit_price != -1:
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

    if not await has_enough_items(interaction, player, item_tag, amount): return

    if await check_existing_orders(interaction, user_id, server_id, item_tag, unit_price, amount): return

    await check_market_initialized(server_id, item_tag)

    market_item = await get_market_item(server_id, item_tag)

    if unit_price == -1:
        unit_price = market_item.min_price

    amount = await handle_player_buy_orders(interaction, player, item_tag, unit_price, amount)

    if amount > 0 and unit_price <= market_item.min_price:
        amount = await sell_to_npc_market(interaction, player, market_item, amount)

    if amount > 0:
        now = datetime.now()
        new_order = get_default_sell_order(user_id, item_tag, server_id, amount, unit_price,
                                            now + SELL_ORDER_DURATION, False)
        await add_object(new_order, "Sell_Orders")

        await interaction.followup.send(
            embed=Embed(
                title="Sell Order Placed",
                description=f"A sell order for **{amount}x {item_tag}** at **${unit_price:.2f}** has been created.",
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

async def has_enough_items(interaction, player, item_tag, amount):
    inv_item = await get_player_item(player.id, player.server_id, item_tag, amount)
    if not inv_item or inv_item.amount < amount:
        await interaction.followup.send(
            embed=Embed(
                title="Error!",
                description=f"You don't have enough **{item_tag}**.",
                color=Color.red()
            ), ephemeral=True
        )
        return False
    return True

async def check_existing_orders(interaction, user_id, server_id, item_tag, unit_price, amount):

    existing_orders = await get_own_sell_orders(user_id, server_id, item_tag, unit_price, False)

    if len(existing_orders) > 0:
        existing_order = existing_orders[0]
        existing_order.amount += amount
        await update_sell_order(existing_order)

        await interaction.followup.send(
            embed=Embed(
                title="Sell Order Merged",
                description=(
                    f"Merged your sell orders for **{item_tag}** at **${unit_price}**.\n"
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


async def handle_player_buy_orders(interaction, player, item_tag, unit_price, amount):
    total_sold = 0
    total_earned = 0.0

    buy_orders = await get_buy_orders(player.server_id, item_tag, unit_price, datetime.now())

    for buy_order in buy_orders:
        buyer_user = await get_player(buy_order.user_id, buy_order.server_id)
        buyer_money = round(buyer_user.money,2)

        print(f"Checking buy order for {item_tag} at ${buy_order.unit_price}")

        if total_sold >= amount:
            break

        match_amount = min(amount, buy_order.amount)
        total_price = round(match_amount * buy_order.unit_price, 2)

        if buyer_money < unit_price:
            continue

        if buyer_money < total_price:
            match_amount = int(round(player.money,2) // round(buy_order.unit_price,2))
            total_price = round(match_amount * round(buy_order.unit_price,2), 2)

        if match_amount <= 0:
            break


        await remove_player_item(player.id, player.server_id, item_tag, match_amount)
        await add_player_item(buy_order.user_id, buy_order.server_id, item_tag, match_amount)
        await transfer_money(interaction, buy_order, total_price, match_amount, item_tag,
                             "company" if buy_order.is_company else "player", "player" , seller=player)


        if buy_order.amount == match_amount:
            await delete_buy_orders(buy_order.user_id, buy_order.server_id, buy_order.item_tag, buy_order.unit_price)
        else:
            buy_order.amount -= match_amount
            await update_buy_order(buy_order)

        total_sold += match_amount
        total_earned += total_price
        amount -= match_amount


        if amount == 0:
            await interaction.followup.send(
                embed=Embed(
                    title="Sell Order Fulfilled",
                    description=f"You sold **{total_sold}x {item_tag}** to player orders for **${total_earned:.2f}**.",
                    color=Color.green()
                )
            )
            return 0

    if amount > 0 and total_sold > 0:
        await interaction.followup.send(
            embed=Embed(
                title="Sell Order Partially Fulfilled",
                description=f"You sold **{total_sold}x {item_tag}** to player orders for **${total_earned:.2f}**.",
                color=Color.green()
            )
        )

    return amount



async def sell_to_npc_market(interaction, player, market_item, amount):
    print("    Trying to sell to NPC market")
    total_price = round(amount * market_item.min_price, 2)

    player.money += total_price
    market_item.stockpile += amount
    await update_player(player)
    
    await add_owed_taxes(user_id=player.id, server_id=player.server_id, amount=total_price, is_company=False)
    await remove_player_item(player.id, player.server_id, market_item.item_tag, amount)

    
    await update_market_item(market_item)

    await interaction.followup.send(
        embed=Embed(
            title="NPC Market Selling",
            description=f"You sold **{amount}x {market_item.item_tag}** to the NPC market for **${market_item.min_price:.2f}** each. Total: **${total_price:.2f}**.",
            color=Color.green()
        )
    )

    amount = 0

    await increase_npc_price(market_item, amount)

    return amount
