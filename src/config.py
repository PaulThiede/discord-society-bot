import os

from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
PORT = int(os.getenv("PORT"))

JOB_SWITCH_COOLDOWN = timedelta(minutes=30)
WORK_COOLDOWN = timedelta(minutes=5)
GIFT_COOLDOWN = timedelta(hours=1)
BUY_ORDER_DURATION = timedelta(days=3)
SELL_ORDER_DURATION = timedelta(days=3)