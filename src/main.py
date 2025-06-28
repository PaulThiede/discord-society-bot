import discord
from discord.ext import commands
from discord import app_commands

import logging
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
GUILD_ID = 1388465512450752644  # use plain int

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class Client(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # register commands for testing
        guild = discord.Object(id=GUILD_ID)
        await self.tree.sync(guild=guild)
        print("Slash commands synced.")

    async def on_ready(self):
        print(f'We have logged in as {self.user.name}')

    async def on_member_join(self, member):
        await member.send(f"Welcome To The Society, {member.name}!")

    async def on_message(self, message):
        if message.author == self.user:
            return
        if "shit" in message.content.lower():
            await message.channel.send(f"{message.author.mention} nanana. that was a bad word")
        await self.process_commands(message)


client = Client()


# SLASH command using app_commands
@client.tree.command(name="ping", description="Pings the bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!", ephemeral=True)


client.run(TOKEN, log_handler=handler, log_level=logging.DEBUG)