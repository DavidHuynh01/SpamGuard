SpamGuard is a Discord bot that locks down channels and punishes anyone who posts in them. The idea is simple: set up a honeypot channel that no real user would post in, and any spam bot that does gets dealt with automatically.

## What it does

Any message sent in a watched channel triggers one of three actions:
- **Mute + Purge** (default) - 24hr timeout and deletes their messages
- **Softban** - bans and unbans them to wipe messages, they can rejoin
- **Permanent Ban** - bans them and deletes 7 days of messages

You can watch multiple channels, customize the DM sent to punished users, choose how far back to purge (1 hour up to 1 week), and log everything to a mod channel with color-coded embeds.

All settings are per-server and persist across restarts. Every command is admin-only and ephemeral.

## Setup

You need Python 3.9+ and a bot token from the Discord Developer Portal. Make sure Message Content Intent is enabled in your bot settings.

Bot permissions needed: Manage Messages, Ban Members, Moderate Members, Send Messages, Read Message History.

```bash
git clone https://github.com/YOUR_USERNAME/SpamGuard.git
cd SpamGuard
pip install -r requirements.txt
```

Create a `.env` file:
```
DISCORD_TOKEN=your_bot_token_here
```

Run it:
```bash
python Spamguard.py
```

## Commands

`/setup #channel [action]` - add a channel to watch, optionally pick the punishment
`/remove #channel` - stop watching a channel
`/channels` - list watched channels

`/setaction` - change punishment mode
`/setpurge` - set how far back auto-purge goes
`/purge @user <duration>` - manually purge someone's messages

`/setmessage <action> <message>` - custom DM message (use `{server}` for server name)
`/viewmessage` - see current messages
`/resetmessage <action>` - reset to default

`/setlog #channel` - set where logs go (auto-enables logging)
`/logger enable` / `/logger disable` - toggle logging

## Quick example

```
/setup #verify-here
/setaction Permanent Ban
/setpurge 1 week
/setlog #mod-logs
```
