#!/usr/bin/env python3
"""
Interactive Hailo Whisper Transcription for Raspberry Pi 5 with Hailo-8L
Records audio and performs real-time transcription using hardware acceleration.
"""

import os
import sys
import time
import subprocess
import tempfile
import signal
import numpy as np
from simple_term_menu import TerminalMenu

# Add Hailo examples to path
hailo_path = os.path.expanduser("~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition")
if os.path.exists(hailo_path):
    sys.path.insert(0, hailo_path)

try:
    # Import Hailo modules
    from app.hailo_whisper_pipeline import HailoWhisperPipeline
    from common.audio_utils import load_audio, SAMPLE_RATE
    from common.preprocessing import preprocess, detect_first_speech
    from common.postprocessing import clean_transcription as postprocess_text
except ImportError as e:
    print(f"❌ Error importing Hailo modules: {e}")
    print("\nPlease ensure you've run setup.py in the Hailo repository:")
    print("  cd ~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition")
    print("  python3 setup.py")
    sys.exit(1)

# Helper functions
def apply_gain(audio, gain_db):
    """Apply gain to audio signal in decibels"""
    gain_linear = 10 ** (gain_db / 20)
    return audio * gain_linear

def improve_input_audio_quiet(audio, vad=True, low_audio_gain=True, vad_threshold=0.2, debug=False):
    """
    Improve input audio with optional VAD and auto-gain (quiet version).

    Parameters:
    - audio: Audio array
    - vad: Enable voice activity detection
    - low_audio_gain: Enable automatic gain control
    - vad_threshold: Energy threshold for VAD (0.0-1.0)
    - debug: Print debug information

    Returns:
    - audio: Processed audio
    - start_time: Timestamp where speech begins (or None)
    - gain_applied: Gain in dB that was applied (or 0)
    """
    audio_max = np.max(np.abs(audio))
    gain_applied = 0

    # Apply automatic gain control
    if low_audio_gain:
        if audio_max < 0.1:
            gain_applied = 20
            audio = apply_gain(audio, gain_db=20)
            if debug:
                print(f"  [DEBUG] Audio boosted by {gain_applied}dB: {audio_max:.4f} → {np.max(np.abs(audio)):.4f}", flush=True)
        elif audio_max < 0.2:
            gain_applied = 10
            audio = apply_gain(audio, gain_db=10)
            if debug:
                print(f"  [DEBUG] Audio boosted by {gain_applied}dB: {audio_max:.4f} → {np.max(np.abs(audio)):.4f}", flush=True)

    # Detect speech start time
    start_time = None
    if vad:
        start_time = detect_first_speech(audio, SAMPLE_RATE, threshold=vad_threshold, frame_duration=0.2)
        if debug:
            if start_time is not None:
                print(f"  [DEBUG] Speech detected at: {start_time:.2f}s", flush=True)
            else:
                print(f"  [DEBUG] No speech detected (processing full chunk)", flush=True)

    return audio, start_time, gain_applied

# Configuration
class Config:
    def __init__(self):
        # Hailo settings
        self.hw_arch = 'hailo8l'
        self.model_variant = 'base'  # 'tiny' for 10s chunks, 'base' for 5s chunks

        # Audio settings
        self.device = 'plughw:0,0'
        self.sample_rate = 48000
        self.channels = 2

        # Audio preprocessing
        self.enable_vad = True  # Voice Activity Detection
        self.enable_auto_gain = True  # Automatic gain control for quiet audio
        self.vad_threshold = 0.2  # Energy threshold for speech detection (0.0-1.0)
        self.chunk_overlap = 0.0  # Overlap for long audio files (keep 0.0 for real-time)

        # Debug settings
        self.debug_mode = False  # Enable detailed logging

        # Paths (h8l is the directory name for hailo8l)
        self.hef_dir = os.path.join(hailo_path, 'app', 'hefs', 'h8l')
        self.decoder_dir = os.path.join(hailo_path, 'app', 'decoder_assets')

    @property
    def chunk_duration(self):
        return 10 if self.model_variant == 'tiny' else 5

    def display_summary(self):
        """Display configuration summary"""
        print('')
        print('='*70)
        print('  CONFIGURATION SUMMARY')
        print('='*70)
        print('')
        print('HAILO SETTINGS:')
        print(f'  Model Variant: {self.model_variant}')
        print(f'  Hardware: {self.hw_arch} (Hailo-8L)')
        print(f'  Chunk Duration: {self.chunk_duration}s')
        print('')
        print('AUDIO SETTINGS:')
        print(f'  Device: {self.device}')
        print(f'  Sample Rate: {self.sample_rate} Hz')
        print(f'  Channels: {self.channels} (stereo)')
        print('')
        print('PREPROCESSING:')
        print(f'  Voice Activity Detection: {"Enabled" if self.enable_vad else "Disabled"}')
        print(f'  Auto Gain Control: {"Enabled" if self.enable_auto_gain else "Disabled"}')
        if self.enable_vad:
            print(f'  VAD Threshold: {self.vad_threshold}')
        print('')
        print('DEBUG MODE:', 'Enabled' if self.debug_mode else 'Disabled')
        print('='*70)
        print('')

