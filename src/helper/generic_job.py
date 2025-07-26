from discord import Interaction, Embed, Color

from typing import List
from random import randint

from src.db.db_calls import get_player, add_object, get_company, update_player, update_company
from src.helper.defaults import get_default_player
from src.helper.player_checks import check_if_employed_multiple, check_if_on_cooldown, get_tool, check_hunger_thirst_bar
from src.helper.randoms import generate_resources, generate_rare_resources
from src.helper.item import use_item, add_player_item, add_company_item
from src.helper.embed_creators import create_job_embed
from src.helper.transactions import add_owed_taxes

async def execute_job(interaction: Interaction, job_name: str, job_items: List[List[str]], err_message: str, resource_choices: List[str], job_verb: str):
    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    player = await get_player(user_id, server_id)

    if not player:
        player = get_default_player(user_id, server_id)
        await add_object(player, "Players")

    if await check_if_employed_multiple(interaction, player, [job_name, "Worker"]): return

    tool = await get_tool(interaction, player, job_items, err_message)
    if not tool: return

    if player.job == "Worker":
        company = await get_company(player.company_entrepreneur_id, server_id)
        if company.capital < company.wage:
            await interaction.followup.send(embed=Embed(
                title="Not Enough Company Capital",
                description="The Company does not have enough money to pay you, so why should you work?",
                color=Color.red()
            ), ephemeral=True)
            return


    old_hunger, old_thirst = await check_hunger_thirst_bar(interaction, player)
    if not old_hunger: return

    if await check_if_on_cooldown(interaction, player): return

    resource, amount = None, None
    if player.job == "Miner":
        rng = randint(1,10)
        if rng == 1:
            resource, amount = generate_rare_resources(["Gold", "Diamond"], tool)
        else:
            resource, amount = generate_resources(resource_choices, tool)
    else:
        resource, amount = generate_resources(resource_choices, tool)

    durability = await use_item(user_id, server_id, tool)


    if player.job == "Worker":
        company = await get_company(player.company_entrepreneur_id, server_id)
        await add_company_item(player.company_entrepreneur_id, server_id, resource, amount)
        company.capital -= company.wage
        player.money += company.wage
        await update_player(player)
        await update_company(company)
        await add_owed_taxes(user_id=player.id, server_id=server_id,
                                amount=company.wage, is_company=False)

    else:
        await add_player_item(user_id, server_id, resource, amount)

    embed = create_job_embed(player, resource, amount, durability, old_hunger, old_thirst, tool, job_verb)
    await interaction.followup.send(embed=embed)