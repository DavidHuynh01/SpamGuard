import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
from dotenv import load_dotenv
import json
import os

# --- CONFIG ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
MUTE_DURATION = timedelta(hours=24)
DEFAULT_PURGE_DURATION = timedelta(hours=2)

PURGE_CHOICES = [
    app_commands.Choice(name="1 hour", value=1),
    app_commands.Choice(name="2 hours", value=2),
    app_commands.Choice(name="6 hours", value=6),
    app_commands.Choice(name="12 hours", value=12),
    app_commands.Choice(name="24 hours", value=24),
    app_commands.Choice(name="2 days", value=48),
    app_commands.Choice(name="3 days", value=72),
    app_commands.Choice(name="5 days", value=120),
    app_commands.Choice(name="1 week", value=168),
]

ACTION_CHOICES = [
    app_commands.Choice(name="Mute + Purge (default)", value="mute"),
    app_commands.Choice(name="Softban (ban & unban to delete messages)", value="softban"),
    app_commands.Choice(name="Permanent Ban", value="ban"),
]

ACTION_LABELS = {
    "mute": "Mute + Purge",
    "softban": "Softban",
    "ban": "Permanent Ban",
}

DEFAULT_MESSAGES = {
    "mute": "You were muted for 24 hours in **{server}** for sending a message in a restricted channel. Your messages have been deleted.",
    "softban": "You were softbanned from **{server}** for sending a message in a restricted channel. Your recent messages have been deleted. You may rejoin the server.",
    "ban": "You were permanently banned from **{server}** for sending a message in a restricted channel.",
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


async def send_log(guild, config, title, description, color, fields=None):
    guild_id = str(guild.id)
    if not config.get("log_enabled", {}).get(guild_id, False):
        return
    log_channel_id = config.get("log_channel", {}).get(guild_id)
    if not log_channel_id:
        return
    log_channel = guild.get_channel(log_channel_id)
    if not log_channel:
        return
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    if fields:
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=True)
    try:
        await log_channel.send(embed=embed)
    except discord.Forbidden:
        print(f"Cannot send log to #{log_channel.name} - missing permissions")


bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot is online as {bot.user}")


@bot.tree.command(name="setup", description="Add a restricted channel for SpamGuard")
@app_commands.describe(channel="The channel to lock down", action="What to do when someone posts (default: Mute + Purge)")
@app_commands.choices(action=ACTION_CHOICES)
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction, channel: discord.TextChannel, action: app_commands.Choice[str] = None):
    config = load_config()
    guild_id = str(interaction.guild.id)
    channels = config.get(guild_id, [])
    if channel.id in channels:
        await interaction.response.send_message(
            f"{channel.mention} is already being watched by SpamGuard.",
            ephemeral=True
        )
        return
    channels.append(channel.id)
    config[guild_id] = channels
    # Set action if provided
    if action:
        if "action" not in config:
            config["action"] = {}
        config["action"][guild_id] = action.value
    save_config(config)
    current_action = ACTION_LABELS.get((config.get("action", {}).get(guild_id, "mute")), "Mute + Purge")
    await interaction.response.send_message(
        f"SpamGuard is now watching {channel.mention}.\n"
        f"Action: **{current_action}** | Total watched channels: {len(channels)}",
        ephemeral=True
    )


@bot.tree.command(name="remove", description="Remove a channel from SpamGuard")
@app_commands.describe(channel="The channel to stop watching")
@app_commands.checks.has_permissions(administrator=True)
async def remove(interaction: discord.Interaction, channel: discord.TextChannel):
    config = load_config()
    guild_id = str(interaction.guild.id)
    channels = config.get(guild_id, [])
    if channel.id not in channels:
        await interaction.response.send_message(
            f"{channel.mention} is not being watched by SpamGuard.",
            ephemeral=True
        )
        return
    channels.remove(channel.id)
    config[guild_id] = channels
    save_config(config)
    await interaction.response.send_message(
        f"{channel.mention} has been removed from SpamGuard. Remaining watched channels: {len(channels)}",
        ephemeral=True
    )