# Global variable for clean shutdown
running = True
pipeline = None

class ContextTracker:
    """Track transcription context across chunks for visual continuity"""

    def __init__(self):
        self.incomplete_buffer = ""  # Text from previous chunk without terminal punctuation

    def process_transcription(self, text):
        """
        Process transcription text with context from previous chunks.

        Returns:
            tuple: (display_text, is_continuation)
                - display_text: Text to show (includes buffered context if any)
                - is_continuation: True if this chunk continues previous incomplete sentence
        """
        if not text:
            return "", False

        is_continuation = bool(self.incomplete_buffer)

        # Prepend incomplete buffer to current text
        if self.incomplete_buffer:
            full_text = self.incomplete_buffer + " " + text
        else:
            full_text = text

        # Check if current text ends with terminal punctuation
        terminal_punctuation = {'.', '!', '?'}
        has_terminal = text.strip() and text.strip()[-1] in terminal_punctuation

        if has_terminal:
            # Sentence is complete, clear buffer
            self.incomplete_buffer = ""
            display_text = full_text
        else:
            # Sentence is incomplete, buffer for next chunk
            self.incomplete_buffer = full_text
            display_text = full_text + "..."  # Visual indicator of incompleteness

        return display_text, is_continuation

    def reset(self):
        """Clear the context buffer"""
        self.incomplete_buffer = ""

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global running
    print("\n\nStopping transcription...")
    running = False
    if pipeline:
        pipeline.stop()
    sys.exit(0)

def record_audio(duration=10, device='plughw:0,0', sample_rate=48000, channels=2):
    """Record audio from microphone and save to temp file"""
    # Create temp file for audio
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        audio_file = tmp.name

    # Record using arecord
    cmd = [
        'arecord',
        '-D', device,
        '-f', 'S16_LE',
        '-r', str(sample_rate),
        '-c', str(channels),
        '-d', str(duration),
        audio_file
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration+5)
        if result.returncode != 0:
            print(f"Recording error: {result.stderr}")
            return None

        # Verify file exists and has content
        if os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
            return audio_file
        else:
            print("Recording failed - no audio data")
            return None

    except subprocess.TimeoutExpired:
        print("Recording timeout")
        return None
    except Exception as e:
        print(f"Recording error: {e}")
        return None

def format_transcription(text):
    """Format transcription text"""
    if not text:
        return ""

    # Apply Hailo's postprocessing
    text = postprocess_text(text)

    # Clean up whitespace
    text = ' '.join(text.split())

    return text.strip()

def show_welcome():
    """Display welcome screen"""
    print('')
    print('='*70)
    print('  HAILO WHISPER INTERACTIVE TRANSCRIPTION')
    print('  Hardware-accelerated real-time speech-to-text on Raspberry Pi 5')
    print('='*70)
    print('')

