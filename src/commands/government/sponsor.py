import discord

from src.db.db_calls import get_government, add_object, update_government, update_company, get_company
from src.helper.defaults import get_default_government

async def sponsor(interaction: discord.Interaction, amount: int):
    print(f"{interaction.user}: /sponsor {amount}")
    server_id = interaction.guild.id
    user_roles = [r.id for r in interaction.user.roles]

    gov = await get_government(server_id)
    if not gov:
        gov = get_default_government(server_id)
        await add_object(gov, "Government")

    if gov.governing_role not in user_roles:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Permission Denied",
                description="You are not a government official and thus can't sponsor gambling.",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return

    if amount <= 0:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error!",
                description="The amount must be greater than 0.",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return

    if amount > gov.treasury:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error!",
                description=f"The treasury only has ${gov.treasury}, so you can't spend ${amount}.",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return
    

    gov.treasury -= amount
    gov.gambling_pool += amount
    await update_government(gov)

    await interaction.followup.send(embed=discord.Embed(
        title="Gambling sponsored",
        description=f"You successfully sponsored the gambling pool with **${amount}**.",
        color=discord.Color.green()
    ))