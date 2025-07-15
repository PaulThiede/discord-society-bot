from discord import Embed, Color

from datetime import datetime

from src.db.db_calls import update_player
from src.helper.item import has_player_item
from src.helper.randoms import get_hunger_depletion, get_thirst_depletion
from src.config import WORK_COOLDOWN

async def check_if_employed(interaction, player, job):
    if not job in player.job:
        await interaction.followup.send(embed=Embed(
            title="Error!",
            description=f"You are not a {job}!",
            color=Color.red()
        ), ephemeral=True)
        return True
    return False

async def check_if_on_cooldown(interaction, player):
    now = datetime.now()
    if player.work_cooldown_until and player.work_cooldown_until > now:
        cooldown_ts = int(player.work_cooldown_until.timestamp())
        await interaction.followup.send(embed=Embed(
            title="Cooldown Active",
            description=f"⏳ You can work again <t:{cooldown_ts}:R>.",
            color=Color.red()
        ), ephemeral=True)
        return True

    player.work_cooldown_until = now + WORK_COOLDOWN
    update_player(player)

    return False

async def get_tool(interaction, session, player, items, err_message):
    tool = None
    for item in items:
        if item == "F" or item == "W" or item == "N" or item == "P":
            tool = f"Hand-{item}"
            continue
        if await has_player_item(session, player.id, player.server_id, item, min_amount=1): tool = item

    if not tool:
        await interaction.followup.send(embed=Embed(
            title="Error!",
            description=err_message,
            color=Color.red()
        ), ephemeral=True)
        return False
    return tool

async def check_hunger_thirst_bar(interaction, player):
    if player.hunger <= 0:
        await interaction.followup.send(embed=Embed(
            title="Error!",
            description="You are too hungry to work!",
            color=Color.red()
        ), ephemeral=True)
        return True

    if player.thirst <= 0:
        await interaction.followup.send(embed=Embed(
            title="Error!",
            description="You are too thirsty to work!",
            color=Color.red()
        ), ephemeral=True)
        return False, False

    old_hunger = player.hunger
    old_thirst = player.thirst
    player.hunger = max(0, player.hunger - get_hunger_depletion())
    player.thirst = max(0, player.thirst - get_thirst_depletion())
    update_player(player)

    return old_hunger, old_thirst