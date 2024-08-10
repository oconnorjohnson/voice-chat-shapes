import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from openai import OpenAI
import io
import speech_recognition as sr
import tempfile
import asyncio
import wave
import struct
import logging

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

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

class SilentSource(discord.AudioSource):
    def read(self):
        return b'\x00' * 3840  # 20ms of silence

class RecordingSource(discord.AudioSource):
    def __init__(self):
        self.buffer = io.BytesIO()

    def read(self):
        return b'\x00' * 3840  # 20ms of silence

    def write(self, data):
        self.buffer.write(data)
class SilentFFmpegPCMAudio(discord.FFmpegPCMAudio):
    def read(self):
        ret = super().read()
        if ret is None:
            return b'\x00' * 3840
        return ret

class SilentSource(discord.AudioSource):
    def read(self):
        return b'\x00' * 3840  # 20ms of silence

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

    # Create a buffer to store audio data
    audio_buffer = io.BytesIO()
    
    # Define a callback to collect audio packets
    original_send_audio_packet = vc.send_audio_packet
    def audio_callback(data):
        logger.debug(f"Received audio packet of length {len(data)} bytes")
        audio_buffer.write(data)
        original_send_audio_packet(data)

    # Start collecting audio
    vc.send_audio_packet = audio_callback

    # Listen for 5 seconds
    await asyncio.sleep(5)

    # Stop collecting audio
    vc.send_audio_packet = original_send_audio_packet

    # Process the collected audio
    audio_data = audio_buffer.getvalue()
    logger.debug(f"Collected {len(audio_data)} bytes of audio data")
    
    # Convert the raw PCM data to WAV format
    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(2)  # Stereo
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(48000)  # Discord uses 48kHz
            wav_file.writeframes(audio_data)
        wav_data = wav_buffer.getvalue()

    # Save the WAV data to a temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_file.write(wav_data)
        temp_file_path = temp_file.name

    logger.debug(f"Saved audio to temporary file: {temp_file_path}")

    # Process the audio
    await process_audio(ctx, temp_file_path)

    # Clean up
    if vc.is_connected():
        await vc.disconnect()

    # Remove the temporary WAV file
    import os
    os.remove(temp_file_path)

async def process_audio(ctx, audio_file_path):
    # Transcribe the audio
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_file_path) as source:
        audio = recognizer.record(source)
    
    logger.debug(f"Audio file loaded, duration: {len(audio.frame_data) / audio.sample_rate} seconds")
    logger.debug(f"Audio file size: {os.path.getsize(audio_file_path)} bytes")

    try:
        transcript = recognizer.recognize_google(audio)
        logger.debug(f"Transcription successful: {transcript}")
    except sr.UnknownValueError:
        logger.error("Speech recognition could not understand audio")
        await ctx.send("Sorry, I couldn't understand the audio. Please try speaking more clearly or check your microphone.")
        return
    except sr.RequestError as e:
        logger.error(f"Could not request results from Google Speech Recognition service; {e}")
        await ctx.send("Sorry, there was an error processing the audio.")
        return

    # Generate a response using GPT
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    chat_completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": transcript}]
    )
    response_text = chat_completion.choices[0].message.content

    await ctx.send(f"You said: {transcript}\nMy response: {response_text}")
    
async def on_recording_finished(ctx, sink):
    # Get the recorded audio
    recorded_users = [
        (user_id, audio)
        for user_id, audio in sink.audio_data.items()
    ]
    
    if not recorded_users:
        await ctx.send("No audio was recorded.")
        return

    user_id, audio = recorded_users[0]

    # Save the audio to a temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        # Write audio data to the temporary file
        temp_file.write(audio.file.getvalue())
        temp_file_path = temp_file.name

    # Process the audio
    await process_audio(ctx, temp_file_path)



bot.run(os.getenv('DISCORD_TOKEN'))