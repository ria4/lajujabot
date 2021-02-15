Telegram bot notifying when your favorite streamers go live on Twitch.tv. Users can subscribe to Twitch streamers and receive a message when they go online (privately or in a group).

This is a rework of the [misterino](https://github.com/zefzefzfzef) bot by truc & muche.

### Stack

We make use of 

- [_New_ Twitch API](https://dev.twitch.tv/docs/api/reference/);
- [Twitch Webhooks](https://dev.twitch.tv/docs/api/webhooks-reference/) to subscribe to events instead of polling for them.
- [Flask](http://flask.pocoo.org/docs/1.0/api/) as webhook listener;
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot);

#### Webhook mode

You need:

- A public IP address and/or domain;
- A SSL certificate;
- A webhook listener;
- A reverse proxy exposing the webhook listener, handling TLS 1.2+ HTTPS-traffic.

We don't use the python-telegram-bot integrated webserver, but we listen for webhooks with Flask, then we dispatch the de-jsonified (is this even a word?) payloads to another thread, using a shared Queue.

During development, we use the polling mode to get the payload from messages sent to the bot, then pipe them to `webhookTest.sh` to simulate the Telegram server sending webhook to our listener.

FYI the Twitch events are received anyway listening for webhooks, the `mode` setting changes only the telegram bot operating mode. You don't need all the mentioned things for Twitch because it doesn't require an https enabled endpoint: as long as you have DMZ/open ports you are able to set your own IP as _callback_ for the webhook subscriptions.

### Get started

```bash
# System dependencies
sudo apt install python3 python3-pip

# Get things ready
git clone https://github.com/ria4/lajujabot
cd lajujabot
python3 -m venv .
source bin/activate

# Python dependencies
pip3 install -r requirements.txt
```

You need a Telegram bot token (use [BotFather](https://t.me/BotFather)), a Twitch Client ID and a Twitch Client Secret (register an application on the [Twitch dev portal](https://dev.twitch.tv/dashboard/apps/create)).

Create a `config.json` with the mentioned values:

```json
{
    "TelegramBotToken": "TELEGRAM_BOT_TOKEN",
    "TwitchAppClientID": "TWITCH_APP_CLIENT_ID",
    "TwitchAppClientSecret": "TWITCH_APP_CLIENT_SECRET"
    "CallbackURL": "CALLBACK_URL"
}
```

Start the bot

```bash
python3 main.py
```

You can specify the configuration file to use using `python3 main.py -c config2.json`.

Bot is up and running, talk to it on Telegram.
