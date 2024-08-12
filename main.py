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
from scipy.io import wavfile
import webrtcvad
import numpy as np
from concurrent.futures import ThreadPoolExecutor

thread_pool = ThreadPoolExecutor(max_workers=3)

# # Set up logging
logging.basicConfig()
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
        self.buffer = []
        self.last_speech_time = 0
        self.is_processing = False
        self.vad = webrtcvad.Vad(3)
        self.stop_requested = False

voice_states = {}

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
    voice_state.stop_requested = False  # Reset stop flag
    await ctx.send("I'm listening. Speak naturally, and I'll respond. Use !stop to stop listening.")
    # logger.info("Started listening")
    await process_audio(ctx, voice_state)

@bot.command()
async def stop(ctx):
    voice_state = voice_states.get(ctx.guild.id)
    if voice_state and voice_state.is_listening:
        voice_state.stop_requested = True
        await ctx.send("Stopping listening...")
    else:
        await ctx.send("I'm not currently listening.")

async def process_audio(ctx, voice_state):
    # logger.info("Started processing audio")
    try:
        while voice_state.is_listening and not voice_state.stop_requested:
            if not ctx.voice_client or not ctx.voice_client.is_connected():
                # logger.warning("Voice client disconnected")
                break
            audio_data = await record_audio(ctx.voice_client, duration=0.05)  
            
            if audio_data:
                voice_state.buffer.append(audio_data)
                if len(voice_state.buffer) > 20:  
                    voice_state.buffer.pop(0)
                
                if await detect_speech_end(voice_state):
                    voice_state.is_processing = True
                    await process_buffer(ctx, voice_state)
                    voice_state.is_processing = False

            await asyncio.sleep(0.02) 
            
    except Exception as e:
        logger.error(f"Error processing audio: {e}", exc_info=True)
    finally:
        voice_state.is_listening = False
        voice_state.stop_requested = False
        
        await ctx.send("Stopped listening.")

async def detect_speech_end(voice_state):
    if len(voice_state.buffer) < 10:  
        return False

    recent_audio = b''.join(voice_state.buffer[-10:])
    audio_np = np.frombuffer(recent_audio, dtype=np.int16)

    frame_duration = 20  # Reduce to 20ms frames
    frame_size = int(48000 * frame_duration / 1000)
    frames = [audio_np[i:i+frame_size] for i in range(0, len(audio_np), frame_size)]

    is_speech = [voice_state.vad.is_speech(frame.tobytes(), 48000) for frame in frames[-3:]]  # Check last 60ms
    
    return not any(is_speech)

async def process_buffer(ctx, voice_state):
    if not voice_state.buffer:
        return

    combined_audio = b''.join(voice_state.buffer)
    voice_state.buffer.clear()

    await process_audio_chunk(ctx, combined_audio)

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
            # logger.info(f"Transcribed user input: {user_input}")
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
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a playful friend in a discord voice channel. Have fun, do not be vulgar, but feel free to poke fun and be sarcastic. "},
                {"role": "user", "content": user_input}
            ]
        )
        ai_response = response.choices[0].message.content
        # logger.info(f"Generated AI response: {ai_response}")
        return ai_response
    except Exception as e:
        # logger.error(f"Error generating AI response: {e}")
        return "Sorry, I couldn't generate a response at this time."

async def send_audio_response(ctx, text):
    try:
        response = await asyncio.to_thread(client.audio.speech.create,
            model="tts-1",
            voice="shimmer",
            input=text
        )

        # Stream directly to Discord without saving to a file
        audio_source = discord.FFmpegPCMAudio(io.BytesIO(response.content), pipe=True)
        ctx.voice_client.play(audio_source)
        
     #   logger.info("Sent streaming audio response")
    except Exception as e:
        # logger.error(f"Error sending audio response: {e}")
        await ctx.send("Sorry, I couldn't send an audio response. Here's the text: " + text)

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        if ctx.guild.id in voice_states:
            del voice_states[ctx.guild.id]
        await ctx.send('Left the voice channel')
        # logger.info('Left the voice channel')
    else:
        await ctx.send("I'm not in a voice channel.")

bot.run(os.getenv('DISCORD_TOKEN'))