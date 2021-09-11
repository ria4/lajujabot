import logging
import pickle
from datetime import datetime, timezone
from inspect import cleandoc
from telegram.ext import (Updater, Dispatcher, PicklePersistence,
                          CommandHandler, MessageHandler, Filters)


logger = logging.getLogger(__name__)


class LajujaBotUpdater(Updater):
    """
    This bot has persistent chat_data to enable seamless restoration.
    chat_data is a dict of the following structure:
        { <chat_id_1> : <context_chat_data_1>,
          <chat_id_2> : <context_chat_data_2>, ...}
    where context_chat_datas are of the following structure:
        { <broadcaster_id_1> : <broadcaster_name_1>,
          <broadcaster_id_2> : <broadcaster_name_2>, ...}

    bot_data is a non-persistent dict of the following structure:
        { <broadcaster_id_1> : {"subscription_uuid": <subscription_uuid>,
                                "subscribers": [<chat_id_1>, <chat_id_2>, ...] },
          <broadcaster_id_2> : {...}, etc. }
    """

    def __init__(self, config, wh_handler):
        self.config = config
        self.wh_handler = wh_handler
        persistence = PicklePersistence(filename=config["PersistenceFile"],
                                        store_user_data=False,
                                        store_bot_data=False)
        super().__init__(token=config["TelegramBotToken"], persistence=persistence)
        self.register_handlers()
        self.restore_bot_data()

    def register_handlers(self):
        if self.config["OopsItsBroken"] == "True":
            self.dispatcher.add_handler(CommandHandler('start', self.start))
            self.dispatcher.add_handler(CommandHandler('help', self.help))
            self.dispatcher.add_handler(CommandHandler('about', self.about))
            self.dispatcher.add_handler(MessageHandler(Filters.command, self.broken))
        else:
            self.dispatcher.add_handler(CommandHandler('start', self.start))
            self.dispatcher.add_handler(CommandHandler('sub', self.sub))
            self.dispatcher.add_handler(CommandHandler('unsub', self.unsub))
            self.dispatcher.add_handler(CommandHandler('unsub_all', self.unsub_all))
            self.dispatcher.add_handler(CommandHandler('import', self.subs_import))
            self.dispatcher.add_handler(CommandHandler('list', self.list))
            self.dispatcher.add_handler(CommandHandler('help', self.help))
            self.dispatcher.add_handler(CommandHandler('about', self.about))
            self.dispatcher.add_handler(MessageHandler(Filters.command, self.unknown))

    def _get_broadcaster_id(broadcaster_name):
        return self.wh_handler.get_broadcaster_id_clean(broadcaster_name)

    def _get_stream_info(broadcaster_id):
        return self.wh_handler.get_channel_information_clean(broadcaster_id)

    def _subscribe_stream_online(broadcaster_id, broadcaster_name):
        return self.wh_handler.listen_stream_online_clean(broadcaster_id, broadcaster_name,
                                                          self.callback_stream_changed)

    def _unsubscribe(uuid):
        self.wh_handler.hook.unsubscribe_topic(uuid)

    def restore_bot_data(self):
        chat_data = self.persistence.get_chat_data()
        bot_data = {}
        for chat_id, broadcasters in chat_data.items():
            for broadcaster_id, broadcaster_name in broadcasters.items():
                if broadcaster_id in bot_data:
                    bot_data[broadcaster_id]["subscribers"].append(chat_id)
                else:
                    uuid = self._subscribe_stream_online(broadcaster_id, broadcaster_name)
                    if uuid:
                        bot_data[broadcaster_id] = {"subscription_uuid": uuid, "subscribers": [chat_id]}
        self.dispatcher.bot_data = bot_data


    def callback_stream_changed(self, uuid, data):

        data = data["event"]

        started_at = data["started_at"]
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(started_at[:-1]+"+00:00")
        #print("Notification delay: {} seconds".format(delta.seconds))
        if (delta.days > 0) or (delta.seconds > 300):
            # the stream changed but was already up for some time
            # we do not want to send another notification
            return

        broadcaster_id = data["broadcaster_user_id"]
        game, title = self._get_stream_info(broadcaster_id)

        for subscriptions in self.dispatcher.bot_data.values():
            if subscriptions["subscription_uuid"] == uuid:
                for chat_id in subscriptions["subscribers"]:
                    # we retrieve our user-defined broadcaster_name,
                    # because the one returned in data["user_name"] is de-capitalized,
                    # which is ugly, and also it might not work with our /unsub
                    broadcaster_name = self.dispatcher.chat_data[chat_id][broadcaster_id]
                    if title:
                        if game:
                            text = '{0} is streaming {1}!\n « {2} »\n https://twitch.tv/{0}\n'.format(broadcaster_name, game, title)
                        else:
                            text = '{0} is live on Twitch!\n « {1} »\n https://twitch.tv/{0}\n'.format(broadcaster_name, title)
                    else:
                        text = '{0} is live on Twitch!\n https://twitch.tv/{0}'.format(broadcaster_name)
                    self.bot.send_message(chat_id=chat_id, text=text)
                break

    
    def start(self, update, context):
        text = """💜 Greetings! 💜
                  This bot can send you notifications on Telegram when the Twitch streamers of your choice go live. You may ask for notifications about certain channels in one group chat, while maintaining a different pool of notifications in your private chat with the bot. You just have to register your subscriptions chat by chat.
                  Ask /help to get the commands."""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def help(self, update, context):
        text = """/sub channel – receive notifications when the channel goes live.
                  /unsub channel – remove the subscription to the channel.
                  /unsub_all – remove all subscriptions for the current chat.
                  /import account – monitor all channels followed by the account.
                  /list – display all subscriptions for the current chat.
                  /about – learn more about this bot.
                  /help – get some help."""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def about(self, update, context):
        text = """This bot was developed by @oriane_tury. ✨
                  It was reworked from a bot by @avivace and @dennib, and it relies on a Twitch API implementation by Lena 'Teekeks' During.
                  Get the source code at https://github.com/ria4/lajujabot"""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def unknown(self, update, context):
        text = """There is no such command. Do you need some /help?"""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def broken(self, update, context):
        text = """Lajujabot is asleep right now. 😴
                  There's been major changes to the Twitch API, which are not supported by our backend yet. Hopefully this'll be sorted out by the end of the summer. Please come back later. 🙏"""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def sub(self, update, context, broadcaster_id=None, broadcaster_name=None):
        # if one of broadcaster_id or broadcaster_name is present,
        # both or them are supposed to be present and correspond to a valid broadcaster

        chat_id = update.message.chat_id

        # if you ever want to remove the 100-subs limit, just delete this part
        if len(context.chat_data) >= 100:
            text = "There's already 100 subscriptions on this chat and I believe that's quite enough. If you want more, tweak the code and deploy it yourself. Or send a few $$$ to @oriane_tury so that she can help you."
            context.bot.send_message(chat_id=chat_id, text=text)
            return

        if broadcaster_id or broadcaster_name:
            if broadcaster_id not in context.bot_data:
                uuid = self._subscribe_stream_online(broadcaster_id, broadcaster_name)
                if not uuid:
                    text = "Something went wrong with the subscription to {}'s channel. If you send a message to @oriane_tury, she'll try to sort things out. Sorry!".format(broadcaster_name)
                    context.bot.send_message(chat_id=chat_id, text=text)
                    return
                context.bot_data[broadcaster_id] = {"subscription_uuid": uuid, "subscribers": []}

            context.chat_data[broadcaster_id] = broadcaster_name
            context.bot_data[broadcaster_id]["subscribers"].append(chat_id)
            text = "You were successfully subscribed to {}'s channel!".format(broadcaster_name)
            context.bot.send_message(chat_id=chat_id, text=text)
            return

        if not context.args:
            text = "You must submit a Twitch channel name for this to work."

        else:
            text = ""
            if len(context.args) > 1:
                text += "Please send one channel name at a time.\n"

            broadcaster_name = context.args[0]
            if broadcaster_name in context.chat_data.values():
                text += "You're already subscribed to {}'s channel, so we're good here.".format(broadcaster_name)

            else:
                broadcaster_id = self._get_broadcaster_id(broadcaster_name)
                if not broadcaster_data["data"]:
                    text += "This account cannot be found. Please check your input."

                else:
                    broadcaster_id = broadcaster_data["data"][0]["id"]
                    if broadcaster_id not in context.bot_data:
                        uuid = self._subscribe_stream_online(broadcaster_id, broadcaster_name)
                        if not uuid:
                            text += "Something went wrong with the subscription to {}'s channel. If you send a message to @oriane_tury, she'll try to sort things out. Sorry!".format(broadcaster_name)
                            context.bot.send_message(chat_id=chat_id, text=text)
                            return
                        context.bot_data[broadcaster_id] = {"subscription_uuid": uuid, "subscribers": []}
                    context.chat_data[broadcaster_id] = broadcaster_name
                    context.bot_data[broadcaster_id]["subscribers"].append(chat_id)
                    text += "You were successfully subscribed to {}'s channel!".format(broadcaster_name)

        context.bot.send_message(chat_id=chat_id, text=text)


    def unsub(self, update, context, broadcaster_id=None):
        # if broadcaster_id is present, it is supposed to be a valid broadcaster subscribed by the user

        if broadcaster_id:
            broadcaster_name = context.chat_data[broadcaster_id]
            context.chat_data.pop(broadcaster_id)
            context.bot_data[broadcaster_id]["subscribers"].remove(update.message.chat_id)
            if len(context.bot_data[broadcaster_id]["subscribers"]) == 0:
                self._unsubscribe(context.bot_data[broadcaster_id]["subscription_uuid"])
                context.bot_data.pop(broadcaster_id)
            text = "You won't receive notifications about {} anymore.".format(broadcaster_name)
            context.bot.send_message(chat_id=update.message.chat_id, text=text)
            return

        if not context.args:
            text = "You must submit a Twitch channel name for this to work."

        else:
            text = ""
            if len(context.args) > 1:
                text += "Please send one channel name at a time.\n"

            broadcaster_name = context.args[0]
            if not broadcaster_name in context.chat_data.values():
                text += "You weren't subscribed to the channel '{}', so we're good here.".format(broadcaster_name)

            else:
                broadcaster_id = list(context.chat_data.keys())[list(context.chat_data.values()).index(broadcaster_name)]
                context.chat_data.pop(broadcaster_id)
                context.bot_data[broadcaster_id]["subscribers"].remove(update.message.chat_id)
                if len(context.bot_data[broadcaster_id]["subscribers"]) == 0:
                    self._unsubscribe(context.bot_data[broadcaster_id]["subscription_uuid"])
                    context.bot_data.pop(broadcaster_id)
                text += "You won't receive notifications about {} anymore.".format(context.args[0])

        context.bot.send_message(chat_id=update.message.chat_id, text=text)


    def unsub_all(self, update, context):

        if not context.chat_data:
            text = "You're not subscribed to any channel, so we're good here."
            context.bot.send_message(chat_id=update.message.chat_id, text=text)
            return

        for broadcaster_id in list(context.chat_data.keys()):
            self.unsub(update, context, broadcaster_id)


    def subs_import(self, update, context):

        text = ""
        if not context.args:
            text = "You must submit a Twitch account name for this to work."

        else:
            user_data = self.wh_handler.get_users(logins=[context.args[0]])

            if user_data["data"]:
                user_id = user_data["data"][0]["id"]
                followed_data = self.wh_handler.get_users_follows(from_id=user_id, first=100)
                if not followed_data["data"]:
                    text = "This account follows no other account. Stop messing around."
                else:
                    for followed_broadcaster in followed_data["data"]:
                        self.sub(update, context,
                                 broadcaster_id=followed_broadcaster["to_id"],
                                 broadcaster_name=followed_broadcaster["to_name"])
                    if followed_data["total"] == 100:
                        text = "You cannot import more than 100 accounts. Be reasonable."

            else:
                text = "This account cannot be found. Please check your input."

        if text:
            context.bot.send_message(chat_id=update.message.chat_id, text=text)


    def list(self, update, context):

        if not context.chat_data:
            text = "It seems you have no subscriptions yet."

        else:
            text = "Here's a list of your subscriptions:"
            for broadcaster_name in context.chat_data.values():
                text += "\n" + broadcaster_name

        context.bot.send_message(chat_id=update.message.chat_id, text=text)
