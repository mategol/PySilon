import asyncio
import os
import uuid
from typing import Dict

import discord
from discord.ext import commands
from dotenv import load_dotenv
from supabase import acreate_client


load_dotenv(".env.bot")

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
BOT_SUPABASE_EMAIL = os.environ["BOT_SUPABASE_EMAIL"]
BOT_SUPABASE_PASSWORD = os.environ["BOT_SUPABASE_PASSWORD"]
COMMAND_PREFIX = os.environ.get("COMMAND_PREFIX", ".")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

supabase = None
response_channel = None
pending_requests: Dict[str, int] = {}


async def setup_supabase():
    global supabase, response_channel

    if supabase is not None:
        return

    supabase = await acreate_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    auth = await supabase.auth.sign_in_with_password(
        {
            "email": BOT_SUPABASE_EMAIL,
            "password": BOT_SUPABASE_PASSWORD,
        }
    )

    if auth.user is None or auth.session is None:
        raise RuntimeError("Bot Supabase sign-in failed")

    await supabase.realtime.set_auth(auth.session.access_token)

    response_channel = supabase.channel(
        "bot-responses",
        {"config": {"private": True}},
    )

    response_channel.on_broadcast(
        event="command_result",
        callback=lambda payload: asyncio.create_task(handle_command_result(payload)),
    )
    response_channel.on_broadcast(
        event="command_error",
        callback=lambda payload: asyncio.create_task(handle_command_error(payload)),
    )

    await response_channel.subscribe()


async def get_device_by_slot(slot_number):
    result = await (
        supabase.table("device_slots")
        .select("slot_number, device_id, devices!inner(status, display_name)")
        .eq("slot_number", slot_number)
        .execute()
    )

    if not result.data:
        return None

    row = result.data[0]
    if row["devices"]["status"] != "active":
        return None

    return row


async def get_discord_channel(channel_id):
    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel

    try:
        return await bot.fetch_channel(channel_id)
    except Exception:
        return None


async def handle_command_result(payload):
    data = payload.get("payload", {})
    request_id = data.get("request_id")
    channel_id = pending_requests.pop(request_id, None)

    if channel_id is None:
        return

    channel = await get_discord_channel(channel_id)
    if channel is None:
        return

    slot_number = data.get("slot_number")
    display_name = data.get("display_name") or "Unknown device"
    cmd = data.get("cmd") or "command"
    result = data.get("result") or {}
    summary = result.get("summary") or "No result."

    await channel.send(f"Client {slot_number} ({display_name}) `{cmd}`:\n```{summary}```")


async def handle_command_error(payload):
    data = payload.get("payload", {})
    request_id = data.get("request_id")
    channel_id = pending_requests.pop(request_id, None)

    if channel_id is None:
        return

    channel = await get_discord_channel(channel_id)
    if channel is None:
        return

    slot_number = data.get("slot_number")
    error = data.get("error") or "Unknown error"
    await channel.send(f"Client {slot_number} error: `{error}`")


async def send_monitor_command(ctx, slot_number, command_name):
    await setup_supabase()

    device = await get_device_by_slot(slot_number)
    if device is None:
        await ctx.send(f"Slot {slot_number} not found or not active.")
        return

    request_id = str(uuid.uuid4())
    pending_requests[request_id] = ctx.channel.id

    command_channel = supabase.channel(
        f"device:{device['device_id']}",
        {"config": {"private": True}},
    )

    try:
        await command_channel.subscribe()
        await command_channel.send_broadcast(
            "command",
            {
                "cmd": command_name,
                "request_id": request_id,
                "args": {},
            },
        )
    finally:
        try:
            await supabase.remove_channel(command_channel)
        except Exception:
            pass

    await ctx.send(f"Sent `{command_name}` to slot {slot_number}.")


def usage_for(command_name):
    return (
        f"Usage: `{COMMAND_PREFIX}{command_name} <slot>`\n"
        f"Example: `{COMMAND_PREFIX}{command_name} 3`\n"
        f"Use `{COMMAND_PREFIX}devices` to list active clients."
    )


@bot.event
async def on_ready():
    await setup_supabase()
    print(f"Logged in as {bot.user}")


@bot.command()
async def cpu(ctx, slot_number: int):
    await send_monitor_command(ctx, slot_number, "cpu")


@bot.command()
async def ram(ctx, slot_number: int):
    await send_monitor_command(ctx, slot_number, "ram")


@bot.command()
async def disk(ctx, slot_number: int):
    await send_monitor_command(ctx, slot_number, "disk")


@cpu.error
@ram.error
@disk.error
async def monitor_command_error(ctx, error):
    command_name = ctx.command.name if ctx.command else "command"

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(usage_for(command_name))
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send(
            f"Slot must be a number.\n"
            f"{usage_for(command_name)}"
        )
        return

    raise error


@bot.command()
async def devices(ctx):
    await setup_supabase()
    result = await (
        supabase.table("device_slots")
        .select("slot_number, device_id, devices!inner(status, display_name, last_seen_at)")
        .order("slot_number")
        .execute()
    )

    if not result.data:
        await ctx.send("No devices found.")
        return

    lines = []
    for row in result.data:
        device = row["devices"]
        lines.append(
            f"{row['slot_number']}: {device.get('display_name') or row['device_id']} "
            f"[{device.get('status')}] last seen {device.get('last_seen_at')}"
        )

    await ctx.send("```" + "\n".join(lines) + "```")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
