This Telegram bot sends notifications when selected Twitch streamers go live. It works in private chats and also in group chats.

### How it works

We make use of [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) & webhooks via [twitchAPI](https://github.com/Teekeks/pyTwitchAPI). Basically the twitchAPI library sets up a webhook which will make Twitch report live events to a public domain under your control. When the alert reaches your side, it triggers the bot into sending a message to every chat which subscribed to the related Twitch channel.

#### What it needs

- [A Telegram bot token](https://core.telegram.org/bots#6-botfather);
- [A Twitch application id & secret](https://dev.twitch.tv/console/apps/create);
- A secure host for the webhook listener.

If you've already got control over a domain served with TLS 1.2+, you only need to proxy the webhook traffic to this application e.g. on port 15151. With nginx, this would mean adding to your server block something like

```
location /lajujabot-webhook/ {
    proxy_pass http://127.0.0.1:15151/; }
```

### Start the bot

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

Create a `config.json` with the mentioned values:

```json
{
    "TelegramBotToken": "TELEGRAM_BOT_TOKEN",
    "TwitchAppClientID": "TWITCH_APP_CLIENT_ID",
    "TwitchAppClientSecret": "TWITCH_APP_CLIENT_SECRET"
    "CallbackURL": "https://mydomain.tld/whatever/path:high_port"
}
```

Start the bot

```bash
python3 main.py
```

You can specify an alternative configuration file using `python3 main.py -c config2.json`.

### Credits

This bot is a rework of [misterino](https://github.com/avivace/misterino), by Denni Bevilacqua and Antonio Vivace.

It is also indebted to the [twitchAPI](https://github.com/Teekeks/pyTwitchAPI) implementation by Lena 'Teekeks' During.