@bot.tree.command(name="channels", description="List all channels watched by SpamGuard")
@app_commands.checks.has_permissions(administrator=True)
async def channels(interaction: discord.Interaction):
    config = load_config()
    guild_id = str(interaction.guild.id)
    channel_ids = config.get(guild_id, [])
    if not channel_ids:
        await interaction.response.send_message("SpamGuard is not watching any channels.", ephemeral=True)
        return
    mentions = [f"<#{cid}>" for cid in channel_ids]
    await interaction.response.send_message(
        f"SpamGuard is watching: {', '.join(mentions)}",
        ephemeral=True
    )


@bot.tree.command(name="purge", description="Delete a user's messages from a chosen time range")
@app_commands.describe(user="The user whose messages to delete", duration="How far back to delete messages")
@app_commands.choices(duration=PURGE_CHOICES)
@app_commands.checks.has_permissions(administrator=True)
async def purge(interaction: discord.Interaction, user: discord.Member, duration: app_commands.Choice[int]):
    await interaction.response.defer(ephemeral=True)
    purge_after = discord.utils.utcnow() - timedelta(hours=duration.value)
    total_deleted = 0
    target_id = user.id
    for channel in interaction.guild.text_channels:
        try:
            deleted = await channel.purge(
                limit=None,
                check=lambda m, uid=target_id: m.author.id == uid,
                after=purge_after,
                reason=f"Purge command by {interaction.user} — {duration.name}"
            )
            total_deleted += len(deleted)
        except (discord.Forbidden, discord.HTTPException):
            pass
    await interaction.followup.send(
        f"Deleted **{total_deleted}** messages from {user.mention} in the last **{duration.name}**.",
        ephemeral=True
    )
    config = load_config()
    await send_log(interaction.guild, config,
        "Manual Purge",
        f"{interaction.user.mention} purged messages from {user.mention}.",
        discord.Color.blue(),
        [
            ("Target", f"{user.mention}\n{user.id}"),
            ("Purged By", f"{interaction.user.mention}"),
            ("Range", duration.name),
            ("Messages Deleted", str(total_deleted)),
        ]
    )


@bot.tree.command(name="setpurge", description="Set how far back auto-purge deletes when someone triggers SpamGuard")
@app_commands.describe(duration="How far back to auto-delete messages")
@app_commands.choices(duration=PURGE_CHOICES)
@app_commands.checks.has_permissions(administrator=True)
async def setpurge(interaction: discord.Interaction, duration: app_commands.Choice[int]):
    config = load_config()
    guild_id = str(interaction.guild.id)
    if "purge_hours" not in config:
        config["purge_hours"] = {}
    config["purge_hours"][guild_id] = duration.value
    save_config(config)
    await interaction.response.send_message(
        f"Auto-purge duration set to **{duration.name}**.",
        ephemeral=True
    )


@bot.tree.command(name="setaction", description="Change what SpamGuard does when someone posts in a watched channel")
@app_commands.describe(action="The action to take")
@app_commands.choices(action=ACTION_CHOICES)
@app_commands.checks.has_permissions(administrator=True)
async def setaction(interaction: discord.Interaction, action: app_commands.Choice[str]):
    config = load_config()
    guild_id = str(interaction.guild.id)
    if "action" not in config:
        config["action"] = {}
    config["action"][guild_id] = action.value
    save_config(config)
    await interaction.response.send_message(
        f"SpamGuard action set to **{action.name}**.",
        ephemeral=True
    )


@bot.tree.command(name="setmessage", description="Set a custom DM message for a SpamGuard action")
@app_commands.describe(action="Which action to set the message for", message="Custom message ({server} will be replaced with the server name)")
@app_commands.choices(action=ACTION_CHOICES)
@app_commands.checks.has_permissions(administrator=True)
async def setmessage(interaction: discord.Interaction, action: app_commands.Choice[str], message: str):
    config = load_config()
    guild_id = str(interaction.guild.id)
    if "messages" not in config:
        config["messages"] = {}
    if guild_id not in config["messages"]:
        config["messages"][guild_id] = {}
    config["messages"][guild_id][action.value] = message
    save_config(config)
    preview = message.replace("{server}", interaction.guild.name)
    await interaction.response.send_message(
        f"Custom message set for **{action.name}**.\n\nPreview:\n> {preview}",
        ephemeral=True
    )


