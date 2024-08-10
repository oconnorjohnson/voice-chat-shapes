import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from openai import OpenAI
import io

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f'Joined {channel}')
    else:
        await ctx.send("You're not in a voice channel.")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send('Left the voice channel')
    else:
        await ctx.send("I'm not in a voice channel.")

@bot.command()
async def speak(ctx, *, text):
    if not ctx.voice_client:
        await ctx.send("I'm not in a voice channel. Use !join first.")
        return

    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        
        audio_data = io.BytesIO(response.content)
        
        ctx.voice_client.play(discord.FFmpegPCMAudio(audio_data, pipe=True))
        await ctx.send(f"Speaking: {text}")
    except Exception as e:
        print(f"Error in text_to_speech: {str(e)}")
        await ctx.send("Sorry, I couldn't generate the audio response.")

bot.run(os.getenv('DISCORD_TOKEN'))