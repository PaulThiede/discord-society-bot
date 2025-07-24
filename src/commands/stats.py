from discord import Interaction, User, Member, Embed, Color

from src.db.db_calls import get_player, get_player_inventory, add_object
from src.helper.defaults import get_default_player
from src.helper.embed_creators import create_inventory_embed


async def stats(interaction: Interaction, user: User | Member = None):
    print(f"{interaction.user}: /stats: {user}")

    target_user = user or interaction.user
    user_id = int(target_user.id)
    server_id = int(interaction.guild.id)

    player = await get_player(user_id, server_id)

    if not player:
        player = get_default_player(user_id, server_id)
        await add_object(player, "Players")


    embed = create_stats_embed(target_user, player)
    items = await get_player_inventory(user_id, server_id)
    embed = create_inventory_embed(items, embed)
    await interaction.followup.send(embed=embed)


def create_stats_embed(target_user, player):
    embed = Embed(
        title=f"Stats for {target_user.display_name}",
        color=Color.yellow()
    )
    embed.add_field(name="Money", value=f"{player.money:.2f}", inline=True)
    embed.add_field(name="Debt", value=f"{player.debt:.2f}", inline=True)
    embed.add_field(name="Health", value=f"{player.health}", inline=True)
    embed.add_field(name="Hunger", value=f"{player.hunger}", inline=True)
    embed.add_field(name="Thirst", value=f"{player.thirst}", inline=True)
    embed.add_field(name="Job", value=player.job or "None", inline=True)
    embed.add_field(name="Taxes Owed", value=f"{player.taxes_owed:.2f}", inline=True)
    embed.set_footer(text=f"User ID: {target_user.id}")

    return embed