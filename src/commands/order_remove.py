from discord import Interaction, Embed, Color

from datetime import datetime

from src.db.db_calls import get_sell_orders, get_own_item_sell_orders, get_own_sell_orders, get_company, \
    delete_buy_orders, delete_sell_orders
from src.helper.item import add_company_item, add_player_item


async def order_remove(interaction: Interaction, item_tag: str, price: float | None = None):
    print(f"{interaction.user}: /order remove item_tag:{item_tag}, price:{price}")
    try:

        user_id = int(interaction.user.id)
        server_id = int(interaction.guild.id)

        now = datetime.now()
        if price is None:
            sell_orders = await get_own_item_sell_orders(user_id, server_id, item_tag, now, "both")
        else:
            sell_orders = await get_own_sell_orders(user_id, server_id, item_tag, price, "both")

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

        await delete_buy_orders(user_id, server_id, item_tag, price)

        await delete_sell_orders(user_id, server_id, item_tag, price)

        await interaction.followup.send(
            embed=Embed(
                title="Orders Removed",
                description=f"Deleted your order(s) for **{item_tag}**{' at $' + str(price) if price else ''}.\n"
                            f"Returned **{total_returned}x {item_tag}** to your inventory.",
                color=Color.green()
            )
        )
    except Exception as e:
        print(e)