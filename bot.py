from inspect import cleandoc
from telegram.ext import Dispatcher, CommandHandler, Updater, PicklePersistence


class LajujaBotUpdater(Updater):
    """
    This bot has persistent bot_data to enable seamless restoration.
    bot_data is a dict of the following structure:
        { <channel_id_1> : {"subscription_uuid": <subscription_uuid>,
                            "subscribers": [chat_id_1, chat_id_2, ...] },
          <channel_id_2> : {...}, etc. }

    """
    def __init__(self, config, wh_handler):
        self.config = config
        self.wh_handler = wh_handler
        persistence = PicklePersistence(filename="subscriptions.pickle")
        super().__init__(token=config["TelegramBotToken"], persistence=persistence)
        self.register_handlers()
        self.restore_subscriptions()

    def register_handlers(self):
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('sub', self.sub))
        self.dispatcher.add_handler(CommandHandler('unsub', self.unsub))
        self.dispatcher.add_handler(CommandHandler('unsub_all', self.unsub_all))
        self.dispatcher.add_handler(CommandHandler('import', self.subs_import))
        self.dispatcher.add_handler(CommandHandler('list', self.list))
        self.dispatcher.add_handler(CommandHandler('help', self.help))
        self.dispatcher.add_handler(CommandHandler('about', self.about))

    def restore_subscriptions(self):
        subscriptions = self.persistence.get_bot_data()
        for channel_id, channel_subs in subscriptions.items():
            uuid = self.wh_handler.add_subscription(channel_id, self.callback_stream_changed)
            subscriptions[channel_id]["subscription_uuid"] = uuid
        self.persistence.update_bot_data(subscriptions)


    def callback_stream_changed(self, uuid, data):

        if not data["data"]:
            # stream went offline
            return

        username = data["data"][0]["user_name"]
        title = data["data"][0]["title"]
        text='{0} is live on Twitch! _{1}_ \nhttps://twitch.tv/{0}'.format(username, title)

        subscriptions = self.persistence.get_bot_data()
        for channel_id, channel_subs in subscriptions.items():
            if channel_subs["subscription_uuid"] == uuid:
                for chat_id in channel_subs["subscribers"]:
                    self.bot.send_message(chat_id=chat_id, text=text)
            break

    
    def start(self, update, context):
        text = """💜 Greetings! 💜
                  This bot can send you notifications on Telegram when the Twitch streamers of your choice go live. You may ask for notifications about certain channels in one group chat, while maintaining a different pool of notifications in your private chat with the bot. You just have to register your subscriptions chat by chat.
                  Ask /help to get the commands."""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def help(self, update, context):
        text = """/sub channel – send notifications when the channel goes live.
                  /unsub channel – remove the subscription to the channel.
                  /unsub_all – remove all subscriptions for the current chat.
                  /import account – monitor all channels followed by the account.
                  /list – display all subscriptions for the current chat.
                  /about – learn more about this bot.
                  /help – get some help."""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def about(self, update, context):
        text = """This bot was developed by @oriane_tury.
                  It was reworked from a bot by @avivace and @dennib.
                  Get the source code at https://github.com/ria4/lajujabot"""
        context.bot.send_message(chat_id=update.message.chat_id, text=cleandoc(text))


    def sub(self, update, context, user_name=None, user_id=None):
