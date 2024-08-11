import asyncio
import discord
from discord.ext import commands
import speech_recognition as sr
from openai import OpenAI
import tempfile
import os
from dotenv import load_dotenv
import logging
from pydub import AudioSegment
import io
import struct 
import wave

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize speech recognizer
recognizer = sr.Recognizer()

class VoiceState:
    def __init__(self):
        self.is_listening = False

voice_states = {}

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name}')

@bot.command()
async def join(ctx):
    if ctx.author.voice is None:
        return await ctx.send("You are not connected to a voice channel.")
    
    channel = ctx.author.voice.channel
    if ctx.voice_client is not None:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()
    
    await ctx.send(f"Joined {channel.name}")
    logger.info(f"Joined voice channel: {channel.name}")

@bot.command()
async def listen(ctx):
    if ctx.voice_client is None:
        return await ctx.send("I'm not in a voice channel. Use !join first.")

    voice_state = voice_states.get(ctx.guild.id)
    if voice_state is None:
        voice_state = VoiceState()
        voice_states[ctx.guild.id] = voice_state

    if voice_state.is_listening:
        return await ctx.send("I'm already listening.")

    voice_state.is_listening = True
    await ctx.send("I'm listening. Speak naturally, and I'll respond.")
    logger.info("Started listening")
    await process_audio(ctx, voice_state)

async def process_audio(ctx, voice_state):
    logger.info("Started processing audio")
    
    try:
        while voice_state.is_listening:
            if not ctx.voice_client or not ctx.voice_client.is_connected():
                logger.warning("Voice client disconnected")
                break

            # Record audio in small chunks (e.g., 2 seconds)
            audio_data = await record_audio(ctx.voice_client, duration=2)
            
            if audio_data:
                # Process the audio chunk
                await process_audio_chunk(ctx, audio_data)

            await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Error processing audio: {e}", exc_info=True)
    finally:
        voice_state.is_listening = False
        logger.info("Stopped listening")

async def record_audio(voice_client, duration):
    if not voice_client.is_connected():
        return None

    audio_sink = discord.sinks.WaveSink()
    voice_client.start_recording(audio_sink, on_recording_finished, None)
    await asyncio.sleep(duration)
    voice_client.stop_recording()
    
    # Get the recorded audio data
    for user_id, audio in audio_sink.audio_data.items():
        return audio.file.getvalue()
    
    return None

async def process_audio_chunk(ctx, audio_data):
    try:
        # Convert raw PCM to 16-bit integers
        pcm_data = struct.unpack('h' * (len(audio_data) // 2), audio_data)
        
        # Create a temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            with wave.open(temp_audio.name, 'wb') as wf:
                wf.setnchannels(2)  # Stereo
                wf.setsampwidth(2)  # 2 bytes per sample
                wf.setframerate(48000)  # 48 kHz (Discord's audio rate)
                wf.writeframes(struct.pack('h' * len(pcm_data), *pcm_data))
        
        # Transcribe audio using OpenAI's Whisper model
        with open(temp_audio.name, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        
        user_input = transcript.text
        if user_input.strip():  # Only process non-empty transcriptions
            logger.info(f"Transcribed user input: {user_input}")
            await ctx.send(f"You said: {user_input}")
            response = await generate_ai_response(user_input)
            await send_audio_response(ctx, response)
    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}", exc_info=True)
    finally:
        if 'temp_audio' in locals():
            os.unlink(temp_audio.name)

async def on_recording_finished(sink, channel, *args):
    # This function is called when recording is finished, but we don't need to do anything here
    pass

async def generate_ai_response(user_input):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_input}
            ]
        )
        ai_response = response.choices[0].message.content
        logger.info(f"Generated AI response: {ai_response}")
        return ai_response
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return "Sorry, I couldn't generate a response at this time."

async def send_audio_response(ctx, text):
    try:
        audio_response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        
        # Convert audio response to a format Discord can play
        audio_segment = AudioSegment.from_mp3(io.BytesIO(audio_response.content))
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as fp:
            audio_segment.export(fp.name, format="wav")
            ctx.voice_client.play(discord.FFmpegPCMAudio(fp.name), after=lambda e: os.unlink(fp.name))
        logger.info("Sent audio response")
    except Exception as e:
        logger.error(f"Error sending audio response: {e}")
        await ctx.send("Sorry, I couldn't send an audio response. Here's the text: " + text)

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        if ctx.guild.id in voice_states:
            del voice_states[ctx.guild.id]
        await ctx.send('Left the voice channel')
        logger.info('Left the voice channel')
    else:
        await ctx.send("I'm not in a voice channel.")

bot.run(os.getenv('DISCORD_TOKEN'))