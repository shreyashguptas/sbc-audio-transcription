#!/usr/bin/env python3
"""
Interactive Faster-Whisper Transcription Configuration Tool
Test different configurations to find optimal performance for your setup
"""

import subprocess
import soundfile as sf
import numpy as np
from scipy import signal
from faster_whisper import WhisperModel
from simple_term_menu import TerminalMenu
import sys
import re
import os
import time

class TranscriptionConfig:
    """Configuration for transcription parameters"""

    def __init__(self):
        # Model settings
        self.model_size = 'base'
        self.compute_type = 'int8'
        self.cpu_threads = 0  # 0 = auto

        # Transcription quality
        self.beam_size = 5
        self.temperature = 0.0
        self.condition_on_previous_text = True

        # VAD settings
        self.vad_filter = True
        self.vad_threshold = 0.25
        self.vad_min_silence_ms = 1500

        # Audio processing
        self.chunk_duration = 7
        self.overlap_duration = 2
        self.gain = 30.0
        self.min_audio_energy = 0.0002

        # Constants
        self.min_words = 1
        self.overlap_words = 5
        self.max_context_chunks = 4

    def display_summary(self):
        """Display configuration summary"""
        print('')
        print('='*70)
        print('  CONFIGURATION SUMMARY')
        print('='*70)
        print('')
        print('MODEL SETTINGS:')
        print(f'  Model Size: {self.model_size}')
        print(f'  Compute Type: {self.compute_type}')
        print(f'  CPU Threads: {"auto" if self.cpu_threads == 0 else self.cpu_threads}')
        print('')
        print('TRANSCRIPTION QUALITY:')
        print(f'  Beam Size: {self.beam_size}')
        print(f'  Temperature: {self.temperature}')
        print(f'  Condition on Previous Text: {"Yes" if self.condition_on_previous_text else "No"}')
        print('')
        print('VAD SETTINGS:')
        print(f'  VAD Enabled: {"Yes" if self.vad_filter else "No"}')
        if self.vad_filter:
            print(f'  VAD Threshold: {self.vad_threshold}')
            print(f'  Min Silence Duration: {self.vad_min_silence_ms}ms')
        print('')
        print('AUDIO PROCESSING:')
        print(f'  Chunk Duration: {self.chunk_duration}s')
        print(f'  Overlap Duration: {self.overlap_duration}s')
        print(f'  Microphone Gain: {self.gain}x')
        print(f'  Min Audio Energy: {self.min_audio_energy}')
        print('='*70)
        print('')

def show_welcome():
    """Display welcome screen"""
    print('')
    print('='*70)
    print('  FASTER-WHISPER INTERACTIVE CONFIGURATION TOOL')
    print('  Test different settings to optimize your transcription performance')
    print('='*70)
    print('')

