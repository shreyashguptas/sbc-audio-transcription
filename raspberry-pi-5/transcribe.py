#!/usr/bin/env python3
"""
Continuous context-aware transcription with overlapping chunks
Captures all words including trailing speech using smart deduplication
"""

import subprocess
import soundfile as sf
import numpy as np
from scipy import signal
from faster_whisper import WhisperModel
import sys
import re
import os

print('')
print('='*60)
print('  CONTINUOUS VOICE TRANSCRIPTION')
print('  (Overlapping chunks - captures all words)')
print('='*60)
print('')

# Load model
print('Loading model...')
model = WhisperModel('base', device='cpu', compute_type='int8')

print('')
print('Ready! Speak naturally - transcription will flow continuously.')
print('Press Ctrl+C to stop')
print('')
print('-' * 60)
print('')

# Context management with overlapping chunks
context_buffer = []  # Store recent transcriptions for context
MAX_CONTEXT_CHUNKS = 4  # Keep last ~20-30 seconds of context
CHUNK_DURATION = 7  # INCREASED: Record 7-second chunks
OVERLAP_DURATION = 2  # 2-second overlap to catch trailing words
MIN_AUDIO_ENERGY = 0.0002  # Further lowered for trailing speech
MIN_WORDS = 1  # Allow single-word endings

segment_num = 0
first_output = True
last_text = ""
last_words = []  # Track last few words for deduplication
OVERLAP_WORDS = 5  # Number of words to check for overlap

def is_repetition(new_text, previous_text, threshold=0.7):
    """
    Check if new text is mostly a repetition of previous text
    Returns True if it's a repetition (should be skipped)
    """
    if not previous_text or not new_text:
        return False
    
    # Normalize for comparison
    new_words = new_text.lower().split()
    prev_words = previous_text.lower().split()
    
    if len(new_words) < 3:
        return False
    
    # Check if new text is just repeating the end of previous text
    check_length = min(len(prev_words), 10)
    prev_end = ' '.join(prev_words[-check_length:])
    
    # Simple similarity check
    matching_words = sum(1 for word in new_words if word in prev_end.split())
    similarity = matching_words / len(new_words) if new_words else 0
    
    return similarity > threshold

def remove_overlap(new_text, previous_words):
    """
    Remove overlapping words from the beginning of new_text
    that match the end of previous transcription
    """
    if not previous_words or not new_text:
        return new_text
    
    new_words = new_text.split()
    
    # Check how many words at the start of new match the end of previous
    max_check = min(len(new_words), len(previous_words), OVERLAP_WORDS)
    
    overlap_count = 0
    for i in range(max_check, 0, -1):
        # Check if last i words of previous match first i words of new
        if previous_words[-i:] == new_words[:i]:
            overlap_count = i
            break
    
    # Remove overlapping words
    if overlap_count > 0:
        new_words = new_words[overlap_count:]
    
    return ' '.join(new_words)

def has_sufficient_audio(audio_data, threshold=MIN_AUDIO_ENERGY):
    """
    Check if audio has sufficient energy to likely contain speech
    Very lenient to catch all speech including trailing words
    """
    rms = np.sqrt(np.mean(audio_data**2))
    max_amp = np.max(np.abs(audio_data))
    
    # Very lenient - accept if there's any reasonable signal
    return rms > threshold or max_amp > threshold * 3

def normalize_whitespace(text):
    """
    Normalize whitespace in text: remove extra spaces, normalize to single spaces
    """
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text

try:
    while True:
        segment_num += 1

        # Record
        audio_file = f'/tmp/seg_{segment_num}.wav'

        # Record audio with error checking
        result = subprocess.run(
            ['arecord', '-D', 'plughw:0,0', '-f', 'S16_LE',
             '-r', '48000', '-c', '2', '-d', str(CHUNK_DURATION), audio_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Check if recording succeeded
        if result.returncode != 0:
            print(f"\nError: Recording failed!")
            print(f"arecord error: {result.stderr}")
            print("\nTroubleshooting:")
            print("1. Check if microphones are wired correctly (see PINOUT.md)")
            print("2. Verify I2S is enabled: dtparam i2s")
            print("3. Test audio device: arecord -l")
            print("4. Try manual recording: arecord -D plughw:0,0 -f S16_LE -r 48000 -c 2 -d 3 test.wav")
            sys.exit(1)

        # Check if file exists and has content
        if not os.path.exists(audio_file):
            print(f"\nError: Audio file was not created: {audio_file}")
            print("The recording command succeeded but no file was created.")
            sys.exit(1)

        if os.path.getsize(audio_file) == 0:
            print(f"\nError: Audio file is empty: {audio_file}")
            print("Recording succeeded but no audio data was captured.")
            sys.exit(1)

        # Process audio
        try:
            audio, sr = sf.read(audio_file)
        except Exception as e:
            print(f"\nError reading audio file: {e}")
            print(f"File: {audio_file}")
            print(f"File size: {os.path.getsize(audio_file)} bytes")
            sys.exit(1)
        # Mix both LEFT and RIGHT channels for stereo audio capture
        audio = np.mean(audio, axis=1)  # Average both channels into mono
        audio = signal.resample(audio, int(len(audio) * 16000 / sr))
        
        # Check audio energy BEFORE applying gain
        # Very lenient to catch trailing words in overlapping chunks
        if not has_sufficient_audio(audio):
            # Skip transcription for silence
            try:
                os.remove(audio_file)
            except:
                pass
            continue
        
        audio = audio * 30.0  # 30x gain
        audio = np.clip(audio, -1.0, 1.0)

        proc_file = f'/tmp/proc_{segment_num}.wav'
        sf.write(proc_file, audio, 16000)

        # Transcribe with VERY RELAXED VAD to catch all speech
        segments, info = model.transcribe(
            proc_file,
            language='en',
            beam_size=5,
            vad_filter=True,  # Enable VAD to filter silence
            vad_parameters=dict(
                min_silence_duration_ms=1500,  # INCREASED: Wait 1.5s before cutting off
                threshold=0.25  # VERY LOW: Catch even quiet trailing speech
            ),
            temperature=0.0
        )

        text = ' '.join([s.text for s in segments]).strip()
        
        # Normalize whitespace to prevent extra spaces
        text = normalize_whitespace(text)

        # Validation checks
        if text:
            word_count = len(text.split())
            
            # Skip if too few words (likely noise)
            if word_count < MIN_WORDS:
                try:
                    os.remove(audio_file)
                    os.remove(proc_file)
                except:
                    pass
                continue
            
            # Skip if it's a repetition of the last transcription
            if is_repetition(text, last_text):
                # Detected repetition loop - skip this output
                try:
                    os.remove(audio_file)
                    os.remove(proc_file)
                except:
                    pass
                continue
            
            # Remove overlapping words from previous chunk
            deduplicated_text = remove_overlap(text, last_words)
            
            # If after deduplication we have content, display it
            if deduplicated_text.strip():
                # Add to context buffer (use full text for context)
                context_buffer.append(text)
                if len(context_buffer) > MAX_CONTEXT_CHUNKS:
                    context_buffer.pop(0)

                # Progressive display with normalized spacing
                if not first_output:
                    # Add exactly one space before new text
                    print(' ' + deduplicated_text, end='', flush=True)
                else:
                    print(deduplicated_text, end='', flush=True)
                    first_output = False
                
                # Update last text and last words for overlap detection
                last_text = text
                last_words = text.split()

        # Cleanup
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
