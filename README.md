# Audio Processing Bot

## How It Works

Based on the current implementation in `main.py`, the bot processes audio as follows:

1. **Continuous Recording**:

   - Records audio in small chunks (0.1 seconds each) while listening.
   - Adds these audio chunks to a buffer.

2. **Speech End Detection**:

   - After each chunk is added, checks for the end of speech using the `detect_speech_end` function.
   - The `detect_speech_end` function:
     - Ensures there's at least 1.5 seconds of audio in the buffer.
     - Analyzes the last 1.5 seconds of audio (15 chunks of 0.1 seconds each).
     - Uses WebRTC's Voice Activity Detection (VAD) to check if the last 0.5 seconds (5 frames of 30ms each) are silent.

3. **Processing**:
   - If silence is detected (indicating the end of speech), the bot processes the entire buffer:
     - Combines all the audio chunks in the buffer.
     - Transcribes the combined audio using OpenAI's Whisper model.
     - Generates and sends a response if the transcription is not empty.
   - The buffer is then cleared, and the process starts over.

## FAQ

### Q: Does it wait to transcribe until it hears silence?

A: Yes, it waits for a short period of silence (0.5 seconds) before attempting to transcribe.

### Q: Does it listen for a set amount of time?

A: Not exactly. It listens continuously but processes the audio in chunks whenever it detects a pause in speech. The minimum amount of audio it will process is 1.5 seconds, but there's no upper limit - it will keep adding to the buffer until it detects silence.

## Approach

This approach aims to balance responsiveness with accuracy, allowing the bot to capture complete sentences or thoughts before processing them, while also avoiding long delays in response.
