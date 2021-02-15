from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook


class TwitchWebhookHandler(Twitch):
    def __init__(self, config):
        self.config = config
        self.hook = None
        super().__init__(config["TwitchAppClientID"], config["TwitchAppClientSecret"])
        super().authenticate_app([])
        self.setup_webhook(config["CallbackURL"], config["TwitchAppClientID"])

    def setup_webhook(self, callback_url, twitch_app_id):
        hook = TwitchWebHook(callback_url, twitch_app_id, 15151)
        self.hook = hook
        hook.authenticate(self)
        hook.start()

    def add_subscription(self, channel_id, callback_stream_changed):
        # userID should be a valid digit, not username
        success, uuid = self.hook.subscribe_stream_changed(channel_id, callback_stream_changed)
        if not success:
            return None
        return uuid

    def __del__(self):
        self.hook.stop()
