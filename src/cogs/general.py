import discord
from discord.ext import commands
from discord import app_commands

class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Pings the bot")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong!", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await member.send(f"Welcome To The Society, {member.name}!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if "shit" in message.content.lower():
            await message.channel.send(f"{message.author.mention} nanana. that was a bad word")
        await self.bot.process_commands(message)

async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
