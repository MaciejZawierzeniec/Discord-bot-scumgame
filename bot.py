import asyncio
import datetime
import pytz
import logging
import os
import sqlite3

import discord

from discord.ext import commands
from discord import Message

from sqlite_update_subscribers import add_user
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)

bot = commands.Bot(command_prefix='!', intents=intents)

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")


@client.event
async def on_ready():
    client.loop.create_task(check_and_send_event_messages())
    client.loop.create_task(send_restart_alerts())


async def send_message_to_user(_client, message, user_id):
    user = await _client.fetch_user(user_id)
    await user.send(message)


@client.event
async def on_message(message: Message):
    table = get_table_for_channel(str(message.channel))

    if table:
        add_user_to_database(message.author.id, message.content.lower(), table)
        await message.delete()


def get_table_for_channel(channel_name: str) -> str:
    if channel_name == 'raid-alerts':
        return 'subscribers'
    elif channel_name == 'restart-alerts':
        return 'restart_subscribers'
    return ''


def add_user_to_database(discord_id: int, username: str, table: str) -> None:
    with sqlite3.connect('raid_events.db') as conn:
        add_user(discord_id, username, table)
        conn.commit()


async def check_and_send_event_messages():
    while True:
        events = fetch_unsent_events()
        if events:
            for event in events:
                await process_event(event)

        await asyncio.sleep(5)


async def send_restart_alerts():
    restart_times = ["03:00", "09:00", "15:00", "21:00"]
    server_timezone = pytz.timezone("Europe/Warsaw")
    sent_alerts = set()

    while True:
        now_local = datetime.datetime.now(server_timezone)

        for restart_time in restart_times:
            restart_datetime = datetime.datetime.strptime(restart_time, "%H:%M").replace(year=now_local.year,
                                                                                         month=now_local.month,
                                                                                         day=now_local.day)
            restart_datetime = server_timezone.localize(restart_datetime)

            if restart_datetime < now_local:
                sent_alerts.clear()
                continue

            minutes_until_restart = (restart_datetime - now_local).seconds / 60

            if 9.5 < minutes_until_restart <= 10:
                conn = sqlite3.connect('raid_events.db')
                cur = conn.cursor()
                cur.execute("SELECT user_id, username FROM restart_subscribers WHERE online = 1")
                online_users = cur.fetchall()

                for user_id, username in online_users:
                    if user_id not in sent_alerts:
                        message = f"Hey {username.capitalize()}, the server will restart in 10 minutes."
                        await send_message_to_user(client, message, user_id)
                        sent_alerts.add(user_id)

                conn.close()

        await asyncio.sleep(60)


def fetch_unsent_events():
    conn = sqlite3.connect('raid_events.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM events_table WHERE alert_sent = 0")
    events = cur.fetchall()
    conn.close()

    return events


async def process_event(event):
    timestamp, user, owner, success, attempts, obj, lock_type, alert_sent = event

    if alert_sent == 1:
        return

    owner_exists = check_owner_exists(owner)

    if owner_exists:

        update_alert_sent(timestamp)
        user_id = fetch_user_id(owner)

        if lock_type:
            message = (f'Wake up {owner.capitalize()}! {user.capitalize()} is lockpicking your {obj}. '
                       f'He tried {attempts} times with{"" if success == "Yes" else " no"} success!')
        else:
            message = f'Wake up {owner.capitalize()}! {user.capitalize()} just triggered your {obj}!'

        await send_message_to_user(client, message, user_id)


def check_owner_exists(owner):
    conn = sqlite3.connect('raid_events.db')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM subscribers WHERE username=?", (owner,))
    owner_exists = cur.fetchone()[0]
    conn.close()
    return owner_exists


def update_alert_sent(timestamp):
    conn = sqlite3.connect('raid_events.db')
    cur = conn.cursor()
    try:
        cur.execute("UPDATE events_table SET alert_sent = 1 WHERE timestamp = ?", (timestamp,))
        conn.commit()
    except Exception as e:
        logging.error(f"Failed to update alert_sent for timestamp {timestamp}: {str(e)}")
    finally:
        conn.close()


def fetch_user_id(owner):
    conn = sqlite3.connect('raid_events.db')
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM subscribers WHERE username=?", (owner,))
    user_id = cur.fetchone()[0]
    conn.close()
    return user_id


client.run(DISCORD_TOKEN)
