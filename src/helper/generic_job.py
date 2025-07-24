from typing import List

from discord import Interaction

from src.db.db_calls import get_player, add_object
from src.helper.defaults import get_default_player
from src.helper.player_checks import check_if_employed, check_if_on_cooldown, get_tool, check_hunger_thirst_bar
from src.helper.randoms import generate_resources
from src.helper.item import use_item, add_player_item
from src.helper.embed_creators import create_job_embed

async def execute_job(interaction: Interaction, job_name: str, job_items: List[str], err_message: str, resource_choices: List[str], job_verb: str):
    try:
        user_id = int(interaction.user.id)
        server_id = int(interaction.guild.id)

        print("generic_job test 1")

        player = await get_player(user_id, server_id)

        if not player:
            player = get_default_player(user_id, server_id)
            await add_object(player, "Players")

        print("generic_job test 2")

        if await check_if_employed(interaction, player, job_name): return

        print("generic_job test 3")

        tool = await get_tool(interaction, player, job_items, err_message)
        if not tool: return

        print("generic_job test 4")

        old_hunger, old_thirst = await check_hunger_thirst_bar(interaction, player)
        if not old_hunger: return

        print("generic_job test 5")

        if await check_if_on_cooldown(interaction, player): return

        print("generic_job test 6")

        resource, amount = generate_resources(resource_choices, tool)

        print("generic_job test 7")

        durability = await use_item(user_id, server_id, tool)

        print("generic_job test 8")

        await add_player_item(user_id, server_id, resource, amount)

        print("generic_job test 9")

        embed = create_job_embed(player, resource, amount, durability, old_hunger, old_thirst, tool, job_verb)
        await interaction.followup.send(embed=embed)

        print("generic_job test 10")
    except Exception as e:
        print(e)