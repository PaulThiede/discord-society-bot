import discord
from discord.ext import commands
from discord import app_commands
from config import GUILD_ID

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Slash-Command registrieren
    @app_commands.command(name="ping", description="Pings the bot")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong!", ephemeral=True)

    # Optionales Event
    @commands.Cog.listener()
    async def on_member_join(self, member):
        await member.send(f"Welcome to the Society, {member.name}!")

async def setup(bot):
    await bot.add_cog(General(bot), guild=discord.Object(id=GUILD_ID))
