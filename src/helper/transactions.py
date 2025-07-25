from discord import Embed, Color, Forbidden

from datetime import date

from src.db.db_calls import get_company, get_player, get_government, get_gdp_entry, add_object, update_player, \
    update_company, update_market_item, delete_sell_orders, delete_buy_orders, update_government_gdp
from src.db.models import BuyOrder, SellOrder, Player, Company
from src.helper.defaults import get_default_government, get_default_gdp_entry, get_default_player


async def transfer_money(interaction, order: BuyOrder | SellOrder, total_price,
                         match_amount, item_tag, buyer_type, seller_type,
                         buyer: Player | Company = None, seller: Player | Company = None):
    '''
    :param order: Either a buy or sell order
    :param buyer: If this is none, then this code is executed by the seller
    :param seller: If this is none, then this code is executed by the buyer
    '''
    order_type = None
    if seller is None:
        order_type = 'Sell'
        seller = await get_company(order.user_id, order.server_id) if seller_type == "company" else await get_player(order.user_id, order.server_id)
    elif buyer is None:
        order_type = 'Buy'
        buyer = await get_company(order.user_id, order.server_id) if buyer_type == "company" else await get_player(order.user_id, order.server_id)

    if not seller:
        if order_type == 'Sell':
            await delete_sell_orders(order.user_id, order.server_id, item_tag)
        else:
            await delete_buy_orders(order.user_id, order.server_id, item_tag)
        await interaction.followup.send(
            embed=Embed(
                title="Sell Order Removed",
                description="The person/company who made the sell orders no longer exists. Sell order removed.",
                color=Color.red()
            )
        )
        return

    if not buyer:
        if order_type == 'Sell':
            await delete_sell_orders(order.user_id, order.server_id, item_tag)
        else:
            await delete_buy_orders(order.user_id, order.server_id, item_tag)
        await interaction.followup.send(
            embed=Embed(
                title="Sell Order Removed",
                description="The person/company who made the buy orders no longer exists. Buy order removed.",
                color=Color.red()
            )
        )
        return

    if seller_type == "company":
        seller.capital += total_price
        await update_company(seller)
        await add_owed_taxes(user_id=seller.entrepreneur_id, server_id=buyer.server_id,
                         amount=total_price, is_company=True)
    else:
        seller.money += total_price
        await update_player(seller)
        await add_owed_taxes(user_id=seller.id, server_id=buyer.server_id,
                         amount=total_price, is_company=False)

    if buyer_type == "company":
        buyer.capital -= total_price
        await update_company(buyer)
    else:
        buyer.money -= total_price
        await update_player(buyer)
    
    

    try:
        user_obj = await interaction.client.fetch_user(order.user_id)
        await user_obj.send(embed=Embed(
            title=f"{order_type} Order Fulfilled",
            description=f"Your {order_type} order for **{match_amount}x {item_tag}** was fulfilled for **${total_price:.2f}**.",
            color=Color.green()
        ))
    except Forbidden:
        pass




async def add_owed_taxes(user_id: int, server_id: int, amount: float, is_company: bool = False):
    #print(f"Adding taxes for amount ${amount}")
    if amount <= 0:
        return
    

    await increase_gdp(server_id, amount)


    government = await get_government(server_id)
    if not government:
        government = get_default_government(server_id)
        await add_object(government, "Government")


    taxrate = government.taxrate or 0.0
    tax_amount = round(amount * taxrate, 2)

    if tax_amount <= 0:
        return  # Steuerbetrag zu gering

    if is_company:
        company = await get_company(user_id, server_id)
        if not company:
            return

        company.taxes_owed = (company.taxes_owed or 0) + tax_amount
        await update_company(company)

    else:
        player = await get_player(user_id, server_id)
        if not player:
            player = get_default_player(user_id, server_id)

        player.taxes_owed += tax_amount
        await update_player(player)





async def increase_gdp(server_id: int, amount: float):
    today = date.today()
    gdp_entry = await get_gdp_entry(server_id, today)
    if not gdp_entry:
        gdp_entry = get_default_gdp_entry(server_id, today)
        await add_object(gdp_entry, "Government_GDP")

    gdp_entry.gdp_value += amount
    await update_government_gdp(gdp_entry)

async def increase_npc_price(market_item, amount):
    factor = 1 + 0.005 * amount
    market_item.min_price = round(market_item.min_price * factor, 2)
    market_item.max_price = round(market_item.max_price * factor, 2)
    await update_market_item(market_item)

async def decrease_npc_price(market_item, amount):
    factor = 1 - 0.005 * amount
    market_item.min_price = round(market_item.min_price * factor, 2)
    market_item.max_price = round(market_item.max_price * factor, 2)
    await update_market_item(market_item)