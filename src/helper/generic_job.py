from typing import List

from discord import Interaction

from src.db.db_calls import get_player, add_object
from src.helper.defaults import get_default_player
from src.helper.player_checks import check_if_employed, check_if_on_cooldown, get_tool, check_hunger_thirst_bar
from src.helper.randoms import generate_resources
from src.helper.item import use_item, add_player_item
from src.helper.embed_creators import create_job_embed

async def execute_job(interaction: Interaction, job_name: str, job_items: List[str], err_message: str, resource_choices: List[str], job_verb: str):

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    player = await get_player(user_id, server_id)

    if not player:
        player = get_default_player(user_id, server_id)
        await add_object(player, "Players")

    if await check_if_employed(interaction, player, job_name): return

    if await check_if_on_cooldown(interaction, player): return

    tool = await get_tool(interaction, player, job_items, err_message)
    if not tool: return

    old_hunger, old_thirst = await check_hunger_thirst_bar(interaction, player)
    if not old_hunger: return

    resource, amount = generate_resources(resource_choices, tool)

    durability = await use_item(user_id, server_id, tool)

    await add_player_item(user_id, server_id, resource, amount)

    embed = create_job_embed(player, resource, amount, durability, old_hunger, old_thirst, tool, job_verb)
    await interaction.followup.send(embed=embed)