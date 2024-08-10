import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    print(f'Bot ID: {bot.user.id}')
    print(f'Connected to {len(bot.guilds)} guilds:')
    for guild in bot.guilds:
        print(f' - {guild.name} (ID: {guild.id})')
    print(f'Command prefix: {bot.command_prefix}')

@bot.event
async def on_message(message):
    if message.author.bot:
        print(f"Bot message detected: {message.content}")
    
    await bot.process_commands(message)

@bot.command()
async def join(ctx):
    print(f"Join command received from {ctx.author}")
    try:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            print(f"Attempting to join channel: {channel}")
            await channel.connect()
            await ctx.send(f'Joined {channel}')
            print(f"Successfully joined channel: {channel}")
        else:
            await ctx.send("You're not in a voice channel.")
            print(f"Join failed: User {ctx.author} not in a voice channel")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")
        print(f"Error in join command: {str(e)}")

@bot.command()
async def start_voice(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        voice_client = ctx.voice_client

        if voice_client is None:
            await channel.connect()
            await ctx.send(f'Joined {channel} and started voice chat.')
        elif voice_client.channel != channel:
            await voice_client.move_to(channel)
            await ctx.send(f'Moved to {channel} and started voice chat.')
        else:
            await ctx.send('Already in your voice channel.')
    else:
        await ctx.send("You need to be in a voice channel to start voice chat.")

bot.run(os.getenv('DISCORD_TOKEN'))