def menu_preset(config):
    """Show preset configuration menu"""
    options = [
        "Fastest (tiny, int8, beam=1, no VAD)",
        "Balanced (base, int8, beam=5, VAD on) [Current]",
        "Quality (small, int8, beam=5, VAD on)",
        "Custom (configure all options)"
    ]

    menu = TerminalMenu(
        options,
        title="Select Configuration Preset:",
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()

    if choice == 0:  # Fastest
        config.model_size = 'tiny'
        config.compute_type = 'int8'
        config.beam_size = 1
        config.vad_filter = False
        config.temperature = 0.0
        return False  # Skip custom menus
    elif choice == 1:  # Balanced (default)
        # Keep current defaults
        return False
    elif choice == 2:  # Quality
        config.model_size = 'small'
        config.compute_type = 'int8'
        config.beam_size = 5
        config.vad_filter = True
        return False
    else:  # Custom
        return True

def menu_model_size(config):
    """Model size selection menu"""
    options = [
        "tiny (fastest, least accurate)",
        "base (balanced) [Recommended for Pi 5]",
        "small (better quality, slower)",
        "medium (high quality, much slower)",
        "large-v3 (best quality, very slow)",
        "turbo (optimized for speed)"
    ]

    model_map = ['tiny', 'base', 'small', 'medium', 'large-v3', 'turbo']
    current_idx = model_map.index(config.model_size) if config.model_size in model_map else 1

    menu = TerminalMenu(
        options,
        title="Select Whisper Model Size:",
        cursor_index=current_idx,
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()
    config.model_size = model_map[choice]

def menu_compute_type(config):
    """Compute type selection menu"""
    options = [
        "int8 (fastest, best for CPU/Pi) [Recommended]",
        "int16 (slower, slightly better quality)",
        "float32 (slowest, most accurate)"
    ]

    compute_map = ['int8', 'int16', 'float32']
    current_idx = compute_map.index(config.compute_type) if config.compute_type in compute_map else 0

    menu = TerminalMenu(
        options,
        title="Select Compute Type:",
        cursor_index=current_idx,
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()
    config.compute_type = compute_map[choice]

def menu_beam_size(config):
    """Beam size selection menu"""
    options = [
        "1 (fastest, greedy search)",
        "3 (faster, good quality)",
        "5 (balanced) [Recommended]",
        "7 (slower, better quality)",
        "10 (slowest, best quality)"
    ]

    beam_map = [1, 3, 5, 7, 10]
    current_idx = beam_map.index(config.beam_size) if config.beam_size in beam_map else 2

    menu = TerminalMenu(
        options,
        title="Select Beam Size:",
        cursor_index=current_idx,
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()
    config.beam_size = beam_map[choice]

def menu_temperature(config):
    """Temperature selection menu"""
    options = [
        "0.0 (deterministic, no fallback) [Recommended]",
        "[0.0, 0.2] (fallback if transcription fails)"
    ]

    menu = TerminalMenu(
        options,
        title="Select Temperature Setting:",
        cursor_index=0,
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()
    config.temperature = 0.0 if choice == 0 else [0.0, 0.2]

def menu_vad(config):
    """VAD configuration menu"""
    options = ["Yes (filter silence) [Recommended]", "No (process all audio)"]

    menu = TerminalMenu(
        options,
        title="Enable Voice Activity Detection (VAD)?",
        cursor_index=0 if config.vad_filter else 1,
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()
    config.vad_filter = (choice == 0)

    if config.vad_filter:
        # VAD Threshold
        threshold_options = [
            "0.2 (very sensitive, catches quiet speech)",
            "0.25 (sensitive) [Current]",
            "0.3 (balanced)",
            "0.4 (moderate)",
            "0.5 (default)",
            "0.6 (strict, ignores quiet sounds)"
        ]
        threshold_map = [0.2, 0.25, 0.3, 0.4, 0.5, 0.6]

        menu = TerminalMenu(
            threshold_options,
            title="Select VAD Threshold:",
            cursor_index=1,
            menu_cursor="→ ",
            menu_cursor_style=("fg_cyan", "bold"),
            menu_highlight_style=("bg_cyan", "fg_black")
        )

        choice = menu.show()
        config.vad_threshold = threshold_map[choice]

        # Min Silence Duration
        silence_options = [
            "500ms (quick cutoff)",
            "1000ms (responsive)",
            "1500ms (balanced) [Current]",
            "2000ms (patient, default)",
            "2500ms (very patient)"
        ]
        silence_map = [500, 1000, 1500, 2000, 2500]

        menu = TerminalMenu(
            silence_options,
            title="Select Minimum Silence Duration:",
            cursor_index=2,
            menu_cursor="→ ",
            menu_cursor_style=("fg_cyan", "bold"),
            menu_highlight_style=("bg_cyan", "fg_black")
        )

        choice = menu.show()
        config.vad_min_silence_ms = silence_map[choice]

def menu_audio_processing(config):
    """Audio processing configuration menu"""
    # Chunk Duration
    chunk_options = [
        "3 seconds (low latency, less context)",
        "5 seconds (balanced)",
        "7 seconds (good context) [Current]",
        "10 seconds (more context)",
        "15 seconds (maximum context, high latency)"
    ]
    chunk_map = [3, 5, 7, 10, 15]

    menu = TerminalMenu(
        chunk_options,
        title="Select Chunk Duration:",
        cursor_index=2,
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()
    config.chunk_duration = chunk_map[choice]

    # Overlap Duration
    overlap_options = [
        "1 second (minimal overlap)",
        "2 seconds (balanced) [Current]",
        "3 seconds (maximum overlap)"
    ]
    overlap_map = [1, 2, 3]

    menu = TerminalMenu(
        overlap_options,
        title="Select Overlap Duration:",
        cursor_index=1,
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()
    config.overlap_duration = overlap_map[choice]

    # Microphone Gain
    gain_options = [
        "10x (low gain)",
        "20x (moderate gain)",
        "30x (balanced) [Current]",
        "40x (high gain)",
        "50x (maximum gain)"
    ]
    gain_map = [10.0, 20.0, 30.0, 40.0, 50.0]

    menu = TerminalMenu(
        gain_options,
        title="Select Microphone Gain:",
        cursor_index=2,
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()
    config.gain = gain_map[choice]

def menu_advanced(config):
    """Advanced settings menu"""
    options = [
        "Yes (configure CPU threads, energy threshold, etc.)",
        "No (use defaults) [Recommended]"
    ]

    menu = TerminalMenu(
        options,
        title="Configure Advanced Settings?",
        cursor_index=1,
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()

    if choice == 0:
        # CPU Threads
        thread_options = [
            "Auto (let system decide) [Recommended]",
            "2 threads",
            "4 threads"
        ]
        thread_map = [0, 2, 4]

        menu = TerminalMenu(
            thread_options,
            title="Select CPU Threads:",
            cursor_index=0,
            menu_cursor="→ ",
            menu_cursor_style=("fg_cyan", "bold"),
            menu_highlight_style=("bg_cyan", "fg_black")
        )

        choice = menu.show()
        config.cpu_threads = thread_map[choice]

        # Min Audio Energy
        energy_options = [
            "0.0001 (very sensitive)",
            "0.0002 (balanced) [Current]",
            "0.0005 (moderate)",
            "0.001 (strict)"
        ]
        energy_map = [0.0001, 0.0002, 0.0005, 0.001]

        menu = TerminalMenu(
            energy_options,
            title="Select Minimum Audio Energy Threshold:",
            cursor_index=1,
            menu_cursor="→ ",
            menu_cursor_style=("fg_cyan", "bold"),
            menu_highlight_style=("bg_cyan", "fg_black")
        )

        choice = menu.show()
        config.min_audio_energy = energy_map[choice]

        # Condition on Previous Text
        context_options = [
            "Yes (use context from previous chunks) [Recommended]",
            "No (each chunk independent)"
        ]

        menu = TerminalMenu(
            context_options,
            title="Condition on Previous Text?",
            cursor_index=0 if config.condition_on_previous_text else 1,
            menu_cursor="→ ",
            menu_cursor_style=("fg_cyan", "bold"),
            menu_highlight_style=("bg_cyan", "fg_black")
        )

        choice = menu.show()
        config.condition_on_previous_text = (choice == 0)

def configure_transcription():
    """Main configuration workflow"""
    show_welcome()

    config = TranscriptionConfig()

    # Show preset menu
    custom = menu_preset(config)

    if custom:
        # Model settings
        menu_model_size(config)
        menu_compute_type(config)

        # Transcription quality
        menu_beam_size(config)
        menu_temperature(config)

        # VAD settings
        menu_vad(config)

        # Audio processing
        menu_audio_processing(config)

        # Advanced settings
        menu_advanced(config)

    # Show summary
    config.display_summary()

    # Confirm
    options = ["Yes, start transcription", "No, reconfigure", "Cancel"]
    menu = TerminalMenu(
        options,
        title="Start transcription with these settings?",
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()

    if choice == 0:
        return config
    elif choice == 1:
        return configure_transcription()  # Recursive call to reconfigure
    else:
        print("\nConfiguration cancelled.")
        sys.exit(0)

# Utility functions (from original code)

def is_repetition(new_text, previous_text, threshold=0.7):
    """Check if new text is mostly a repetition of previous text"""
    if not previous_text or not new_text:
        return False

    new_words = new_text.lower().split()
    prev_words = previous_text.lower().split()

    if len(new_words) < 3:
        return False

    check_length = min(len(prev_words), 10)
    prev_end = ' '.join(prev_words[-check_length:])

    matching_words = sum(1 for word in new_words if word in prev_end.split())
    similarity = matching_words / len(new_words) if new_words else 0

    return similarity > threshold

def remove_overlap(new_text, previous_words, overlap_words):
    """Remove overlapping words from the beginning of new_text"""
    if not previous_words or not new_text:
        return new_text

    new_words = new_text.split()
    max_check = min(len(new_words), len(previous_words), overlap_words)

    overlap_count = 0
    for i in range(max_check, 0, -1):
        if previous_words[-i:] == new_words[:i]:
            overlap_count = i
            break

    if overlap_count > 0:
        new_words = new_words[overlap_count:]

    return ' '.join(new_words)

def has_sufficient_audio(audio_data, threshold):
    """Check if audio has sufficient energy to likely contain speech"""
    rms = np.sqrt(np.mean(audio_data**2))
    max_amp = np.max(np.abs(audio_data))
    return rms > threshold or max_amp > threshold * 3

def normalize_whitespace(text):
    """Normalize whitespace in text"""
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text

def run_transcription(config):
    """Run transcription with configured parameters"""

    print('')
    print('='*70)
    print('  LOADING MODEL')
    print('='*70)
    print('')
    print(f'Loading {config.model_size} model with {config.compute_type} compute type...')

    # Load model with configured parameters
    model = WhisperModel(
        config.model_size,
        device='cpu',
        compute_type=config.compute_type,
        cpu_threads=config.cpu_threads
    )

    print('')
    print('='*70)
    print('  TRANSCRIPTION ACTIVE')
    print('='*70)
    print('')
    print('Ready! Speak naturally - transcription will flow continuously.')
    print('Press Ctrl+C to stop')
    print('')
    print('-' * 70)
    print('')

    # Context management
    context_buffer = []
    segment_num = 0
    first_output = True
    last_text = ""
    last_words = []

    # Performance tracking
    start_time = time.time()
    total_audio_duration = 0
    total_words = 0

    try:
        while True:
            segment_num += 1

            # Record
            audio_file = f'/tmp/seg_{segment_num}.wav'

            result = subprocess.run(
                ['arecord', '-D', 'plughw:0,0', '-f', 'S16_LE',
                 '-r', '48000', '-c', '2', '-d', str(config.chunk_duration), audio_file],
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
            audio = np.mean(audio, axis=1)
            audio = signal.resample(audio, int(len(audio) * 16000 / sr))

            total_audio_duration += config.chunk_duration

            # Check audio energy BEFORE applying gain
            if not has_sufficient_audio(audio, config.min_audio_energy):
                try:
                    os.remove(audio_file)
                except:
                    pass
                continue

            audio = audio * config.gain
            audio = np.clip(audio, -1.0, 1.0)

            proc_file = f'/tmp/proc_{segment_num}.wav'
            sf.write(proc_file, audio, 16000)

            # Transcribe with configured parameters
            transcribe_params = {
                'language': 'en',
                'beam_size': config.beam_size,
                'temperature': config.temperature,
                'condition_on_previous_text': config.condition_on_previous_text
            }

            if config.vad_filter:
                transcribe_params['vad_filter'] = True
                transcribe_params['vad_parameters'] = dict(
                    min_silence_duration_ms=config.vad_min_silence_ms,
                    threshold=config.vad_threshold
                )

            segments, info = model.transcribe(proc_file, **transcribe_params)

            text = ' '.join([s.text for s in segments]).strip()
            text = normalize_whitespace(text)

            # Validation checks
            if text:
                word_count = len(text.split())

                if word_count < config.min_words:
                    try:
                        os.remove(audio_file)
                        os.remove(proc_file)
                    except:
                        pass
                    continue

                if is_repetition(text, last_text):
                    try:
                        os.remove(audio_file)
                        os.remove(proc_file)
                    except:
                        pass
                    continue

                deduplicated_text = remove_overlap(text, last_words, config.overlap_words)

                if deduplicated_text.strip():
                    context_buffer.append(text)
                    if len(context_buffer) > config.max_context_chunks:
                        context_buffer.pop(0)

                    # Progressive display
                    if not first_output:
                        print(' ' + deduplicated_text, end='', flush=True)
                    else:
                        print(deduplicated_text, end='', flush=True)
                        first_output = False

                    last_text = text
                    last_words = text.split()
                    total_words += len(deduplicated_text.split())

            # Cleanup
            try:
                os.remove(audio_file)
                os.remove(proc_file)
            except:
                pass

    except KeyboardInterrupt:
        elapsed_time = time.time() - start_time

        print('')
        print('')
        print('='*70)
        print('  PERFORMANCE STATISTICS')
        print('='*70)
        print('')
        print(f'Configuration: {config.model_size} model, {config.compute_type}, beam={config.beam_size}')
        print(f'Total Runtime: {elapsed_time:.1f}s')
        print(f'Total Audio Processed: {total_audio_duration:.1f}s')
        print(f'Total Words Transcribed: {total_words}')
        if total_audio_duration > 0:
            speed_factor = total_audio_duration / elapsed_time
            print(f'Speed Factor: {speed_factor:.2f}x real-time')
        print('')
        print('='*70)
        print('Transcription stopped')
        print('='*70)
        sys.exit(0)

def main():
    """Main entry point"""
    try:
        config = configure_transcription()
        run_transcription(config)
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)

if __name__ == "__main__":
    main()
