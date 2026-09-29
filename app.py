# Entry point for HeavenCloud hosting
from main import bot, DISCORD_BOT_TOKEN

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("⚠️ ERROR: DISCORD_BOT_TOKEN is not set in .env")
    else:
        bot.run(DISCORD_BOT_TOKEN)
