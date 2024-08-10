import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import tempfile
import logging
import openai
from gtts import gTTS

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(raw_audio)
            temp_file_path = temp_file.name

        logger.debug(f"Saved audio to temporary file: {temp_file_path}")
        logger.debug(f"Audio file size: {os.path.getsize(temp_file_path)} bytes")

        # Play back the recorded audio to verify its quality
        vc = ctx.voice_client
        try:
            vc.play(discord.FFmpegPCMAudio(temp_file_path), after=lambda e: logger.debug("Finished playing recorded audio"))
        except Exception as e:
            logger.error(f"Error playing audio: {e}")

        await process_audio(ctx, temp_file_path)

        os.unlink(temp_file_path)

async def process_audio(ctx, audio_file_path):
    try:
        # Transcribe audio using OpenAI Whisper
        with open(audio_file_path, "rb") as audio_file:
            transcript_response = openai.Audio.transcribe("whisper-1", audio_file)
            transcript = transcript_response["text"]
            logger.debug(f"Transcription: {transcript}")
            await ctx.send(f"Transcription: {transcript}")

        # Generate response using OpenAI GPT-4o
        response = openai.Completion.create(
            engine="gpt-4o",
            prompt=transcript,
            max_tokens=150
        )
        response_text = response.choices[0].text.strip()
        logger.debug(f"Response: {response_text}")

        # Convert response text to speech
        tts = gTTS(response_text)
        response_audio_path = tempfile.mktemp(suffix=".mp3")
        tts.save(response_audio_path)

        # Play the response audio in the voice channel
        vc = ctx.voice_client
        vc.play(discord.FFmpegPCMAudio(response_audio_path), after=lambda e: os.remove(response_audio_path))

    except Exception as e:
        logger.error(f"An error occurred during audio processing: {e}")
        await ctx.send(f"An error occurred: {e}")

bot.run(os.getenv('DISCORD_TOKEN'))