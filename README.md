This Telegram bot sends notifications when selected Twitch streamers go live. It works in private chats and also in group chats.

### How it works

We make use of [`python-telegram-bot`](https://github.com/python-telegram-bot/python-telegram-bot) & Twitch subscriptions via [`twitchAPI`](https://github.com/Teekeks/pyTwitchAPI). Basically the `twitchAPI` library sets up a webhook which will make Twitch report go-live events to a public domain under your control. When the alert reaches your side (usually 30-60s after the streamer actually goes live), it triggers the bot into sending a message to every chat which subscribed to the related Twitch channel.

These subscriptions are persistent, meaning that the bot should automatically restore them after a crash.

### What it needs

- [A Telegram bot token](https://core.telegram.org/bots#6-botfather);
- [A Twitch application id & secret](https://dev.twitch.tv/console/apps/create);
- A secure host for the webhook listener.

If you've already got control over a domain served with TLS 1.2+ (from standard port 443; this is [a Twitch requirement](https://dev.twitch.tv/docs/eventsub/handling-webhook-events/)), you only need to proxy the webhook traffic to this application e.g. on port 15151.

With nginx, this would mean adding to your `listen 443 ssl` server block something like:

```nginx
location /lajujabot-webhook/ {
    proxy_pass http://127.0.0.1:15151/; }
```

### Start the bot

```bash
# System dependencies
sudo apt install python3 python3-pip
pip3 install virtualenvwrapper

# Get things ready
git clone https://github.com/ria4/lajujabot
cd lajujabot
mkvirtualenv -p /usr/bin/python3 lajujabot

# Python dependencies
(lajujabot)$ pip3 install -r requirements.txt
```

Create a `config.json` with the mentioned values:

```json
{
    "TelegramBotToken": "TELEGRAM_BOT_TOKEN",
    "TwitchAppClientID": "TWITCH_APP_CLIENT_ID",
    "TwitchAppClientSecret": "TWITCH_APP_CLIENT_SECRET",
    "CallbackURL": "https://mydomain.tld/lajujabot-webhook/",
    "ListeningPort": "15151",
    "PersistenceFile": "/opt/lajujabot/subscriptions.pickle",
    "LogFile": "/opt/lajujabot/error.log"
}
```

Path `/lajujabot-webhook/` and port 15151 are mainly suggestions. It's sensible to keep the persistence and log files in the bot directory, but you can get creative if you want.

The bot should be able to start now:

```bash
python3 main.py
```

Note that you can specify an alternative configuration file using `python3 main.py -c config2.json`.

### TODO

- Factor method for removing a `broadcaster_id` from the `chat_data` in `bot.py`
- Catch `telegram.error.BadRequest: Chat not found` to remove discontinued chats from `chat_data`

### Credits

This bot is a rework of [`misterino`](https://github.com/avivace/misterino), by Denni Bevilacqua and Antonio Vivace.

It is mostly indebted to the [`twitchAPI`](https://github.com/Teekeks/pyTwitchAPI) implementation by Lena 'Teekeks' During.
