import logging

from twitchAPI import (Twitch, EventSub,
                       TwitchAPIException, UnauthorizedException,
                       MissingScopeException, ValueError, TwitchAuthorizationException,
                       TwitchBackendException, EventSubSubscriptionConflict,
                       EventSubSubscriptionTimeout, EventSubSubscriptionError)


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
        hook = EventSub(callback_url, twitch_app_id, self.config["ListeningPort"], self)
        hook.wait_for_subscription_confirm_timeout = 15
        hook.unsubscribe_all()
        self.hook = hook
        hook.start()

    def get_broadcaster_id_clean(broadcaster_name):
        try:
            res = self.get_users(logins=[broadcaster_name])
        except (TwitchAPIException, UnauthorizedException,
                MissingScopeException, ValueError,
                TwitchAuthorizationException, TwitchBackendException) as e:
            error_msg = "Failed to get information about broadcaster {} with error {}"
            error_msg.format(broadcaster_name, e)
            logger.error(error_msg)
            return None
        return res["data"][0]["id"]

    def get_channel_information_clean(broadcaster_id):
        try:
            res = self.get_channel_information(broadcaster_id)
        except (TwitchAPIException, UnauthorizedException,
                TwitchAuthorizationException, TwitchBackendException) as e:
            error_msg = "Failed to get information about channel {} with error {}"
            error_msg.format(broadcaster_id, e)
            logger.error(error_msg)
            return None, None
        return res["data"]["game_name"], res["data"]["title"]

    def listen_stream_online_clean(broadcaster_id, broadcaster_name, callback):
        try:
            uuid = self.hook.listen_stream_online(broadcaster_id, callback)
        except (EventSubSubscriptionConflict, EventSubSubscriptionTimeout, EventSubSubscriptionError) as e:
            error_msg = "Subscription to broadcaster {} (id {}) failed with error {}"
            error_msg.format(broadcaster_name, broadcaster_id, e)
            logger.error(error_msg)
            return None
        return uuid

    def __del__(self):
        if self.hook:
            self.hook.stop()
            logger.info("The Twitch webhook has been stopped")
