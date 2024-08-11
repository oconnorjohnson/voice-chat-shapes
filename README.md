# Audio Processing Bot

## How It Works

This Discord bot processes audio in real-time, transcribes speech, generates AI responses, and sends audio responses back to the voice channel. Here's a detailed breakdown of its functionality:

1. **Initialization and Setup**:

   - The bot uses Discord.py for Discord integration and OpenAI for AI services.
   - It initializes with custom intents for message content and voice states.
   - A ThreadPoolExecutor is set up for handling CPU-bound tasks.

   ```python
   thread_pool = ThreadPoolExecutor(max_workers=3)
   ```

2. **Voice Channel Interaction**:

   - Users can make the bot join a voice channel using the `!join` command.
   - The `!listen` command starts the audio processing loop.
   - The `!stop` command terminates the listening process.
   - The `!leave` command disconnects the bot from the voice channel.

3. **Audio Recording and Processing**:

   - The bot records audio in small chunks (50ms each) using Discord's voice client.

   ```python
   audio_data = await record_audio(ctx.voice_client, duration=0.05)
   ```

   - These chunks are added to a buffer in the `VoiceState` object, maintaining a 1-second rolling window.
   - The `detect_speech_end` function uses WebRTC's Voice Activity Detection (VAD) to check for silence.

   ```python
   async def detect_speech_end(voice_state):
       # ... (implementation details)
   ```

4. **Speech-to-Text Conversion**:

   - When silence is detected, the audio buffer is processed.
   - The audio is converted to a WAV format and transcribed using OpenAI's Whisper model.

   ```python
   transcript = client.audio.transcriptions.create(
       model="whisper-1",
       file=audio_file
   )
   ```

5. **AI Response Generation**:

   - The transcribed text is sent to OpenAI's chat completion API (GPT-4o-mini model).
   - The API generates a contextual response based on the input.

   ```python
   response = client.chat.completions.create(
       model="gpt-4o-mini",
       messages=[
           {"role": "system", "content": "You are a playful friend in a discord voice channel..."},
           {"role": "user", "content": user_input}
       ]
   )
   ```

6. **Text-to-Speech Conversion**:

   - The AI-generated text response is converted to speech using OpenAI's TTS API.

   ```python
   response = await asyncio.to_thread(client.audio.speech.create,
       model="tts-1",
       voice="shimmer",
       input=text
   )
   ```

7. **Audio Playback**:

   - The generated audio is streamed directly to the Discord voice channel without saving to a file.

   ```python
   audio_source = discord.FFmpegPCMAudio(io.BytesIO(response.content), pipe=True)
   ctx.voice_client.play(audio_source)
   ```

8. **Continuous Listening**:

   - After processing each utterance, the bot immediately resumes listening for the next one.
   - This cycle continues until the `!stop` command is issued or an error occurs.

9. **Error Handling and Logging**:
   - Comprehensive error handling and logging are implemented throughout the code.
   - Errors are caught, logged, and appropriate messages are sent to the Discord channel.

## Bot Commands

- `!join`: Joins the user's current voice channel.
- `!listen`: Starts the audio processing loop.
- `!stop`: Stops the audio processing loop.
- `!leave`: Disconnects from the voice channel.

## Key Components

### VoiceState Class

Manages the state of the bot's voice connection for each guild:

```python
python
class VoiceState:
def init(self):
   self.is_listening = False
   self.buffer = []
   self.last_speech_time = 0
   self.is_processing = False
   self.vad = webrtcvad.Vad(3)
   self.stop_requested = False
```

### Main Processing Functions

- `process_audio(ctx, voice_state)`: Main loop for audio processing.
- `detect_speech_end(voice_state)`: Detects end of speech using VAD.
- `process_buffer(ctx, voice_state)`: Processes the audio buffer when speech ends.
- `process_audio_chunk(ctx, audio_data)`: Handles transcription and response generation.
- `generate_ai_response(user_input)`: Generates AI response using OpenAI's API.
- `send_audio_response(ctx, text)`: Converts text to speech and plays it in the voice channel.

## Approach and Design Considerations

1. **Real-time Processing**: The bot processes audio in small chunks to maintain responsiveness.
2. **Speech Detection**: Uses WebRTC's VAD for efficient speech end detection.
3. **Asynchronous Operations**: Utilizes asyncio for non-blocking operations.
4. **Parallel Processing**: Uses ThreadPoolExecutor for CPU-bound tasks.
5. **Streaming Responses**: Audio responses are streamed directly to Discord for lower latency.
6. **Error Handling**: Comprehensive error catching and logging for reliability.
7. **Scalability**: Designed to handle multiple guild connections simultaneously.

## Limitations and Potential Improvements

- The bot currently processes one utterance at a time. Implementing conversation history could improve context understanding.
- Adding a queue system for multiple users in the same channel could enhance multi-user interaction.
- Implementing local models for transcription and text generation could reduce API dependencies and latency.

## FAQ

Q: How does the bot know when to start recording?
A: The bot starts recording as soon as the `!listen` command is issued.

Q: Does it automatically start recording again after processing speech?
A: Yes, it continuously listens and processes speech until stopped.

Q: Does it wait to transcribe until it hears silence?
A: Yes, it uses VAD to detect silence before processing the audio buffer.

Q: Does it listen for a set amount of time?
A: No, it listens continuously until the `!stop` command is issued or an error occurs.
