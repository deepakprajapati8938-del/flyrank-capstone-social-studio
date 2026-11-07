import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Application Configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "social_studio.db"))
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Real Target Configuration (Discord Webhook or Telegram Bot)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Default Publisher Adapter (discord | mock_x | mock_linkedin | telegram)
DEFAULT_PUBLISHER_ADAPTER = os.getenv("DEFAULT_PUBLISHER_ADAPTER", "discord")
