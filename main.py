import logging

from config import loadConfig
from twitch import TwitchWebhookHandler
from bot import LajujaBotUpdater


# Load configuration
config = loadConfig()

# Start logging
logging.basicConfig(filename=config["LogFile"],
                    format="[%(levelname)s] %(asctime)s - %(message)s",
                    datefmt="%d/%m/%Y %H:%M:%S",
                    level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("######## New session #######################################################################")

try:
    # Start Twitch webhook
    wh_handler = TwitchWebhookHandler(config)

    # Start Telegram bot
    mybot = LajujaBotUpdater(config, wh_handler)
    mybot.start_polling(drop_pending_updates=True)
    logger.info("######## Started polling Telegram updates ##################################################")

except:
    logger.exception("######## main.py crashed ###################################################################")
