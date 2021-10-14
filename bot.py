import asyncio
import logging
import pickle

from datetime import datetime, timezone
from inspect import cleandoc
from queue import Queue

from telegram.error import Unauthorized
from telegram.ext import (Updater, Dispatcher,
                          ExtBot, JobQueue, PicklePersistence,
                          CommandHandler, MessageHandler, Filters)
from telegram.utils.request import Request


logger = logging.getLogger(__name__)


class LajujaBotDispatcher(Dispatcher):
    """
    We need to create a new event loop
    because the Dispatcher runs outside the main thread.
    """

    def start(self, ready=None):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        super().start(ready)


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
        { <broadcaster_id_1> : {"subscription_id": <subscription_id_1>,
                                "subscribers": [<chat_id_1>, <chat_id_2>, ...] },
          <broadcaster_id_2> : {...}, etc. }
    """

    def __init__(self, config, wh_handler):
        self.config = config
        self._wh_handler = wh_handler

        con_pool_size = 4 + 4
        request_kwargs = {"con_pool_size": con_pool_size}
        bot = ExtBot(config["TelegramBotToken"], request=Request(**request_kwargs))
        persistence = PicklePersistence(filename=config["PersistenceFile"],
                                        store_user_data=False,
                                        store_bot_data=False)
        dispatcher = LajujaBotDispatcher(bot,
                                         Queue(),
                                         job_queue=JobQueue(),
                                         persistence=persistence)
        super().__init__(dispatcher=dispatcher, workers=None)

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

    def _get_broadcaster_id(self, broadcaster_name):
        return self._wh_handler.get_broadcaster_id_clean(broadcaster_name)

    def _get_stream_info(self, broadcaster_id):
        return self._wh_handler.get_channel_information_clean(broadcaster_id)

    def _get_followed_channels(self, user_id):
        return self._wh_handler.get_followed_channels(user_id)

    def _subscribe_stream_online(self, broadcaster_id, broadcaster_name):
        return self._wh_handler.listen_stream_online_clean(broadcaster_id, broadcaster_name,
                                                           self.callback_stream_changed)

    def _unsubscribe(self, sub_id):
        self._wh_handler.hook.unsubscribe_topic(sub_id)

    def restore_bot_data(self):
        chat_data = self.persistence.get_chat_data()

        #empty_keys = [k for k,v in chat_data.items() if not v]
        #for k in empty_keys:
        #    self.delete_chat_data(k)

        bot_data = {}
        for chat_id, broadcasters in chat_data.items():
            for broadcaster_id, broadcaster_name in broadcasters.items():
                if broadcaster_id in bot_data:
                    bot_data[broadcaster_id]["subscribers"].append(chat_id)
                else:
                    sub_id = self._subscribe_stream_online(broadcaster_id, broadcaster_name)
                    if sub_id:
                        bot_data[broadcaster_id] = {"subscription_uuid": sub_id, "subscribers": [chat_id]}
        self.dispatcher.bot_data = bot_data

    def delete_chat_data(self, chat_id):
        # remove chat key from chat_data
        #self.dispatcher.remove_from_persistent_chat_data(chat_id)
        #info_msg = "Removed for chat {} from persistent data."
        #info_msg = info_msg.format(chat_id)
        #logger.info(info_msg)

        # since there's no method for this yet, at least empty the related entry
        chat_data = self.dispatcher.chat_data
        bot_data = self.dispatcher.bot_data
        broadcaster_ids = chat_data[chat_id].keys()
        for broadcaster_id in broadcaster_ids:
            chat_data[chat_id].pop(broadcaster_id)
            subscription = bot_data[broadcaster_id]
            subscription["subscribers"].remove(chat_id)
            if len(subscription["subscribers"]) == 0:
                self._unsubscribe(subscription["subscription_uuid"])
                bot_data.pop(broadcaster_id)
        self.dispatcher.update_persistence()
        info_msg = "Removed all subscription data for chat {} from persistent data."
        info_msg = info_msg.format(chat_id)
        logger.info(info_msg)
        return


    async def callback_stream_changed(self, data):

        sub_id = data["subscription"]["id"]
        event = data["event"]

        started_at = event["started_at"]
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(started_at[:-1]+"+00:00")
        if (delta.days > 0) or (delta.seconds > 300):
            # the stream changed but was already up for some time
            # we do not want to send another notification
            return

        broadcaster_id = event["broadcaster_user_id"]
        broadcaster_name_official = event["broadcaster_user_name"]
        info_msg = "Broadcaster {} started streaming (notification received from twitch with a {}s delay)"
        info_msg = info_msg.format(broadcaster_name_official, delta.seconds)
        logger.info(info_msg)

        game, title = self._get_stream_info(broadcaster_id)

        for subscriptions in self.dispatcher.bot_data.values():
            if subscriptions["subscription_uuid"] == sub_id:
                for chat_id in subscriptions["subscribers"]:
                    # we retrieve our user-defined broadcaster_name,
                    # because the one returned in the "broadcaster_user_name" field
                    # might not work with the internal name needed for /unsub
                    broadcaster_name = self.dispatcher.chat_data[chat_id][broadcaster_id]
                    if title:
                        if game:
                            text = '{0} is streaming {1}!\n « {2} »\n https://twitch.tv/{0}'
                            text = text.format(broadcaster_name, game, title)
                        else:
                            text = '{0} is live on Twitch!\n « {1} »\n https://twitch.tv/{0}'
                            text = text.format(broadcaster_name, title)
                    else:
                        text = '{0} is live on Twitch!\n https://twitch.tv/{0}'
                        text = text.format(broadcaster_name)
                    try:
                        self.bot.send_message(chat_id=chat_id, text=text)
                        info_msg = "Sent message to chat {}:\n{}"
                        info_msg = info_msg.format(chat_id, text)
                        logger.info(info_msg)
                    except Unauthorized as e:
                        info_msg = "Sending a message to chat {} raised a telegram.error.Unauthorized: {}"
                        info_msg = info_msg.format(chat_id, e)
                        logger.info(info_msg)
                        self.delete_chat_data(chat_id)
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
                  There's been major changes to the Twitch API, which are not fully supported by our backend yet. We're working on it, please come back later! 🙏"""
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
                sub_id = self._subscribe_stream_online(broadcaster_id, broadcaster_name)
                if not sub_id:
                    text = "Something went wrong with the subscription to {}'s channel. If you send a message to @oriane_tury, she'll try to sort things out. Sorry!".format(broadcaster_name)
                    context.bot.send_message(chat_id=chat_id, text=text)
                    return
                context.bot_data[broadcaster_id] = {"subscription_uuid": sub_id, "subscribers": []}

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
                if not broadcaster_id:
                    text += "This account cannot be found. Please check your input."

                else:
                    if broadcaster_id not in context.bot_data:
                        sub_id = self._subscribe_stream_online(broadcaster_id, broadcaster_name)
                        if not sub_id:
                            text += "Something went wrong with the subscription to {}'s channel. If you send a message to @oriane_tury, she'll try to sort things out. Sorry!".format(broadcaster_name)
                            context.bot.send_message(chat_id=chat_id, text=text)
                            return
                        context.bot_data[broadcaster_id] = {"subscription_uuid": sub_id, "subscribers": []}
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
            user_name = context.args[0]
            user_id = self._get_broadcaster_id(user_name)

            if user_id:
                followed_channels = self._get_followed_channels(user_id)

                if not followed_channels:
                    text = "It seems this account does not follow any other account."
                else:
                    for followed_broadcaster in followed_channels:
                        self.sub(update, context,
                                 broadcaster_id=followed_broadcaster["to_id"],
                                 broadcaster_name=followed_broadcaster["to_name"])
                    if len(followed_channels) == 100:
                        text = "You cannot import more than 100 accounts."

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
