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

## Dependencies and Libraries

This project relies on several Python libraries and packages. Here's a detailed breakdown of each dependency and its purpose:

1. **asyncio**

   - Purpose: Provides support for asynchronous programming.
   - Usage: Used throughout the bot for non-blocking operations and concurrent task management.

2. **discord.py**

   - Purpose: A Python wrapper for the Discord API.
   - Usage: Handles all interactions with Discord, including connecting to voice channels and sending messages.

3. **speech_recognition**

   - Purpose: Library for performing speech recognition.
   - Usage: Used to initialize the speech recognizer (though primary transcription is done via OpenAI).

4. **openai**

   - Purpose: Official Python client for the OpenAI API.
   - Usage: Used for speech-to-text (Whisper model), text generation (GPT model), and text-to-speech services.

5. **python-dotenv**

   - Purpose: Loads environment variables from a .env file.
   - Usage: Securely loads API keys and tokens without hardcoding them in the script.

6. **logging**

   - Purpose: Python's built-in logging module.
   - Usage: Provides comprehensive logging throughout the application for debugging and monitoring.

7. **pydub**

   - Purpose: Manipulates audio with a simple and easy interface.
   - Usage: Used for potential audio file manipulations (though not actively used in the current implementation).

8. **io**

   - Purpose: Core Python module for handling I/O operations.
   - Usage: Used for creating in-memory binary streams, particularly for audio data.

9. **struct**

   - Purpose: Performs conversions between Python values and C structs represented as Python bytes objects.
   - Usage: Used for packing and unpacking binary data, particularly in audio processing.

10. **wave**

    - Purpose: Provides a convenient interface to the WAV sound format.
    - Usage: Used for reading and writing WAV files in audio processing.

11. **scipy**

    - Purpose: Library for scientific computing in Python.
    - Usage: The `scipy.io.wavfile` module is imported for potential WAV file operations (though not actively used in the current implementation).

12. **webrtcvad**

    - Purpose: Python interface to the WebRTC Voice Activity Detector.
    - Usage: Used for detecting speech in audio streams, particularly for determining when a user has finished speaking.

13. **numpy**

    - Purpose: Fundamental package for scientific computing in Python.
    - Usage: Used for efficient operations on arrays, particularly in audio processing and speech detection.

14. **tempfile**

    - Purpose: Generates temporary files and directories.
    - Usage: Used for creating temporary files during audio processing.

15. **os**

    - Purpose: Provides a way of using operating system dependent functionality.
    - Usage: Used for file and path operations, particularly in handling temporary files.

16. **concurrent.futures**
    - Purpose: Provides a high-level interface for asynchronously executing callables.
    - Usage: The ThreadPoolExecutor is used for running CPU-bound tasks asynchronously.
