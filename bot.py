import asyncio
import logging
import pickle

from datetime import datetime, timezone
from inspect import cleandoc
from queue import Queue

from telegram.error import BadRequest, ChatMigrated, Unauthorized
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
        if "MaintenanceMode" in self.config and self.config["MaintenanceMode"] == "True":
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
                    sub_id = self._tw_subscribe_stream_online(broadcaster_id, broadcaster_name)
                    if sub_id:
                        bot_data[broadcaster_id] = {"subscription_uuid": sub_id, "subscribers": [chat_id]}
        self.dispatcher.bot_data = bot_data

    def remove_from_bot_data(self, bot_data, chat_id, broadcaster_id):
        subscription = bot_data[broadcaster_id]
        subscription["subscribers"].remove(chat_id)
        if len(subscription["subscribers"]) == 0:
            self._tw_unsubscribe(subscription["subscription_uuid"])
            bot_data.pop(broadcaster_id)

    def delete_chat_data(self, chat_id):
        # remove chat key from chat_data
        #self.dispatcher.remove_from_persistent_chat_data(chat_id)
        #logger.info(f"Removed for chat {chat_id} from persistent data.")

        # since there's no method for this yet, at least empty the related entry
        chat_data = self.dispatcher.chat_data
        bot_data = self.dispatcher.bot_data
        broadcaster_ids = list(chat_data[chat_id].keys())
        for broadcaster_id in broadcaster_ids:
            chat_data[chat_id].pop(broadcaster_id)
            self.remove_from_bot_data(bot_data, chat_id, broadcaster_id)
        self.dispatcher.update_persistence()
        info_msg = f"Removed all subscription data for chat {chat_id} from persistent data."
        logger.info(info_msg)
        return


    def _tw_get_broadcaster_id(self, broadcaster_name):
        return self._wh_handler.get_broadcaster_id_clean(broadcaster_name)

    def _tw_get_stream_info(self, broadcaster_id):
        return self._wh_handler.get_channel_information_clean(broadcaster_id)

    def _tw_get_followed_channels(self, user_id):
        return self._wh_handler.get_followed_channels(user_id)

    def _tw_subscribe_stream_online(self, broadcaster_id, broadcaster_name):
        return self._wh_handler.listen_stream_online_clean(
            broadcaster_id,
            broadcaster_name,
            self.callback_stream_changed
        )

    def _tw_unsubscribe(self, sub_id):
        self._wh_handler.hook.unsubscribe_topic(sub_id)


    def _sub_by_id(self, update, context, broadcaster_id, broadcaster_name):
        # broadcaster_id & broadcaster_name must refer to a valid broadcaster

        if broadcaster_id not in context.bot_data:
            sub_id = self._tw_subscribe_stream_online(broadcaster_id, broadcaster_name)
            if not sub_id:
                text = f"Something went wrong with the subscription to {broadcaster_name}'s channel. If you send a message to @oriane_tury, she'll try to sort things out. Sorry!"
                context.bot.send_message(chat_id=chat_id, text=text)
                return
            context.bot_data[broadcaster_id] = {"subscription_uuid": sub_id, "subscribers": []}

        context.chat_data[broadcaster_id] = broadcaster_name
        chat_id = update.message.chat_id
        context.bot_data[broadcaster_id]["subscribers"].append(chat_id)
        text = f"You were successfully subscribed to {broadcaster_name}'s channel!"
        context.bot.send_message(chat_id=chat_id, text=text)


    def _unsub_by_id(self, update, context, broadcaster_id):
        # broadcaster_id must by a valid broadcaster the chat user subscribed to

        broadcaster_name = context.chat_data[broadcaster_id]
        context.chat_data.pop(broadcaster_id)
        chat_id = update.message.chat_id
        self.remove_from_bot_data(context.bot_data, chat_id, broadcaster_id)
        text = f"You won't receive notifications about {broadcaster_name} anymore."
        context.bot.send_message(chat_id=chat_id, text=text)


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
        logger.info(
            f"Broadcaster {broadcaster_name_official} started streaming "
            f"(notification received from twitch with a {delta.seconds}s delay)"
        )

        game, title = self._tw_get_stream_info(broadcaster_id)

        for subscriptions in self.dispatcher.bot_data.values():
            if subscriptions["subscription_uuid"] == sub_id:
                for chat_id in subscriptions["subscribers"]:
                    # we retrieve our user-defined broadcaster_name,
                    # because the one returned in the "broadcaster_user_name" field
                    # might not work with the internal name needed for /unsub
                    broadcaster_name = self.dispatcher.chat_data[chat_id][broadcaster_id]
                    if title:
                        if game:
                            text = f"{broadcaster_name} is streaming {game}!\n « {title} »\n https://twitch.tv/{broadcaster_name}"
                        else:
                            text = f"{broadcaster_name} is live on Twitch!\n « {title} »\n https://twitch.tv/{broadcaster_name}"
                    else:
                        text = f"{broadcaster_name} is live on Twitch!\n https://twitch.tv/{broadcaster_name}"
                    try:
                        self.bot.send_message(chat_id=chat_id, text=text)
                        logger.info(f"Sent message to chat {chat_id}:\n{text}")
                    except (BadRequest, ChatMigrated, Unauthorized) as e:
                        logger.info(f"Sending a message to chat {chat_id} raised error {type(e).__name__}: {e}")
                        logger.info(f"Removing chat {chat_id} from bot users...")
                        self.delete_chat_data(chat_id)
                break


    def start(self, update, context):
        """Telegram bot command /start to get a greeting message."""

        text = """💜 Greetings! 💜
                  This bot can send you notifications on Telegram when the Twitch streamers of your choice go live. You may ask for notifications about certain channels in one group chat, while maintaining a different pool of notifications in your private chat with the bot. You just have to register your subscriptions chat by chat.
                  Ask /help to get the commands."""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def help(self, update, context):
        """Telegram bot command /help to list available commands."""

        text = """/sub channel – receive notifications when the channel goes live.
                  /unsub channel – remove the subscription to the channel.
                  /unsub_all – remove all subscriptions for the current chat.
                  /import account – monitor all channels followed by the account.
                  /list – display all subscriptions for the current chat.
                  /about – learn more about this bot.
                  /help – get some help."""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def about(self, update, context):
        """Telegram bot command /about to display info about the bot."""

        text = """This bot was developed by @oriane_tury. ✨
                  It was reworked from a bot by @avivace and @dennib, and it relies on a Twitch API implementation by Lena 'Teekeks' During.
                  Get the source code at https://github.com/ria4/lajujabot"""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def unknown(self, update, context):
        """Telegram bot catch-all for unknown commands."""

        text = """There is no such command. Do you need some /help?"""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def broken(self, update, context):
        """Telegram bot catch-all in maintenance mode."""

        text = """Lajujabot is asleep right now. 😴
                  There's been major changes to the Twitch API, which are not fully supported by our backend yet. We're working on it, please come back later! 🙏"""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def sub(self, update, context):
        """Telegram bot command /sub to subscribe to broadcaster args[0]."""

        chat_id = update.message.chat_id

        if len(context.chat_data) >= 100:
            text = "There's already 100 subscriptions on this chat, and it's quite enough for my own little server. If you want more, tweak the code and deploy it yourself."
            context.bot.send_message(chat_id=chat_id, text=text)
            return

        if not context.args:
            text = "You must submit a Twitch channel name for this to work."
            context.bot.send_message(chat_id=chat_id, text=text)
            return

        if len(context.args) > 1:
            text = "Please send one channel name at a time."
            context.bot.send_message(chat_id=chat_id, text=text)
            return

        broadcaster_name = context.args[0]
        if broadcaster_name in context.chat_data.values():
            text = f"You're already subscribed to {broadcaster_name}'s channel, so we're good here."
            context.bot.send_message(chat_id=chat_id, text=text)
            return

        broadcaster_id = self._tw_get_broadcaster_id(broadcaster_name)
        if not broadcaster_id:
            text = "This account cannot be found. Please check your input."
            context.bot.send_message(chat_id=chat_id, text=text)
            return

        self._sub_by_id(update, context, broadcaster_id, broadcaster_name)


    def unsub(self, update, context):
        """Telegram bot command /unsub to unsubscribe from broadcaster args[0]."""

        if not context.args:
            text = "You must submit a Twitch channel name for this to work."
            context.bot.send_message(chat_id=update.message.chat_id, text=text)
            return

        if len(context.args) > 1:
            text = "Please send one channel name at a time."
            context.bot.send_message(chat_id=update.message.chat_id, text=text)
            return

        broadcaster_name = context.args[0]
        if not broadcaster_name in context.chat_data.values():
            text = f"You weren't subscribed to the channel '{broadcaster_name}', so we're good here."
            context.bot.send_message(chat_id=update.message.chat_id, text=text)
            return

        broadcaster_id = list(context.chat_data.keys())[list(context.chat_data.values()).index(broadcaster_name)]
        self._unsub_by_id(update, context, broadcaster_id)


    def unsub_all(self, update, context):
        """Telegram bot command /unsub_all to unsubscribe from all broadcasters."""

        if not context.chat_data:
            text = "You're not subscribed to any channel, so we're good here."
            context.bot.send_message(chat_id=update.message.chat_id, text=text)
            return

        for broadcaster_id in list(context.chat_data.keys()):
            self._unsub_by_id(update, context, broadcaster_id)


    def subs_import(self, update, context):
        """Telegram bot command /subs_import to subscribe to all channels followed by Twitch account args[0]."""

        if not context.args:
            text = "You must submit a Twitch account name for this to work."
            context.bot.send_message(chat_id=update.message.chat_id, text=text)
            return

        user_name = context.args[0]
        user_id = self._tw_get_broadcaster_id(user_name)

        if not user_id:
            text = "This account cannot be found. Please check your input."
            context.bot.send_message(chat_id=update.message.chat_id, text=text)
            return

        followed_channels = self._tw_get_followed_channels(user_id)
        if not followed_channels:
            text = "It seems this account does not follow any other account."
            context.bot.send_message(chat_id=update.message.chat_id, text=text)
            return

        for followed_broadcaster in followed_channels[:100]:
            self._sub_by_id(
                update,
                context,
                followed_broadcaster["to_id"],
                followed_broadcaster["to_name"]
            )
        text = ""
        if len(followed_channels) > 100:
            text += "You cannot import more than 100 accounts.\n"
        text += "Finished importing account subscriptions."
        context.bot.send_message(chat_id=update.message.chat_id, text=text)


    def list(self, update, context):
        """Telegram bot command /list to list all current subscriptions."""

        if not context.chat_data:
            text = "It seems you have no subscriptions yet."
            context.bot.send_message(chat_id=update.message.chat_id, text=text)
            return

        text = "Here's a list of your subscriptions:"
        for broadcaster_name in context.chat_data.values():
            text += "\n" + broadcaster_name
        context.bot.send_message(chat_id=update.message.chat_id, text=text)
