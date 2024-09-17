import discord
from discord.ext import commands, tasks
import aiohttp
import time
from discord import app_commands
import os
import sys
import redis
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta


load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN') #A .env file is needed or you can replace the "os.getenv('DISCORD_TOKEN')" with the token this applies to everything below this too.
REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = int(os.getenv('REDIS_PORT'))
REDIS_DB = int(os.getenv('REDIS_DB'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
github_link = "https://github.com/Mr-Baguetter/Space-Engineers-Discord-Bot"  # Change to your repo if you create a fork, or create a new repo
allowed_user_id = 617462103938302098 #Change this to your Discord id.
BOT_PATH = 'C:\\Users\\admin\\Downloads\\Discordbot\\SEBot.py' #Change this to the bot path.

redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, db=REDIS_DB, decode_responses=True) #I would recommend setting up Redis since alot of the code requires it. Bot likely wont start without it.

SERVER_URL = 'http://localhost:3000/players'  # URL of the Express server. If self hosted should be http://localhost:3000/players
CHECK_INTERVAL = 1
log_channel_key = "log_channel_id"
utc_minus_5 = timezone(timedelta(hours=-5)) #Change hours=x to your UTC time offset.

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)
start_time = None

server_was_offline = False

async def fetch_player_count():
    async with aiohttp.ClientSession() as session:
        async with session.get(SERVER_URL) as response:
            if response.status == 200:
                players = await response.json()
                return len(players)
            else:
                return None


@tasks.loop(seconds=CHECK_INTERVAL)
async def update_status():
    player_count = await fetch_player_count()
    if player_count is not None:
        await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=f"{player_count}/16 players online"))


@bot.event
async def on_ready():
    await bot.tree.sync()
    global start_time
    start_time = datetime.now(utc_minus_5)
    print(f'Logged in as {bot.user.name}')
    print('Commands have been synced.')
    check_server_status.start()
    update_status.start()

previous_players = set()
player_join_times = {}

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_server_status():
    global previous_players
    global server_was_offline

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(SERVER_URL) as response:
                if response.status == 200:
                    current_players = await response.json()
                    current_player_names = set(player['name'] for player in current_players)

                    new_players = current_player_names - previous_players
                    for player in new_players:
                        player_join_times[player] = datetime.now(utc_minus_5)
                        await notify_player_joined(player)

                    left_players = previous_players - current_player_names
                    for player in left_players:
                        join_time = player_join_times.pop(player, None)
                        if join_time:
                            time_spent = datetime.now(utc_minus_5) - join_time
                            await notify_player_left(player, time_spent)

                    previous_players = current_player_names

                    if server_was_offline:
                        await notify_server_online()
                        server_was_offline = False
                else:
                    if not server_was_offline:
                        await notify_server_offline()
                        server_was_offline = True
    except aiohttp.ClientError:
        if not server_was_offline:
            await notify_server_offline()
            server_was_offline = True


async def notify_player_joined(player_name):
    log_channel_id = await get_log_channel_id()
    if log_channel_id:
        channel = bot.get_channel(int(log_channel_id))
        if channel:
            await channel.send(f"Player **{player_name}** has joined the server at {datetime.now(utc_minus_5).strftime('%H:%M:%S UTC')}.")
        else:
            print("Log channel not found.")
    else:
        print("Log channel has not been set.")