def menu_preset(config):
    """Show preset configuration menu"""
    options = [
        "Fastest (tiny model, 10s chunks)",
        "Balanced (base model, 5s chunks) [Recommended]",
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
        config.model_variant = 'tiny'
        return False  # Skip custom menus
    elif choice == 1:  # Balanced (default)
        config.model_variant = 'base'
        return False
    else:  # Custom
        return True

def menu_model_variant(config):
    """Model variant selection menu"""
    options = [
        "tiny (10s chunks, fastest)",
        "base (5s chunks, better quality) [Recommended]"
    ]

    variant_map = ['tiny', 'base']
    current_idx = variant_map.index(config.model_variant) if config.model_variant in variant_map else 1

    menu = TerminalMenu(
        options,
        title="Select Hailo Model Variant:",
        cursor_index=current_idx,
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()
    config.model_variant = variant_map[choice]

def menu_audio_device(config):
    """Audio device selection menu"""
    # Get available audio devices
    try:
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        # Parse output for card numbers
        print("\nAvailable audio devices:")
        print(result.stdout)
    except:
        pass

    options = [
        f"plughw:0,0 (default) [Current: {config.device}]",
        "Custom device string"
    ]

    menu = TerminalMenu(
        options,
        title="Select Audio Device:",
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()

    if choice == 1:  # Custom
        print("\nEnter custom device string (e.g., plughw:1,0): ", end='')
        custom_device = input().strip()
        if custom_device:
            config.device = custom_device

def menu_advanced_options(config):
    """Advanced configuration menu"""
    options = [
        f"Debug Mode: {'Enabled' if config.debug_mode else 'Disabled'}",
        f"Voice Activity Detection: {'Enabled' if config.enable_vad else 'Disabled'}",
        f"Auto Gain Control: {'Enabled' if config.enable_auto_gain else 'Disabled'}",
        f"VAD Threshold: {config.vad_threshold}",
        f"Chunk Overlap: {config.chunk_overlap*100:.0f}%",
        "Done (continue)"
    ]

    while True:
        menu = TerminalMenu(
            options,
            title="Advanced Options:",
            menu_cursor="→ ",
            menu_cursor_style=("fg_cyan", "bold"),
            menu_highlight_style=("bg_cyan", "fg_black")
        )

        choice = menu.show()

        if choice == 0:  # Toggle debug mode
            config.debug_mode = not config.debug_mode
            options[0] = f"Debug Mode: {'Enabled' if config.debug_mode else 'Disabled'}"
        elif choice == 1:  # Toggle VAD
            config.enable_vad = not config.enable_vad
            options[1] = f"Voice Activity Detection: {'Enabled' if config.enable_vad else 'Disabled'}"
        elif choice == 2:  # Toggle auto gain
            config.enable_auto_gain = not config.enable_auto_gain
            options[2] = f"Auto Gain Control: {'Enabled' if config.enable_auto_gain else 'Disabled'}"
        elif choice == 3:  # VAD threshold
            print("\nEnter VAD threshold (0.0-1.0, default 0.2): ", end='')
            try:
                threshold = float(input().strip())
                if 0.0 <= threshold <= 1.0:
                    config.vad_threshold = threshold
                    options[3] = f"VAD Threshold: {config.vad_threshold}"
                else:
                    print("Invalid value. Must be between 0.0 and 1.0")
            except:
                print("Invalid input")
        elif choice == 4:  # Chunk overlap
            print("\n⚠️  Note: Overlap is for long pre-recorded files, not real-time!")
            print("For real-time transcription, keep at 0.0 (disabled).")
            print("\nEnter chunk overlap (0.0-0.5, recommended 0.0): ", end='')
            try:
                overlap = float(input().strip())
                if 0.0 <= overlap <= 0.5:
                    config.chunk_overlap = overlap
                    options[4] = f"Chunk Overlap: {config.chunk_overlap*100:.0f}%"
                else:
                    print("Invalid value. Must be between 0.0 and 0.5")
            except:
                print("Invalid input")
        else:  # Done
            break

def main():
    """Main transcription loop"""
    global pipeline

    # Show welcome screen
    show_welcome()

    # Create config and show menu
    config = Config()

    # Show preset menu
    show_custom = menu_preset(config)

    # If custom selected, show detailed menus
    if show_custom:
        menu_model_variant(config)
        menu_audio_device(config)
        menu_advanced_options(config)

    # Display configuration summary
    config.display_summary()

    input("Press Enter to start transcription with these settings...")

    print("\n" + "="*60)
    print("  HAILO WHISPER TRANSCRIPTION")
    print("  Model: {} | Hardware: {}".format(config.model_variant, config.hw_arch))
    print("="*60)

    # Verify Hailo HAT
    try:
        result = subprocess.run(['hailortcli', 'fw-control', 'identify'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            print("\n⚠️  Warning: Hailo device check failed")
            print("Continuing anyway...")
    except:
        print("\n⚠️  Warning: Could not verify Hailo device")

    # Verify audio device
    print("\nChecking audio device...")
    result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
    if config.device.split(':')[1] not in result.stdout:
        print("⚠️  Warning: Audio device may not be available")
    else:
        print("✓ Audio device found")

    # Test recording
    print("\nTesting audio recording...")
    test_file = record_audio(1, config.device, config.sample_rate, config.channels)
    if test_file:
        os.remove(test_file)
        print("✓ Audio recording works")
    else:
        print("❌ Audio recording failed")
        return

    # Initialize pipeline
    print("\nInitializing Hailo pipeline...")
    try:
        # Construct HEF paths (files are in model-specific subdirectories)
        # Note: tiny model has "15dB" in name, base model doesn't
        if config.model_variant == 'tiny':
            encoder_hef = f"{config.model_variant}-whisper-encoder-{config.chunk_duration}s_15dB_h8l.hef"
        else:  # base model
            encoder_hef = f"{config.model_variant}-whisper-encoder-{config.chunk_duration}s_h8l.hef"

        decoder_hef = f"{config.model_variant}-whisper-decoder-fixed-sequence-matmul-split_h8l.hef"

        encoder_path = os.path.join(config.hef_dir, config.model_variant, encoder_hef)
        decoder_path = os.path.join(config.hef_dir, config.model_variant, decoder_hef)

        # Verify files exist
        if not os.path.exists(encoder_path):
            print(f"❌ Encoder HEF not found: {encoder_path}")
            return
        if not os.path.exists(decoder_path):
            print(f"❌ Decoder HEF not found: {decoder_path}")
            return

        # Create pipeline
        pipeline = HailoWhisperPipeline(
            encoder_model_path=encoder_path,
            decoder_model_path=decoder_path,
            variant=config.model_variant,
            host="arm64"
        )
        print("✓ Pipeline initialized")

    except Exception as e:
        print(f"❌ Failed to initialize pipeline: {e}")
        return

    # Main transcription loop
    print("\n" + "="*60)
    print("  TRANSCRIPTION ACTIVE")
    print("  Press Ctrl+C to stop")
    print("="*60 + "\n")

    signal.signal(signal.SIGINT, signal_handler)
    recording_num = 0

    # Initialize context tracker for cross-chunk continuity
    context_tracker = ContextTracker()

    while running:
        recording_num += 1

        # Record audio
        print(f"\n[{recording_num}] Recording {config.chunk_duration}s...", end='', flush=True)
        start_time = time.time()
        audio_file = record_audio(config.chunk_duration, config.device, config.sample_rate, config.channels)
        record_duration = time.time() - start_time

        if not audio_file:
            print(" ❌ FAILED")
            time.sleep(1)
            continue

        print(f" ✓ ({record_duration:.1f}s)", flush=True)

        try:
            # Load audio (handles conversion to 16kHz mono)
            print(f"[{recording_num}] Processing...", end='', flush=True)
            audio = load_audio(audio_file)

            # Debug: Log audio level before preprocessing
            if config.debug_mode:
                audio_max = np.max(np.abs(audio))
                print(f"\n  [DEBUG] Raw audio max amplitude: {audio_max:.4f}", flush=True)

            # Apply VAD and auto-gain preprocessing (quiet version - no spam)
            start_time = None
            gain_applied = 0
            if config.enable_vad or config.enable_auto_gain:
                audio, start_time, gain_applied = improve_input_audio_quiet(
                    audio,
                    vad=config.enable_vad,
                    low_audio_gain=config.enable_auto_gain,
                    vad_threshold=config.vad_threshold,
                    debug=config.debug_mode
                )

            # Calculate chunk offset (skip silence at beginning, but not too aggressively)
            chunk_offset = 0
            if start_time is not None and start_time > 0.5:
                # Only skip if there's significant silence (>0.5s)
                # Start 0.3s before detected speech for safety
                chunk_offset = max(0, start_time - 0.3)
                if config.debug_mode:
                    print(f"  [DEBUG] Chunk offset: {chunk_offset:.2f}s (speech at {start_time:.2f}s)", flush=True)
            elif config.debug_mode and start_time is not None:
                print(f"  [DEBUG] No offset applied (speech starts early at {start_time:.2f}s)", flush=True)

            # Generate mel spectrograms with overlap
            mel_spectrograms = preprocess(
                audio,
                is_nhwc=True,
                chunk_length=config.chunk_duration,
                chunk_offset=chunk_offset,
                overlap=config.chunk_overlap
            )

            if not mel_spectrograms:
                print(" ⚠️  No audio")
                continue

            # Process through pipeline
            for i, mel in enumerate(mel_spectrograms):
                # Send mel directly as-is, matching official implementation
                pipeline.send_data(mel)
                time.sleep(0.1)

                # Get transcription (blocks until result available)
                transcription = pipeline.get_transcription()

                if transcription:
                    text = format_transcription(transcription)
                    if text:
                        # Process with context tracker
                        display_text, is_continuation = context_tracker.process_transcription(text)

                        # Show visual indicator for continuations
                        if is_continuation:
                            print(f" ✓\n📝 [CONT] {display_text}", flush=True)
                        else:
                            print(f" ✓\n📝 {display_text}", flush=True)

                        if config.debug_mode:
                            print(f"  [DEBUG] Raw transcription: {text}", flush=True)
                            print(f"  [DEBUG] Incomplete buffer: {context_tracker.incomplete_buffer or '(empty)'}", flush=True)
                    else:
                        print(" [silence]", flush=True)
                else:
                    print(" [no transcription]", flush=True)

        except Exception as e:
            print(f"Processing error: {e}")

        finally:
            # Clean up temp file
            try:
                os.remove(audio_file)
            except:
                pass

    # Cleanup
    if pipeline:
        pipeline.stop()
    print("\n✓ Transcription stopped")

if __name__ == "__main__":
    main()