import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import tempfile
import logging
from openai import OpenAI
from gtts import gTTS

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

openai_api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=openai_api_key)

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
async def listen(ctx):
    if not ctx.author.voice:
        await ctx.send("You need to be in a voice channel to use this command.")
        return

    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        vc = await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)
        vc = ctx.voice_client
    else:
        vc = ctx.voice_client

    await ctx.send("I'm listening. Say something, and I'll respond when you're done.")

    # Start recording
    sink = discord.sinks.WaveSink()
    vc.start_recording(
        sink,
        once_done,
        ctx
    )

    # Record for 10 seconds
    await asyncio.sleep(10)

    # Stop recording
    vc.stop_recording()

async def once_done(sink: discord.sinks.WaveSink, ctx: commands.Context):
    for user_id, audio in sink.audio_data.items():
        raw_audio = audio.file.read()
        
        logger.debug(f"Raw audio data (first 100 bytes): {raw_audio[:100]}")
        logger.debug(f"Audio data length: {len(raw_audio)} bytes")

        # Calculate and log the duration of the recording
        bytes_per_second = 2 * 2 * 44100  # 16-bit PCM, 2 channels, 44.1 kHz
        duration_seconds = len(raw_audio) / bytes_per_second
        logger.debug(f"Audio duration: {duration_seconds:.2f} seconds")

        audio_path = tempfile.mktemp(suffix=".wav")
        with open(audio_path, 'wb') as f:
            f.write(raw_audio)

        await process_audio(ctx, audio_path)

async def process_audio(ctx, audio_file_path):
    try:
        # Transcribe audio using OpenAI Whisper
        with open(audio_file_path, "rb") as audio_file:
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        transcription_text = transcript_response.text

        if not transcription_text:
            raise ValueError("Received an empty transcription response.")

        logger.debug(f"Transcription: {transcription_text}")

        # Generate a response using GPT-4
        gpt_response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": transcription_text}
            ],
            max_tokens=150
        )

        # Access the response content correctly
        response_text = gpt_response.choices[0].message.content.strip()
        logger.debug(f"GPT-4 Response: {response_text}")

        # Convert response text to speech
        tts = gTTS(response_text)
        response_audio_path = tempfile.mktemp(suffix=".mp3")
        tts.save(response_audio_path)

        # Play the response audio in the voice channel
        vc = ctx.voice_client
        vc.play(discord.FFmpegPCMAudio(response_audio_path), after=lambda e: cleanup_after_playback(response_audio_path, e, ctx))

    except Exception as e:
        logger.error(f"An error occurred during audio processing: {e}")
        await ctx.send(f"An error occurred: {e}")

    finally:
        os.remove(audio_file_path)

def cleanup_after_playback(response_audio_path, e, ctx):
    if e:
        logger.error(f"Error during playback: {e}")
    os.remove(response_audio_path)
    if ctx.voice_client and ctx.voice_client.is_connected():
        ctx.voice_client.stop()
        asyncio.run_coroutine_threadsafe(ctx.voice_client.disconnect(), bot.loop)

bot.run(os.getenv('DISCORD_TOKEN'))