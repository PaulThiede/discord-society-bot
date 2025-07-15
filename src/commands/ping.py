from discord import Interaction, Embed, Color

async def ping(interaction: Interaction, client):
    print(f"{interaction.user}: /ping")
    ping_embed = Embed(
        title="Ping",
        description="Latency in ms",
        color=Color.yellow()
    )
    ping_embed.add_field(
        name=f"{client.user.name}'s Latency (ms): ",
        value=f"{round(client.latency * 1000)}ms",
        inline=False
    )
    ping_embed.set_footer(
        text=f"Requested by {interaction.user}",
        icon_url=interaction.user.display_avatar.url
    )
    await interaction.response.send_message(embed=ping_embed)