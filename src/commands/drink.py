from discord import Interaction, Embed, Color

from src.db.db_calls import get_player, add_object, update_player
from src.helper.defaults import get_default_player
from src.helper.item import has_player_item, remove_player_item

async def drink(interaction: Interaction, direct_execution = True):
    if direct_execution: print(f"{interaction.user}: /drink")
    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    player = await get_player(user_id, server_id)

    if not player:
        player = get_default_player(user_id, server_id)
        await add_object(player, "Players")

    if await check_if_thirst_full(interaction, player): return

    if await check_has_water(interaction, player): return

    await remove_player_item(user_id, server_id, "Water", 1)

    player.thirst = 100

    await update_player(player)

    embed = Embed(
        title="Success!",
        description="You just consumed one water! Your thirst bar is now full again!",
        color=Color.green()
    )
    await interaction.followup.send(embed=embed)

async def check_if_thirst_full(interaction, player):
    if player.thirst >= 100:
        embed = Embed(
            title="Error!",
            description="Your thirst bar is completely full! There is no need to drink!",
            color=Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return True
    return False

async def check_has_water(interaction, player):
    has_water = await has_player_item(player.id, player.server_id, "Water")
    if not has_water:
        embed = Embed(
            title="Error!",
            description="You don't have any water! Use **/buy** to buy water.",
            color=Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return True
    return False