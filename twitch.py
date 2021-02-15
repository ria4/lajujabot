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

#    def hook_unsubscribe_hex(self, uuid_hex):
#        # we need this hacky hex interface because we cannot serialize uuids
#        for uuid in self.hook._TwitchWebHook__active_webhooks:
#            if uuid.hex == uuid_hex:
#                self.hook.unsubscribe(uuid)
#                break
#
    def __del__(self):
        self.hook.stop()
