from discord import Embed, Color, Forbidden

from datetime import date

from src.db.db_calls import get_company, get_player, get_government, get_gdp_entry
from src.db.models import BuyOrder, SellOrder, Player, Company
from src.helper.defaults import get_default_government, get_default_gdp_entry


async def transfer_money(session, interaction, order: BuyOrder | SellOrder, total_price,
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
        await session.delete(order)
        await session.commit()
        await interaction.followup.send(
            embed=Embed(
                title="Sell Order Removed",
                description="The person/company who made the sell orders no longer exists. Sell order removed.",
                color=Color.red()
            )
        )
        return

    if not buyer:
        await session.delete(order)
        await session.commit()
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
    else:
        seller.money += total_price

    if buyer_type == "company":
        buyer.capital -= total_price
    else:
        buyer.money -= total_price

    await add_owed_taxes(session, user_id=seller.entrepreneur_id, server_id=buyer.server_id,
                         amount=total_price, is_company=True if seller_type == "company" else False)

    try:
        user_obj = await interaction.client.fetch_user(order.user_id)
        await user_obj.send(embed=Embed(
            title=f"{order_type} Order Fulfilled",
            description=f"Your {order_type} order for **{match_amount}x {item_tag}** was fulfilled for **${total_price:.2f}**.",
            color=Color.green()
        ))
    except Forbidden:
        pass




async def add_owed_taxes(session, user_id: int, server_id: int, amount: float, is_company: bool = False):
    if amount <= 0:
        return

    await increase_gdp(session, server_id, amount)

    government = get_government(session, server_id)
    if not government:
        government = get_default_government()
        session.add(government)
        session.commit()

    taxrate = government.taxrate or 0.0
    tax_amount = round(amount * taxrate, 2)

    if tax_amount <= 0:
        return  # Steuerbetrag zu gering

    if is_company:
        company = get_company(user_id, server_id)
        if not company:
            return

        company.taxes_owed = (company.taxes_owed or 0) + tax_amount

    else:
        player = get_player(user_id, server_id)
        if not player:
            return

        player.taxes_owed = (player.taxes_owed or 0) + tax_amount

    await session.commit()

async def increase_gdp(session, server_id: int, amount: float):
    today = date.today()
    gdp_entry = get_gdp_entry(session, server_id, today)
    if not gdp_entry:
        gdp_entry = get_default_gdp_entry(server_id, today)
        session.add(gdp_entry)

    gdp_entry.gdp_value += amount

async def increase_npc_price(session, market_item, amount):
    factor = 1 + 0.005 * amount
    market_item.min_price = round(market_item.min_price * factor, 2)
    market_item.max_price = round(market_item.max_price * factor, 2)
    await session.commit()

async def decrease_npc_price(session, market_item, amount):
    factor = 1 - 0.005 * amount
    market_item.min_price = round(market_item.min_price * factor, 2)
    market_item.max_price = round(market_item.max_price * factor, 2)
    await session.commit()