from discord import Interaction, Embed, Color, app_commands

from src.db.db_calls import get_player, add_object, update_player
from src.helper.defaults import get_default_player
from src.helper.item import has_player_item, remove_player_item
from src.commands.eat import eat
from src.commands.drink import drink


async def consume(interaction: Interaction, item: app_commands.Choice[str]):
    print(f"{interaction.user}: /consume item:{item.value}")

    await interaction.response.defer(thinking=True)

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)
    item_tag = item.value

    if item_tag == "Water":
        await drink(interaction)
        return
    elif item_tag == "Grocery":
        await eat(interaction)
        return

    player = await get_player(user_id, server_id)

    if not player:
        player = get_default_player(user_id, server_id)
        add_object(player, "Players")

    if await check_if_bars_full(interaction, player): return

    if await check_has_fish(interaction, player): return

    await remove_player_item(user_id, server_id, "Fish", 1)

    player.thirst += 5
    player.hunger += 15

    await update_player(player)

    embed = Embed(
        title="Success!",
        description=f"You just consumed one fish! You now have {player.hunger}/100 hunger and {player.thirst}/100 thirst",
        color=Color.green()
    )
    await interaction.followup.send(embed=embed)

async def check_if_bars_full(interaction, player):
    if player.thirst >= 100 and player.hunger >= 100:
        embed = Embed(
            title="Error!",
            description="Both your thirst and hunger bars are completely full! There is no need to consume fish!",
            color=Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return True
    return False

async def check_has_fish(interaction, player):
    has_fish = await has_player_item(player.id, player.server_id, "Fish")
    if not has_fish:
        embed = Embed(
            title="Error!",
            description="You don't have any fish! Use **/buy** to buy fish.",
            color=Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return True
    return False