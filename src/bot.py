import discord
from discord.ext import commands
from src.config import TOKEN, GUILD_ID

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class Client(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.initial_extensions = [
            "cogs.general",
        ]

    async def setup_hook(self):
        for ext in self.initial_extensions:
            await self.load_extension(ext)

        guild = discord.Object(id=GUILD_ID)
        await self.tree.sync(guild=guild)
        print("Slash commands synced.")

    async def on_ready(self):
        print(f'We have logged in as {self.user.name}')

client = Client()
client.run(TOKEN)
