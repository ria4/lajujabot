import logging

from twitchAPI import (Twitch, EventSub,
                       TwitchAPIException, UnauthorizedException,
                       MissingScopeException, TwitchAuthorizationException,
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

    def get_broadcaster_id_clean(self, broadcaster_name):
        try:
            res = self.get_users(logins=[broadcaster_name])
        except (TwitchAPIException, UnauthorizedException,
                MissingScopeException, ValueError,
                TwitchAuthorizationException, TwitchBackendException) as e:
            error_msg = "Failed to get information about broadcaster {} with error {}: '{}'"
            error_msg = error_msg.format(broadcaster_name, type(e).__name__, e)
            logger.error(error_msg)
            return None
        if not res["data"]:
            # no broadcaster of this name could be found
            return None
        broadcaster_id = res["data"][0]["id"]
        info_msg = "Retrieved id {} from broadcaster name {}"
        info_msg = info_msg.format(broadcaster_id, broadcaster_name)
        logger.info(info_msg)
        return broadcaster_id

    def get_channel_information_clean(self, broadcaster_id):
        try:
            res = self.get_channel_information(broadcaster_id)
        except (TwitchAPIException, UnauthorizedException,
                TwitchAuthorizationException, TwitchBackendException) as e:
            error_msg = "Failed to get information about channel {} with error {}: '{}'"
            error_msg = error_msg.format(broadcaster_id, type(e).__name__, e)
            logger.error(error_msg)
            return None, None
        game = res["data"][0]["game_name"]
        title = res["data"][0]["title"]
        info_msg = "Retrieved stream information about broadcaster {} (game: {}, title: '{}')"
        info_msg = info_msg.format(broadcaster_id, game, title)
        logger.info(info_msg)
        return game, title

    def get_followed_channels(self, user_id):
        try:
            res = self.get_users_follows(from_id=user_id, first=100)
        except (TwitchAPIException, UnauthorizedException, ValueError,
                TwitchAuthorizationException, TwitchBackendException) as e:
            error_msg = "Failed to get channels followed by twitch user {} with error {}: '{}'"
            error_msg = error_msg.format(user_id, type(e).__name__, e)
            logger.error(error_msg)
            return None
        followed_channels = res["data"]
        info_msg = "Retrieved channels followed by twitch user {}"
        info_msg = info_msg.format(user_id)
        logger.info(info_msg)
        return followed_channels

    def listen_stream_online_clean(self, broadcaster_id, broadcaster_name, callback):
        try:
            uuid = self.hook.listen_stream_online(broadcaster_id, callback)
        except (EventSubSubscriptionConflict, EventSubSubscriptionTimeout, EventSubSubscriptionError) as e:
            error_msg = "Subscription to broadcaster {} (id {}) failed with error {}: '{}'"
            error_msg = error_msg.format(broadcaster_name, broadcaster_id, type(e).__name__, e)
            logger.error(error_msg)
            return None
        info_msg = "Subscribed to stream.online events for broadcaster {} (id {})"
        info_msg = info_msg.format(broadcaster_name, broadcaster_id)
        logger.info(info_msg)
        return uuid

    def __del__(self):
        if self.hook:
            self.hook.stop()
            logger.info("The Twitch webhook has been stopped")