@bot.tree.command(name="viewmessage", description="View the current DM messages for each SpamGuard action")
@app_commands.checks.has_permissions(administrator=True)
async def viewmessage(interaction: discord.Interaction):
    config = load_config()
    guild_id = str(interaction.guild.id)
    custom_messages = config.get("messages", {}).get(guild_id, {})
    lines = []
    for key, label in ACTION_LABELS.items():
        msg = custom_messages.get(key, DEFAULT_MESSAGES[key])
        preview = msg.replace("{server}", interaction.guild.name)
        custom_tag = " *(custom)*" if key in custom_messages else " *(default)*"
        lines.append(f"**{label}**{custom_tag}\n> {preview}")
    await interaction.response.send_message("\n\n".join(lines), ephemeral=True)


@bot.tree.command(name="resetmessage", description="Reset a DM message back to default")
@app_commands.describe(action="Which action to reset the message for")
@app_commands.choices(action=ACTION_CHOICES)
@app_commands.checks.has_permissions(administrator=True)
async def resetmessage(interaction: discord.Interaction, action: app_commands.Choice[str]):
    config = load_config()
    guild_id = str(interaction.guild.id)
    custom_messages = config.get("messages", {}).get(guild_id, {})
    if action.value in custom_messages:
        del custom_messages[action.value]
        save_config(config)
    preview = DEFAULT_MESSAGES[action.value].replace("{server}", interaction.guild.name)
    await interaction.response.send_message(
        f"Message for **{action.name}** reset to default.\n\nPreview:\n> {preview}",
        ephemeral=True
    )


@bot.tree.command(name="setlog", description="Set the channel where SpamGuard logs actions")
@app_commands.describe(channel="The channel to send logs to")
@app_commands.checks.has_permissions(administrator=True)
async def setlog(interaction: discord.Interaction, channel: discord.TextChannel):
    config = load_config()
    guild_id = str(interaction.guild.id)
    if "log_channel" not in config:
        config["log_channel"] = {}
    config["log_channel"][guild_id] = channel.id
    # Auto-enable logging when setting a channel
    if "log_enabled" not in config:
        config["log_enabled"] = {}
    config["log_enabled"][guild_id] = True
    save_config(config)
    await interaction.response.send_message(
        f"SpamGuard will now log actions to {channel.mention}.",
        ephemeral=True
    )


logger_group = app_commands.Group(name="logger", description="Enable or disable SpamGuard logging")


@logger_group.command(name="enable", description="Enable SpamGuard action logging")
@app_commands.checks.has_permissions(administrator=True)
async def logger_enable(interaction: discord.Interaction):
    config = load_config()
    guild_id = str(interaction.guild.id)
    log_channel_id = config.get("log_channel", {}).get(guild_id)
    if not log_channel_id:
        await interaction.response.send_message(
            "No log channel set. Use `/setlog` first to pick a channel.",
            ephemeral=True
        )
        return
    if "log_enabled" not in config:
        config["log_enabled"] = {}
    config["log_enabled"][guild_id] = True
    save_config(config)
    await interaction.response.send_message(
        f"Logging enabled. Logs will be sent to <#{log_channel_id}>.",
        ephemeral=True
    )


@logger_group.command(name="disable", description="Disable SpamGuard action logging")
@app_commands.checks.has_permissions(administrator=True)
async def logger_disable(interaction: discord.Interaction):
    config = load_config()
    guild_id = str(interaction.guild.id)
    if "log_enabled" not in config:
        config["log_enabled"] = {}
    config["log_enabled"][guild_id] = False
    save_config(config)
    await interaction.response.send_message(
        "Logging disabled.",
        ephemeral=True
    )


bot.tree.add_command(logger_group)


