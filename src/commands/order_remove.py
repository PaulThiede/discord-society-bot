from discord import Interaction, Embed, Color

from datetime import datetime

from src.db.db_calls import get_sell_orders, get_own_item_sell_orders, get_own_sell_orders, get_company, \
    delete_buy_orders, delete_sell_orders
from src.helper.item import add_company_item, add_player_item


async def order_remove(interaction: Interaction, item_tag: str, price: float | None = None):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /order remove item_tag:{item_tag}, price:{price}")

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    now = datetime.now()
    if price is None:
        sell_orders = await get_own_item_sell_orders(user_id, server_id, item_tag, now)
    else:
        sell_orders = await get_own_sell_orders(user_id, server_id, item_tag, price, now, is_company=False)

    # Items zurückgeben
    total_returned = 0
    for order in sell_orders:
        if order.is_company:
            # Gib Items der Firma zurück
            company = get_company(user_id, server_id)
            if company:
                await add_company_item(
                    user_id=user_id,
                    server_id=server_id,
                    item_tag=item_tag,
                    amount=order.amount,
                )
        else:
            # Gib Items dem Spieler zurück
            await add_player_item(
                user_id=user_id,
                server_id=server_id,
                item_tag=item_tag,
                amount=order.amount,
            )
        total_returned += order.amount

    deleted_buy = await delete_buy_orders(user_id, server_id, item_tag, price)

    deleted_sell = await delete_sell_orders(user_id, server_id, item_tag, price)

    if deleted_buy.rowcount == 0 and deleted_sell.rowcount == 0:
        await interaction.followup.send(
            embed=Embed(
                title="Error!",
                description=f"No matching orders found for `{item_tag}`{' at $' + str(price) if price else ''}.",
                color=Color.red()
            )
        )
    else:
        await interaction.followup.send(
            embed=Embed(
                title="Orders Removed",
                description=f"Deleted **{deleted_buy.rowcount}** buy order(s) and **{deleted_sell.rowcount}** sell order(s) for `{item_tag}`{' at $' + str(price) if price else ''}.\n"
                            f"Returned **{total_returned}x {item_tag}** to your inventory.",
                color=Color.green()
            )
        )