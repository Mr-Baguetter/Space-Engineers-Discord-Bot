import discord
from discord.ext import commands, tasks
import aiohttp
import time
from discord import app_commands
import os
import sys

TOKEN = 'BOT_TOKEN'  # Replace with your bot token
SERVER_URL = 'http://147.185.221.22:42614/players'  # URL of your Express server. If self hosted should be localhost:3000/players

intents = discord.Intents.default()
intents.message_content = True

# Create the bot instance
bot = commands.Bot(command_prefix='/', intents=intents)

async def fetch_player_count():
    async with aiohttp.ClientSession() as session:
        async with session.get(SERVER_URL) as response:
            if response.status == 200:
                players = await response.json()
                return len(players)
            else:
                return None


@tasks.loop(seconds=1)
async def update_status():
    player_count = await fetch_player_count()
    if player_count is not None:
        await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name=f"{player_count}/16 players online"))


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user.name}')
    print('Commands have been synced.')
    update_status.start()


def seconds_to_hours(seconds):
    """Convert seconds to hours or minutes based on playtime."""
    if seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.0f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.2f} hours"


@bot.tree.command(name='playerlist', description='Get the current players on NA1!')
async def playerlist(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get(SERVER_URL) as response:
            if response.status == 200:
                players = await response.json()
                if players:
                    embed = discord.Embed(
                        title="Current Players on Keen NA1",
                        description="Here are the players currently online, sorted by playtime:",
                        color=discord.Color.blue()  # You can set the color to whatever you like
                    )
                    
                    for player in players:
                        playtime = seconds_to_hours(player['raw'].get('time', 0))
                        embed.add_field(
                            name=player['name'],
                            value=f"Playtime: {playtime}",
                            inline=False
                        )
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message('No players are currently online.')
            else:
                await interaction.response.send_message('Failed to fetch player list. Is the API down?')

@bot.tree.command(name="ping", description="Check the bot's latency and response time.")
async def ping(interaction: discord.Interaction):
    start_time = time.time()
    await interaction.response.send_message("Pinging...")
    end_time = time.time()
    latency = bot.latency * 1000 
    response_time = (end_time - start_time) * 1000 

    await interaction.edit_original_response(
        content=f"Pong! Latency: {latency:.2f}ms | Response Time: {response_time:.2f}ms")


@bot.tree.command(name='help', description='Get information about the bot.')
async def info(interaction: discord.Interaction):
    bot_description = (
        "I am a bot created to get the player list of Keen NA1. "
        "You can use various commands to interact with me and get information.\n"
        "Available commands are:\n"
        "/help : Shows this command\n"
        "/playerlist : Lists all the players in NA1\n"
        "/ping : Bot ping\n"
        "/source : Bot source code\n"
        "/orecalc : Ore calculator spreadsheet"
    )
    await interaction.response.send_message(f"Bot Info:\n{bot_description}")

@bot.tree.command(name='source', description='Get the link to the GitHub repository.')
async def link(interaction: discord.Interaction):
    github_link = "https://github.com/Mr-Baguetter/Space-Engineers-Discord-Bot" #Change to your repo if you create a fork
    await interaction.response.send_message(f"Check out the source code here: {github_link}")

@bot.tree.command(name='orecalc', description='Get a link to the ore calculator spreadsheet.')
async def link(interaction: discord.Interaction):
    spreadsheet_link = "https://docs.google.com/spreadsheets/d/1gXqODCeVkEtX4inPnZikTXRwo3n0_wzogJGda3W9JJg/edit?usp=sharing" 
    await interaction.response.send_message(f"Please make a copy of the spreadsheet here: {spreadsheet_link}")

@bot.tree.command(name='restartbot', description='Restart the bot. (Requires administrator)')
async def restartbot(interaction: discord.Interaction):
    if interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('Restarting the bot...')
        print('Restart command issued.')
        await bot.close()
        # Rerun the script by restarting the current Python script. Change this to the directory the script is in
        os.execv(sys.executable, ['python', 'C:\\Users\\%UserProfile%\\OneDrive\\Desktop\\SEBot.py'])
    else:
        await interaction.response.send_message("You don't have permission to restart the bot.")

# Run the bot
bot.run(TOKEN)