async def notify_player_left(player_name, time_spent):
    log_channel_id = await get_log_channel_id()
    notifications_key = "leave_notifications"

    if log_channel_id:
        channel = bot.get_channel(int(log_channel_id))
        if channel:
            hours, remainder = divmod(time_spent.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_spent_str = f"{int(hours)} hour{'s' if hours != 1 else ''}, {int(minutes)} minute{'s' if minutes != 1 else ''}, and {int(seconds)} second{'s' if seconds != 1 else ''}"

            subscribed_user_ids = redis_client.smembers(notifications_key)
            if subscribed_user_ids:
                mentions = ' '.join([f"<@{user_id}>" for user_id in subscribed_user_ids])
                await channel.send(f"Player **{player_name}** has left the server after {time_spent_str}. {mentions}")
            else:
                await channel.send(f"Player **{player_name}** has left the server after {time_spent_str}.")
        else:
            print("Log channel not found.")
    else:
        print("Log channel has not been set.")


@bot.tree.command(name="setlogchannel", description="Set the log channel for server status updates")
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if interaction.user.id == allowed_user_id:
        await set_log_channel_id(channel.id)
        await interaction.response.send_message(f"Log channel has been set to {channel.mention}.")
    else:
        await interaction.response.send_message("You don't have permission to set the logs channel.")

async def set_log_channel_id(channel_id):
    redis_client.set('log_channel_id', channel_id)

async def get_log_channel_id():
    return redis_client.get('log_channel_id')

async def notify_server_offline():
    print("Error: API is offline or the server is restarting.")
    log_channel_id = await get_log_channel_id()
    if log_channel_id:
        channel = bot.get_channel(int(log_channel_id))
        if channel:
            await channel.send(
                "Error: API is offline or the server is restarting. Please notify <@617462103938302098> if the API is down."
            )
        else:
            print("Log channel not found.")
    else:
        print("Log channel has not been set.")

async def notify_server_online():
    log_channel_id = await get_log_channel_id()
    if log_channel_id:
        channel = bot.get_channel(int(log_channel_id))
        if channel:
            await channel.send(
                "Connection to the server reestablished. The API is back online!"
            )
        else:
            print("Log channel not found.")
    else:
        print("Log channel has not been set.")

def seconds_to_hours_and_minutes(seconds):
    hours, remainder = divmod(int(seconds), 3600)  
    minutes = remainder // 60 
    if hours > 0:
        return f"{hours} hour{'s' if hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"
    else:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"

@bot.tree.command(name='playerlist', description='Get the current players on Keen NA1!')
@app_commands.allowed_installs(guilds=True, users=True)
async def playerlist(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SERVER_URL) as response:
                if response.status == 200:
                    players = await response.json()
                    player_count = len(players)

                    if players:
                        embed = discord.Embed(
                            title=f"Current Players on the Server ({player_count}/16)",
                            description="Here are the players currently online, sorted by playtime:",
                            color=discord.Color.green()
                        )

                        for player in players:
                            playtime_seconds = player['raw'].get('time', 0)
                            playtime = seconds_to_hours_and_minutes(playtime_seconds)

                            embed.add_field(
                                name=player['name'],
                                value=f"Playtime: {playtime}",
                                inline=False
                            )

                        await interaction.response.send_message(embed=embed)
                    else:
                        await interaction.response.send_message('No players are currently online.')
                else:
                    await interaction.response.send_message(
                        "Error: cannot fetch player list, please notify <@617462103938302098> that the API is down.",
                        ephemeral=True
                    )
        except aiohttp.ClientError:
            await interaction.response.send_message(
                "Error: cannot fetch player list, please notify <@617462103938302098> that the API is down.",
                ephemeral=True
            )


@bot.tree.command(name="ping", description="Check the bot's latency and response time.")
@app_commands.allowed_installs(guilds=True, users=True)
async def ping(interaction: discord.Interaction):
    start_time = time.time()
    await interaction.response.send_message("Pinging...")
    end_time = time.time()
    latency = bot.latency * 1000
    response_time = (end_time - start_time) * 1000

    await interaction.edit_original_response(
        content=f"Pong! Latency: {latency:.2f}ms | Response Time: {response_time:.2f}ms")


@bot.tree.command(name='help', description='Get information about the bot.')
@app_commands.allowed_installs(guilds=True, users=True)
async def info(interaction: discord.Interaction):
    bot_description = (
        "I am a bot created to get the player list of Keen NA1. "
        "You can use various commands to interact with me and get information.\n"
        "Available commands are:\n"
        "/help : Shows this command\n"
        "/playerlist : Lists all the players in NA1\n"
        "/ping : Bot ping\n"
        "/source : Bot source code\n"
        "/orecalc : Ore calculator spreadsheet \n"
        "/suggestion : Suggest things to be added to the bot \n"
        "/uptime : View the bots uptime"
        "/versioninfo : View latest changes."
        "/playerleavenotification : Get notified when a player leaves the server."
        '/stopplayerleavenotification : Stop getting notified when a player leaves the server.'
    )
    await interaction.response.send_message(f"Bot Info:\n{bot_description}")


@bot.tree.command(name='source', description='Get the link to the GitHub repository.')
@app_commands.allowed_installs(guilds=True, users=True)
async def link(interaction: discord.Interaction):
    await interaction.response.send_message(f"Check out the source code here: {github_link}")


@bot.tree.command(name='orecalc', description='Get a link to the ore calculator spreadsheet.')
@app_commands.allowed_installs(guilds=True, users=True)
async def link(interaction: discord.Interaction):
    spreadsheet_link = "https://docs.google.com/spreadsheets/d/1gXqODCeVkEtX4inPnZikTXRwo3n0_wzogJGda3W9JJg/edit?usp=sharing"
    await interaction.response.send_message(f"Please make a copy of the spreadsheet here: {spreadsheet_link}")


@bot.tree.command(name='restartbot', description='Restart the bot. (Only Mr. Baguetter can run this)')
@app_commands.allowed_installs(guilds=True, users=True)
async def restartbot(interaction: discord.Interaction):
    if interaction.user.id == allowed_user_id:
        await interaction.response.send_message('Restarting the bot...')
        print('Restart command issued.')
        await bot.close()
        os.execv(sys.executable, ['python', 'BOT_PATH'])
    else:
        await interaction.response.send_message("You don't have permission to restart the bot.")

@bot.tree.command(name='suggestion', description='Submit a suggestion.')
@app_commands.describe(suggestion="Your suggestion for the server or bot.")
async def suggestion(interaction: discord.Interaction, suggestion: str):
    suggestions_key = "suggestions_list"
    redis_client.rpush(suggestions_key, suggestion)
    await interaction.response.send_message(f"Thank you for your suggestion! Your idea has been submitted.")


@bot.tree.command(name='showsuggestions', description='Show all suggestions.')
@app_commands.allowed_installs(guilds=True, users=True)
async def showsuggestions(interaction: discord.Interaction):
    if interaction.user.id == allowed_user_id:
        suggestions_key = "suggestions_list"
        suggestions = redis_client.lrange(suggestions_key, 0, -1)
        if suggestions:
            embed = discord.Embed(
                title="Suggestions",
                description="Here are the suggestions submitted:",
                color=discord.Color.green()
            )
            for idx, suggestion in enumerate(suggestions, 1):
                embed.add_field(
                    name=f"Suggestion #{idx}",
                    value=suggestion.decode('utf-8'),
                    inline=False
                )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("No suggestions found.")
    else:
        await interaction.response.send_message("You do not have permission to view suggestions.")

@bot.tree.command(name='changelog', description='Bot changelog')
@app_commands.allowed_installs(guilds=True, users=True)
async def changelog(interaction: discord.Interaction):
        if interaction.user.id == allowed_user_id:
                bot_changelog = (
                    "Changed how the playerlist command shows playtime. \n"
                    "Added the /uptime command"
                )
                await interaction.response.send_message(f"Changelog 9/16/24 (M/D/Y):\n{bot_changelog}")
        else:
            await interaction.response.send_message("You do not have permission to send the changelog")
            
def get_uptime():
    now = datetime.now(utc_minus_5)
    uptime_duration = now - start_time
    
    days = uptime_duration.days
    hours, remainder = divmod(uptime_duration.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    time_components = []
    
    if days > 0:
        time_components.append(f"{days} day{'s' if days != 1 else ''}")
    
    if hours > 0:
        time_components.append(f"{hours} hour{'s' if hours != 1 else ''}")
    
    if minutes > 0 or (days == 0 and hours == 0):  
        time_components.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    
    if len(time_components) > 1:
        uptime_str = ', '.join(time_components[:-1]) + f", and {time_components[-1]}"
    else:
        uptime_str = time_components[0]

    return uptime_str

@bot.tree.command(name='uptime', description="Displays the bot's uptime")
@app_commands.allowed_installs(guilds=True, users=True)
async def uptime(interaction: discord.Interaction):
    uptime_str = get_uptime()
    await interaction.response.send_message(f"Bot has been up for: {uptime_str}")
    
@bot.tree.command(name='shutdown', description='shutdown the bot. (Only Mr. Baguetter can run this!)')
@app_commands.allowed_installs(guilds=True, users=True)
async def shutdown(interaction: discord.Interaction):
    if interaction.user.id == allowed_user_id:
        await interaction.response.send_message('Shuting down the bot...')
        print('Shutdown command issued.')
        await bot.close()
    else:
        await interaction.response.send_message("You don't have permission to shutdown the bot.")

BOT_VERSION = "1.6.3"
LATEST_ADDITIONS = "1.6.0 Added player join/leave logging. \n 1.6.1 Added time joined/left to player join/leave logs. \n 1.6.2 Added player leave notification commands. \n 1.6.3 Code improvements. No noticable changes."

@bot.tree.command(name='versioninfo', description='Get the current version information of the bot.')
@app_commands.allowed_installs(guilds=True, users=True)
async def versioninfo(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Bot Version Information",
        description="Here is the current version information for the bot.",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="Bot Version", value=BOT_VERSION, inline=False)
    embed.add_field(name="Latest Additions", value=LATEST_ADDITIONS, inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="playerleavenotification", description="Subscribe to notifications when a player leaves.")
async def playerleavenotification(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    notifications_key = "leave_notifications"

    if redis_client.sismember(notifications_key, user_id):
        await interaction.response.send_message("You are already subscribed to player leave notifications.", ephemeral=True)
    else:
        redis_client.sadd(notifications_key, user_id)
        await interaction.response.send_message("You have successfully subscribed to player leave notifications.", ephemeral=True)

@bot.tree.command(name="stopplayerleavenotification", description="Unsubscribe from notifications when a player leaves.")
async def stopplayerleavenotification(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    notifications_key = "leave_notifications"

    if redis_client.sismember(notifications_key, user_id):
        redis_client.srem(notifications_key, user_id)
        await interaction.response.send_message("You have successfully unsubscribed from player leave notifications.", ephemeral=True)
    else:
        await interaction.response.send_message("You are not subscribed to player leave notifications.", ephemeral=True)

bot.run(TOKEN)
