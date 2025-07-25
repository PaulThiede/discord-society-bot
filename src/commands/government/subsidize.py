import discord

from src.db.db_calls import get_government, add_object, update_government, update_company, get_company
from src.helper.defaults import get_default_government

async def subsidize(interaction: discord.Interaction, user: discord.User | discord.Member, amount: int):
    print(f"{interaction.user}: /subsidize {user} {amount}")
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
                description="You are not a government official and thus can't subsidize companies.",
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
    
    company = await get_company(user.id, server_id)

    if not company:
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error!",
                description=f"This user does not have a company!",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return

    gov.treasury -= amount
    company.capital += amount
    await update_government(gov)
    await update_company(company)

    await interaction.followup.send(embed=discord.Embed(
        title="Company Subsidized",
        description=f"You successfully subsidized **{company.name}** with **${amount}**.",
        color=discord.Color.green()
    ))