#if not userID.isdigit():
#    userID = self.getUserID(userID)
        # Check if we received the correct, allowed, number of subscriptions
        # to subscribe to (1 atm)
        if len(args) > 1:
            message = 'Sorry, you can subscribe only to one streamer at a time'
            bot.send_message(chat_id=update.message.chat_id, text=message)
        elif len(args) < 1:
            message = 'Sorry, you must provide one valid twitch username '\
              + 'you want to subscribe to.\n\n'\
              + 'Please try again with something like\n'\
              + '_/sub streamerUsername_'
            bot.send_message(
                chat_id=update.message.chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN)
        else:
            streamer = args[0]
            # Check if ANYONE already subscribed to that streamer
            queryParams = (streamer, )
            sql = 'SELECT COUNT(*) FROM SUBSCRIPTIONS WHERE Sub=?'
            self.c.execute(sql, queryParams)
            found = self.c.fetchone()[0]

            if not found:
                logging.warning("Adding a webhook and user subscription")
                userID = self.twitch.getUserID(streamer)
                self.twitch.updateWh('subscribe', userID)
                # Add to webhook list
                sql = ''' INSERT INTO WEBHOOKS (Sub) VALUES (?) '''

                logging.warning("Sending a webhook subscription")
                # ... Add it to db and...
                sql = '''INSERT INTO SUBSCRIPTIONS (ChatID,Sub,Active)
                         VALUES (?,?,?)'''
                queryParams = (update.message.chat_id, streamer, 1)
                self.c.execute(sql, queryParams)
                self.dbConn.commit()

                #... Notify the user
                bot.send_message(chat_id=update.message.chat_id,
                     text='Yeeey! you\'ve successfully subscribed to *{}*!'\
                     .format(streamer),
                     parse_mode=ParseMode.MARKDOWN)
            else:

                # Check if that particular user has that subscription
                queryParams = (update.message.chat_id, streamer)
                sql = 'SELECT COUNT(*) FROM SUBSCRIPTIONS WHERE ChatID=? AND Sub=?'
                self.c.execute(sql, queryParams)
                found = self.c.fetchone()[0]

                # If it doesn't exist yet...
                if not found:
                    logging.warning("Adding a user subscription")
                    userID = self.twitch.getUserID(streamer)
                    # ... Add it to db and...
                    sql = '''INSERT INTO SUBSCRIPTIONS (ChatID,Sub,Active)
                             VALUES (?,?,?)'''
                    queryParams = (update.message.chat_id, streamer, 1)
                    self.c.execute(sql, queryParams)
                    self.dbConn.commit()

                    #... Notify the user
                    bot.send_message(chat_id=update.message.chat_id,
                         text='Yeeey! you\'ve successfully subscribed to *{}*!'\
                         .format(streamer),
                         parse_mode=ParseMode.MARKDOWN)

                else:
                    logging.warning("User were already subbed")
                    # Otherwise warn the user that subscription is already existent
                    bot.send_message(chat_id=update.message.chat_id,
                         text='Don\'t worry! You are already subscribed to '\
                         + '*{}*'.format(streamer),
                         parse_mode=ParseMode.MARKDOWN)


    def unsub(self, update, context):
        # Check if we received the correct, allowed, number of subscriptions
        # to unsubscribe from (1 atm)
        if len(args) > 1:
            message = 'Sorry, you can unsubscribe only from one streamer at a time'
            bot.send_message(chat_id=update.message.chat_id, text=message)
        elif len(args) < 1:
            message = 'Sorry, you must provide one valid twitch username '\
              + 'you want to unsubscribe from.\n\n'\
              + 'Please try again with something like\n'\
              + '_/unsub streamerUsername_'
            bot.send_message(
                chat_id=update.message.chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN)
        else:
            streamer = args[0]
            queryParams = (update.message.chat_id, streamer)
            # Check if requested subscription already exits in db
            sql = 'SELECT COUNT(*) FROM SUBSCRIPTIONS WHERE ChatID=? AND Sub=?'
            self.c.execute(sql, queryParams)
            found = self.c.fetchone()[0]
            # If it exits...
            if found:
                # ... Delete it and...
                sql = 'DELETE FROM SUBSCRIPTIONS WHERE ChatID=? AND Sub=?'
                self.c.execute(sql, queryParams)
                self.dbConn.commit()
                #...Notify the user
                bot.send_message(chat_id=update.message.chat_id,
                     text='Yeeey! *{}* subscription successfully '\
                     .format(streamer) + 'deleted!',
                     parse_mode=ParseMode.MARKDOWN)
            else:
                # Otherwise warn the user that subscription doesn't exist
                bot.send_message(chat_id=update.message.chat_id,
                     text='Sorry, it seems you\'re not subscribed '\
                     + 'to *{}*'.format(streamer),
                     parse_mode=ParseMode.MARKDOWN)


    def unsub_all(self, update, context):
        subscriptions = self.persistence.get_bot_data()
        for channel_id in subscriptions:
            self.unsub(update, context, channel_id)


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
                    for followed_user in followed_data["data"]:
                        self.sub(update, context, user_name=followed_user["to_name"], user_id=followed_user["to_id"])
                    if followed_data["data"][0]["total"] == 100:
                        text = "You cannot import more than 100 accounts. Be reasonable."

            else:
                text = "This account cannot be found. Please check your input."

        if text:
            context.bot.send_message(chat_id=update.message.chat_id, text=text)


    def list(self, update, context):

        chat_id = update.message.chat_id
        followed_channels = []
        subscriptions = self.persistence.get_bot_data()
        for channel_id, channel_subs in subscriptions.items():
            if chat_id in channel_subs["subscribers"]:
                followed_channels.append(channel_id)

        if followed_channels:
            users_data = self.wh_handler.get_users(user_ids=followed_channels)
            channel_names = []
            text = "Here's a list of all of your subscriptions:"
            for channel in users_data["data"]:
                text += "\n" + channel["display_name"]
        else:
            text = "It seems you have no subscriptions yet."

        context.bot.send_message(chat_id=update.message.chat_id, text=text)
