# Audio Processing Bot

## How It Works

Based on the current implementation in `main.py`, the bot processes audio as follows:

1. **Initiation of Recording**:

   - Recording starts when a user issues the `!listen` command.
   - The bot immediately begins recording, regardless of whether there's audio input or not.

2. **Continuous Recording and Processing**:

   - Records audio in small chunks (0.1 seconds each) continuously.
   - Adds these audio chunks to a buffer.
   - After each chunk is added, checks for the end of speech using the `detect_speech_end` function.
   - If end of speech is detected, processes the buffer (transcription and response).
   - Clears the buffer and immediately continues listening for the next utterance.
   - This cycle repeats until the bot is stopped or disconnected.

3. **Speech End Detection**:

   - The `detect_speech_end` function:
     - Ensures there's at least 1.5 seconds of audio in the buffer.
     - Analyzes the last 1.5 seconds of audio (15 chunks of 0.1 seconds each).
     - Uses WebRTC's Voice Activity Detection (VAD) to check if the last 0.5 seconds (5 frames of 30ms each) are silent.

4. **Processing**:

   - If silence is detected (indicating the end of speech), the bot processes the entire buffer:
     - Combines all the audio chunks in the buffer.
     - Transcribes the combined audio using OpenAI's Whisper model.
     - Generates and sends a response if the transcription is not empty.

5. **Termination of Recording**:
   - Recording stops when:
     - A user issues the `!stop` command, or
     - An error occurs, or
     - The bot is disconnected from the voice channel.

## FAQ

### Q: How does the bot know when to start recording?

A: The bot starts recording as soon as the `!listen` command is issued. It doesn't wait for or detect the start of speech activity.

### Q: Does it automatically start recording again after processing speech?

A: Yes, after processing each chunk of speech (when silence is detected), the bot immediately continues listening for the next utterance without needing another command.

### Q: Does it wait to transcribe until it hears silence?

A: Yes, it waits for a short period of silence (0.5 seconds) before attempting to transcribe.

### Q: Does it listen for a set amount of time?

A: No, it listens continuously until stopped. It processes audio in chunks whenever it detects a pause in speech, but immediately resumes listening after processing.

## Approach

This approach aims for continuous interaction, allowing the bot to capture and respond to multiple utterances without needing repeated commands. It balances responsiveness with accuracy by processing speech in chunks separated by short silences. However, it may process silent periods or background noise between utterances, and users need to explicitly stop the bot when they're finished interacting.