@setup.error
@remove.error
@channels.error
@purge.error
@setpurge.error
@setaction.error
@setmessage.error
@viewmessage.error
@resetmessage.error
@setlog.error
@logger_enable.error
@logger_disable.error
async def command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    config = load_config()
    guild_id = str(message.guild.id) if message.guild else None
    locked_channels = config.get(guild_id, [])

    if message.channel.id in locked_channels:
        member = message.author

        # Delete the triggering message
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        # Determine action and message
        action = config.get("action", {}).get(guild_id, "mute")
        custom_messages = config.get("messages", {}).get(guild_id, {})
        dm_message = custom_messages.get(action, DEFAULT_MESSAGES[action]).replace("{server}", message.guild.name)

        # Send warning message in the channel
        action_text = ACTION_LABELS.get(action, "Mute + Purge")
        try:
            await message.channel.send(
                f"{member.mention} Potential Bot — Action: **{action_text}**",
                delete_after=86400
            )
        except discord.Forbidden:
            pass

        if action == "mute":
            # Timeout (mute) the user for 24 hours
            try:
                await member.timeout(MUTE_DURATION, reason="Sent a message in the restricted channel")
            except discord.Forbidden:
                print(f"Cannot mute {member} - missing permissions or role hierarchy issue")

            # Purge their messages using configured or default duration
            purge_hours = config.get("purge_hours", {}).get(guild_id, 2)
            purge_duration = timedelta(hours=purge_hours)
            target_id = member.id
            total_deleted = 0
            for channel in message.guild.text_channels:
                try:
                    deleted = await channel.purge(
                        limit=None,
                        check=lambda m, uid=target_id: m.author.id == uid,
                        after=discord.utils.utcnow() - purge_duration,
                        reason=f"Purging messages from {member} (restricted channel violation)"
                    )
                    if deleted:
                        total_deleted += len(deleted)
                        print(f"Deleted {len(deleted)} messages in #{channel.name}")
                except (discord.Forbidden, discord.HTTPException) as e:
                    print(f"Error in #{channel.name}: {e}")

            try:
                await member.send(dm_message)
            except discord.Forbidden:
                pass

            await send_log(message.guild, config,
                "Mute + Purge",
                f"{member.mention} (`{member}`) was muted and purged.",
                discord.Color.orange(),
                [
                    ("User", f"{member.mention}\n{member.id}"),
                    ("Triggered In", f"<#{message.channel.id}>"),
                    ("Messages Deleted", str(total_deleted)),
                    ("Purge Range", f"{purge_hours} hour(s)"),
                    ("Mute Duration", "24 hours"),
                ]
            )

        elif action == "softban":
            # DM before ban since they won't be in the server after
            try:
                await member.send(dm_message)
            except discord.Forbidden:
                pass

            # Ban with 7-day message delete, then immediately unban
            try:
                await message.guild.ban(member, delete_message_days=7, reason="SpamGuard softban — restricted channel violation")
                await message.guild.unban(member, reason="SpamGuard softban — automatic unban")
                print(f"Softbanned {member}")
            except discord.Forbidden:
                print(f"Cannot softban {member} - missing permissions or role hierarchy issue")

            await send_log(message.guild, config,
                "Softban",
                f"{member.mention} (`{member}`) was softbanned.",
                discord.Color.yellow(),
                [
                    ("User", f"{member.mention}\n{member.id}"),
                    ("Triggered In", f"<#{message.channel.id}>"),
                    ("Messages Deleted", "7 days worth"),
                ]
            )

        elif action == "ban":
            # DM before ban
            try:
                await member.send(dm_message)
            except discord.Forbidden:
                pass

            # Permanent ban with 7-day message delete
            try:
                await message.guild.ban(member, delete_message_days=7, reason="SpamGuard permanent ban — restricted channel violation")
                print(f"Permanently banned {member}")
            except discord.Forbidden:
                print(f"Cannot ban {member} - missing permissions or role hierarchy issue")

            await send_log(message.guild, config,
                "Permanent Ban",
                f"{member.mention} (`{member}`) was permanently banned.",
                discord.Color.red(),
                [
                    ("User", f"{member.mention}\n{member.id}"),
                    ("Triggered In", f"<#{message.channel.id}>"),
                    ("Messages Deleted", "7 days worth"),
                ]
            )

    await bot.process_commands(message)

bot.run(TOKEN)
