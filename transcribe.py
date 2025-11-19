#!/usr/bin/env python3
"""
Continuous context-aware transcription
Words appear progressively with conversation context for accuracy
"""

import subprocess
import soundfile as sf
import numpy as np
from scipy import signal
from faster_whisper import WhisperModel
import sys

print('')
print('='*60)
print('  CONTINUOUS VOICE TRANSCRIPTION')
print('  (Context-aware for accurate sentences)')
print('='*60)
print('')

# Load model
print('Loading model...')
model = WhisperModel('tiny', device='cpu', compute_type='int8')

print('')
print('Ready! Speak naturally - transcription will flow continuously.')
print('Press Ctrl+C to stop')
print('')
print('-' * 60)
print('')

# Context management
context_buffer = []  # Store recent transcriptions for context
MAX_CONTEXT_CHUNKS = 4  # Keep last ~20-30 seconds of context
CHUNK_DURATION = 5  # Record in 5-second chunks

segment_num = 0
first_output = True

try:
    while True:
        segment_num += 1

        # Record
        audio_file = f'/tmp/seg_{segment_num}.wav'

        # Silent recording (no progress messages to keep output clean)
        subprocess.run(
            ['arecord', '-D', 'plughw:0,0', '-f', 'S16_LE',
             '-r', '48000', '-c', '2', '-d', str(CHUNK_DURATION), audio_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Process audio
        audio, sr = sf.read(audio_file)
        audio = audio[:, 0]  # Use LEFT channel only
        audio = signal.resample(audio, int(len(audio) * 16000 / sr))
        audio = audio * 30.0  # 30x gain
        audio = np.clip(audio, -1.0, 1.0)

        proc_file = f'/tmp/proc_{segment_num}.wav'
        sf.write(proc_file, audio, 16000)

        # Build context from recent transcriptions
        # This helps Whisper understand the conversation flow
        context = ' '.join(context_buffer[-MAX_CONTEXT_CHUNKS:])

        # Transcribe with context for better accuracy
        segments, info = model.transcribe(
            proc_file,
            language='en',
            beam_size=5,
            vad_filter=False,
            temperature=0.0,
            initial_prompt=context if context else None  # Pass context to Whisper
        )

        text = ' '.join([s.text for s in segments]).strip()

        # Display transcription
        if text:
            # Add to context buffer
            context_buffer.append(text)
            if len(context_buffer) > MAX_CONTEXT_CHUNKS:
                context_buffer.pop(0)

            # Progressive display
            if not first_output:
                # Add space before new text for natural flow
                print(' ' + text, end='', flush=True)
            else:
                print(text, end='', flush=True)
                first_output = False

        # Cleanup
        import os
        try:
            os.remove(audio_file)
            os.remove(proc_file)
        except:
            pass

except KeyboardInterrupt:
    print('')
    print('')
    print('-' * 60)
    print('Transcription stopped')
    print('='*60)
    sys.exit(0)
