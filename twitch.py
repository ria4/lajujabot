import logging

from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook


logger = logging.getLogger(__name__)


class TwitchWebhookHandler(Twitch):
    def __init__(self, config):
        self.config = config
        self.hook = None
        super().__init__(config["TwitchAppClientID"], config["TwitchAppClientSecret"])
        super().authenticate_app([])
        self.setup_webhook(config["CallbackURL"], config["TwitchAppClientID"])
        logger.info("A Twitch webhook has been set up for app {}, with callback to {}".\
                        format(config["TwitchAppClientID"], config["CallbackURL"]))

    def setup_webhook(self, callback_url, twitch_app_id):
        hook = TwitchWebHook(callback_url, twitch_app_id, self.config["ListeningPort"])
        hook.wait_for_subscription_confirm_timeout = 15
        self.hook = hook
        hook.authenticate(self)
        hook.start()

    def __del__(self):
        if self.hook:
            self.hook.stop()
            logger.info("The Twitch webhook has been stopped")
