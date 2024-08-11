import asyncio
import discord
from discord.ext import commands
from discord.sinks import WaveSink
import pvporcupine
from gtts import gTTS
from openai import OpenAI
import tempfile
import numpy as np
import os
import wave
from dotenv import load_dotenv
import logging
import struct
import time

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

# Initialize Porcupine wake word detector
try:
    porcupine = pvporcupine.create(
        access_key=os.getenv('PICOVOICE_ACCESS_KEY'),
        keywords=["porcupine"],
        sensitivities=[0.5]
    )
    logger.info(f"Porcupine initialized with wake word 'porcupine' and sensitivity 0.5")
except Exception as e:
    logger.error(f"Failed to initialize Porcupine: {e}")
    porcupine = None

class VoiceState:
    def __init__(self):
        self.is_listening = False
        self.audio_queue = asyncio.Queue()

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
        return await ctx.send("I'm already listening for the wake word.")

    voice_state.is_listening = True
    await ctx.send("I'm listening for the wake word 'Porcupine'.")
    logger.info("Started listening for wake word")
    await process_audio(ctx, voice_state)

async def process_audio(ctx, voice_state):
    logger.info("Started processing audio")
    
    if porcupine is None:
        await ctx.send("Error: Porcupine wake word detection is not available.")
        return

    try:
        audio_sink = discord.sinks.WaveSink()
        ctx.voice_client.start_recording(audio_sink, on_recording_finished, ctx.channel)

        buffer = b''
        frame_count = 0
        empty_chunk_count = 0
        last_audio_time = time.time()

        while voice_state.is_listening:
            if not ctx.voice_client or not ctx.voice_client.is_connected():
                logger.warning("Voice client disconnected")
                break

            current_time = time.time()
            if current_time - last_audio_time > 10:  # Log every 10 seconds
                logger.info(f"Waiting for audio... (Empty chunks: {empty_chunk_count})")
                last_audio_time = current_time

            # Process available audio data
            audio_data = audio_sink.get_all_audio()
            logger.debug(f"Received audio data: {len(audio_data)} chunks")  # Add this line
            if not audio_data:
                empty_chunk_count += 1
                if empty_chunk_count % 1000 == 0:
                    logger.debug(f"No audio data received (count: {empty_chunk_count})")
                await asyncio.sleep(0.01)
                continue

            for audio in audio_data:
                chunk = audio.read(porcupine.frame_length * 2)
                if not chunk:
                    continue
                
                logger.debug(f"Received audio chunk of size {len(chunk)}")
                empty_chunk_count = 0  # Reset the counter when we receive audio
                
                # ... rest of the function
                
                buffer += chunk
                while len(buffer) >= porcupine.frame_length * 2:
                    frame = buffer[:porcupine.frame_length * 2]
                    buffer = buffer[porcupine.frame_length * 2:]

                    pcm = np.frombuffer(frame, dtype=np.int16)
                    wake_word_index = porcupine.process(pcm)
                    
                    frame_count += 1
                    if frame_count % 100 == 0:  # Log every 100 frames
                        logger.debug(f"Processed {frame_count} frames. Last wake_word_index: {wake_word_index}")
                        logger.debug(f"Wake word index: {wake_word_index}")
                    
                    if wake_word_index >= 0:
                        logger.info("Wake word detected!")
                        await ctx.send("Wake word detected. Listening for your message...")
                        await process_user_input(ctx, voice_state)
                        return

            await asyncio.sleep(0.01)
    except Exception as e:
        logger.error(f"Error processing audio: {e}", exc_info=True)
    finally:
        ctx.voice_client.stop_recording()
        voice_state.is_listening = False
        logger.info(f"Stopped listening for wake word. Processed {frame_count} frames total.")

async def on_recording_finished(sink, channel, *args):
    logger.info("Recording finished")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        del voice_states[ctx.guild.id]
        await ctx.send('Left the voice channel')
        logger.info('Left the voice channel')
    else:
        await ctx.send("I'm not in a voice channel.")

async def process_user_input(ctx, voice_state):
    logger.info("Started processing user input")
    
    # Create a new sink for user input
    user_input_sink = discord.sinks.WaveSink()
    
    # Start recording user input
    ctx.voice_client.start_recording(
        user_input_sink,
        lambda *args: asyncio.create_task(process_user_audio(ctx, user_input_sink, *args)),
        ctx.channel
    )
    
    # Wait for a short duration to capture user input (adjust as needed)
    await asyncio.sleep(5)
    
    # Stop recording
    ctx.voice_client.stop_recording()

async def process_user_audio(ctx, sink, *args):
    for user_id, audio in sink.audio_data.items():
        if user_id == ctx.author.id:  # Only process audio from the command invoker
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
                temp_audio.write(audio.file.read())

            try:
                # Transcribe audio using OpenAI's Whisper model
                with open(temp_audio.name, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                
                user_input = transcript.text
                logger.info(f"Transcribed user input: {user_input}")
                await ctx.send(f"You said: {user_input}")
                response = await generate_ai_response(user_input)
                await send_audio_response(ctx, response)
            except Exception as e:
                logger.error(f"Error processing speech: {e}")
                await ctx.send(f"Sorry, there was an error processing your speech: {str(e)}")
            finally:
                os.unlink(temp_audio.name)

    # Restart listening for wake word
    voice_state = VoiceState()
    voice_state.is_listening = True
    asyncio.create_task(process_audio(ctx, voice_state))

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
        tts = gTTS(text)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
            tts.save(fp.name)
            ctx.voice_client.play(discord.FFmpegPCMAudio(fp.name), after=lambda e: os.unlink(fp.name))
        logger.info("Sent audio response")
    except Exception as e:
        logger.error(f"Error sending audio response: {e}")
        await ctx.send("Sorry, I couldn't send an audio response. Here's the text: " + text)

bot.run(os.getenv('DISCORD_TOKEN'))