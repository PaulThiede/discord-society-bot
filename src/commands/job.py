from discord import Interaction, User, Member, Embed, Color, app_commands

from datetime import datetime

from src.db.db_calls import get_player, add_object, update_player
from src.helper.defaults import get_default_player
from src.config import JOB_SWITCH_COOLDOWN

async def job(interaction: Interaction, job_type: app_commands.Choice[str]):
    print(f"{interaction.user}: /job {job_type.value}")

    user_id = int(interaction.user.id)
    server_id = int(interaction.guild.id)

    player = await get_player(user_id, server_id)
    if not player:
        player = get_default_player(user_id, server_id)
        add_object(player, "Players")

    if await check_if_employed(interaction, player, job_type): return

    if await check_if_on_cooldown(interaction, player): return

    player.job = job_type.value
    player.company_entrepreneur_id = None

    await update_player(player)

    embed = create_job_embed(interaction, job_type)
    await interaction.followup.send(embed=embed)


async def check_if_employed(interaction, player, job_type):
    if player.job == job_type.value:
        embed = Embed(
            title="Job Change Failed",
            description=f"❌ You already have the job **{job_type.value or 'jobless'}**.",
            color=Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return True
    
    if player.job == "Entrepreneur":
        embed = Embed(
            title="Job Change Failed",
            description=f"❌ You are currently an entrepreneur. Please first disband your company with /company disband.",
            color=Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return True
    return False

async def check_if_on_cooldown(interaction, player):
    now = datetime.now()
    if player.job_switch_cooldown_until and player.job_switch_cooldown_until > now:
        cooldown_ts = int(player.job_switch_cooldown_until.timestamp())
        embed = Embed(
            title="Cooldown Active",
            description=f"⏳ You can change your job again <t:{cooldown_ts}:R>.",
            color=Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return True
    player.job_switch_cooldown_until = now + JOB_SWITCH_COOLDOWN
    return False

def create_job_embed(interaction, job_type):
    return Embed(
        title="Job Change",
        description=(
            f"{interaction.user.mention} quit their job and is now jobless."
            if job_type.value == ""
            else f"{interaction.user.mention} changed their job to **{job_type.value}**."
        ),
        color=Color.green()
    )