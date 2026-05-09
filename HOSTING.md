How to run SpamGuard on a DigitalOcean droplet so it stays online 24/7.

## Create a droplet

1. Go to digitalocean.com and sign up
2. Click Create > Droplets
3. Pick Ubuntu 22.04 or 24.04
4. Choose the $4/mo or $6/mo plan (cheapest one works fine)
5. Pick a region close to you
6. Set a password or add an SSH key
7. Create the droplet

## Connect to your droplet

Open a terminal and SSH in:
```bash
ssh root@your_droplet_ip
```

## Install everything

```bash
apt update && apt upgrade -y
apt install python3 python3-pip python3-venv git -y
```

## Get your bot on the server

```bash
git clone https://github.com/DavidHuynh01/SpamGuard.git
cd SpamGuard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Add your token

```bash
nano .env
```

Type this in:
```
DISCORD_TOKEN=your_bot_token_here
```

Save with Ctrl+X, then Y, then Enter.

## Test it

```bash
python3 Spamguard.py
```

If it says the bot is online, you're good. Hit Ctrl+C to stop it.

## Keep it running forever with systemd

Create a service file:
```bash
nano /etc/systemd/system/spamguard.service
```

Paste this in:
```ini
[Unit]
Description=SpamGuard Discord Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/SpamGuard
ExecStart=/root/SpamGuard/venv/bin/python3 Spamguard.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Save with Ctrl+X, then Y, then Enter.

Then run:
```bash
systemctl daemon-reload
systemctl enable spamguard
systemctl start spamguard
```

## Useful commands

Check if it's running:
```bash
systemctl status spamguard
```

See logs:
```bash
journalctl -u spamguard -f
```

Restart the bot:
```bash
systemctl restart spamguard
```

Stop the bot:
```bash
systemctl stop spamguard
```

## Updating the bot

```bash
cd /root/SpamGuard
git pull
systemctl restart spamguard
```
