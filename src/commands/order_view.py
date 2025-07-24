from discord import Interaction, User, Embed, Color

from datetime import datetime

from src.db.db_calls import get_all_own_buy_orders, get_all_own_sell_orders


async def order_view(interaction: Interaction, user: User | None = None):
    await interaction.response.defer(thinking=True)
    print(f"{interaction.user}: /order view user:{user}")

    target_user = user or interaction.user
    user_id = int(target_user.id)
    server_id = int(interaction.guild.id)
    now = datetime.now()

    buy_orders = await get_all_own_buy_orders(user_id, server_id, now)

    sell_orders = await get_all_own_sell_orders(user_id, server_id, now)

    embed = Embed(
        title=f"{target_user.display_name}'s Active Orders",
        color=Color.yellow()
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