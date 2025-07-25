import random
import discord
from discord import app_commands
from typing import Literal
import asyncio

from src.db.db_calls import get_player, update_player, add_object, get_government, update_government
from src.helper.defaults import get_default_player, get_default_government

# Real European roulette wheel order (37 fields)
ROULETTE_WHEEL = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27,
    13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1,
    20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

# Mapping numbers to colors
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

def get_color(number: int) -> str:
    if number == 0:
        return "green"
    elif number in RED_NUMBERS:
        return "red"
    elif number in BLACK_NUMBERS:
        return "black"
    return "unknown"


async def roulette(
    interaction: discord.Interaction,
    color: str,
    amount: int
):

    print(f"{interaction.user}: /roulette {color} {amount}")

    user = interaction.user
    server_id = interaction.guild.id
    player = await get_player(user.id, server_id)

    if not player:
        player = get_default_player(user.id, server_id)
        await add_object(player, "Players")
        return

    if amount <= 0:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Invalid Amount",
                description="The amount must be greater than 0.",
                color=discord.Color.red()
            )
        )
        return
    
    if amount > 1000:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Invalid Amount",
                description="You cannot gamble for more than $1000!",
                color=discord.Color.red()
            )
        )
        return
    
    gov = await get_government(server_id)
    if not gov:
        gov = get_default_government(server_id)
        await add_object(gov, "Government")

    if amount > gov.gambling_pool:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Invalid Amount",
                description=f"The gambling pool only consists of ${gov.gambling_pool}, you cannot gamble for more!",
                color=discord.Color.red()
            )
        )
        return

    if player.money < amount:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Not Enough Money",
                description=f"You only have ${player.money}.",
                color=discord.Color.red()
            )
        )
        return
    
    player.money -= amount
    gov.gambling_pool += amount
    await update_player(player)
    await update_government(gov)

    # Animation: send initial spinning message
    wheel_message = await interaction.followup.send("🎲 Spinning the wheel...", wait=True)

    # Simulate ball movement
    steps = random.randint(12, 18)  # Total hops before landing
    history = []

    for i in range(steps):
        rolled = ROULETTE_WHEEL[(i % len(ROULETTE_WHEEL))]
        color_result = get_color(rolled)
        symbol = {"red": "🔴", "black": "⚫", "green": "🟢"}[color_result]
        history.append(f"{symbol} **{rolled}**")
        preview = " → ".join(history[-5:])  # Show last 5 rolls
        await wheel_message.edit(content=f"🎲 Ball rolling...\n{preview}")
        await asyncio.sleep(0.5 + i * 0.07)

    # Final result
    final_number = ROULETTE_WHEEL[(steps - 1) % len(ROULETTE_WHEEL)]
    final_color = get_color(final_number)
    print(f"Final color: {final_color}. User chosen color: {color}")

    if final_color == color:
        player.money += 2 * amount
        gov.gambling_pool -= 2 * amount
        result_embed = discord.Embed(
            title="You Win!",
            description=f"The ball landed on **{final_color.upper()} {final_number}**.\nYou won **${amount}**!",
            color=discord.Color.green()
        )
    else:
        result_embed = discord.Embed(
            title="You Lose!",
            description=f"The ball landed on **{final_color.upper()} {final_number}**.\nYou lost **${amount}**.",
            color=discord.Color.red()
        )

    await update_player(player)
    await update_government(gov)
    await wheel_message.edit(content=None, embed=result_embed)
