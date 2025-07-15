from discord import Interaction, Embed, Color

from src.db.db_calls import get_player, add_object, update_player
from src.helper.defaults import get_default_player
from src.helper.item import has_player_item, remove_player_item

async def eat(interaction: Interaction, direct_execution = True):
    if direct_execution: print(f"{interaction.user}: /eat")
    await interaction.response.defer(thinking=True)
    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    player = await get_player(user_id, server_id)

    if not player:
        player = get_default_player(user_id, server_id)
        add_object(player, "Players")

    if await check_if_hunger_full(interaction, player): return

    if await check_has_grocery(interaction, player): return

    await remove_player_item(user_id, server_id, "Grocery", 1)

    player.hunger = 100

    await update_player(player)

    embed = Embed(
        title="Success!",
        description="You just consumed one grocery! Your hunger bar is now full again!",
        color=Color.green()
    )
    await interaction.followup.send(embed=embed)

async def check_if_hunger_full(interaction, player):
    if player.hunger >= 100:
        embed = Embed(
            title="Error!",
            description="Your hunger bar is completely full! There is no need to eat!",
            color=Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return True
    return False

async def check_has_grocery(interaction, player):
    has_grocery = await has_player_item(player.id, player.server_id, "Grocery")
    if not has_grocery:
        embed = Embed(
            title="Error!",
            description="You don't have any groceries! Use **/buy** to buy groceries.",
            color=Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return True
    return False