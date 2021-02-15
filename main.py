from config import loadConfig
from bot import LajujaBotUpdater
from twitch import TwitchWebhookHandler


# Load configuration
config = loadConfig()

# Start Twitch webhook
wh_handler = TwitchWebhookHandler(config)

# Start Telegram bot
mybot = LajujaBotUpdater(config, wh_handler)
mybot.start_polling()
