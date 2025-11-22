#!/usr/bin/env python3
"""
Interactive Hailo AI HAT Whisper Transcription Tool
Hardware-accelerated speech-to-text using Hailo-8L accelerator

This script uses the official Hailo Whisper implementation for maximum
performance and accuracy while maintaining our custom UI and recording pipeline.
"""

import subprocess
import soundfile as sf
import numpy as np
from scipy import signal
from simple_term_menu import TerminalMenu
import sys
import re
import os
import time

# Add Hailo official code to Python path
HAILO_PATH = os.path.expanduser(
    "~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition"
)
if os.path.exists(HAILO_PATH):
    sys.path.insert(0, HAILO_PATH)
else:
    print(f"\n❌ Error: Hailo Application Code Examples not found at: {HAILO_PATH}")
    print("\nPlease run:")
    print("  cd ~")
    print("  git clone https://github.com/hailo-ai/Hailo-Application-Code-Examples.git")
    print("  cd Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition")
    print("  python3 setup.py")
    print("\nSee HAILO_SETUP.md for details.")
    sys.exit(1)

# Import official Hailo modules
try:
    from app.hailo_whisper_pipeline import HailoWhisperPipeline
    from app.whisper_hef_registry import HEF_REGISTRY
    from common.audio_utils import SAMPLE_RATE
    from common.postprocessing import clean_transcription
    HAILO_AVAILABLE = True
except ImportError as e:
    print(f"\n❌ Error importing Hailo modules: {e}")
    print("\nPlease ensure you've run setup.py in the Hailo repository:")
    print("  cd ~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition")
    print("  python3 setup.py")
    print("\nThis will install all required dependencies.")
    sys.exit(1)


class HailoTranscriptionConfig:
    """Configuration for Hailo-based transcription parameters"""

    def __init__(self):
        # Hailo hardware settings
        self.hw_arch = 'hailo8l'  # hailo8l for Raspberry Pi 5
        self.model_variant = 'base'  # tiny or base

        # Audio hardware configuration
        # Configured for: Seeed 2-mic voicecard driver (dual INMP441 I2S microphones)
        # Driver overlays in /boot/firmware/config.txt:
        #   - dtoverlay=googlevoicehat-soundcard,alsaname=seeed-2mic-voicecard
        #   - dtoverlay=i2s-mmap
        #
        # This configuration uses both INMP441 microphones in stereo mode at 48kHz,
        # which provides better audio quality for transcription.
        #
        # Current configuration (Seeed 2-mic driver with dual INMP441 mics):
        self.audio_sample_rate = 48000  # Sample rate in Hz (INMP441 native capability)
        self.audio_channels = 2         # Stereo - uses both left and right INMP441 mics

        # Audio processing (kept from original)
        self.chunk_duration = 5  # Base model works best with 5s chunks
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
        print('HAILO HARDWARE SETTINGS:')
        print(f'  Hardware Architecture: {self.hw_arch.upper()}')
        print(f'  Whisper Model Variant: {self.model_variant}')
        print(f'  Expected Chunk Duration: {self.chunk_duration}s')
        print('')
        print('AUDIO HARDWARE:')
        channel_mode = 'mono' if self.audio_channels == 1 else 'stereo'
        print(f'  Sample Rate: {self.audio_sample_rate} Hz')
        print(f'  Channels: {self.audio_channels} ({channel_mode})')
        print('')
        print('AUDIO PROCESSING:')
        print(f'  Chunk Duration: {self.chunk_duration}s')
        print(f'  Overlap Duration: {self.overlap_duration}s')
        print(f'  Microphone Gain: {self.gain}x')
        print(f'  Min Audio Energy: {self.min_audio_energy}')
        print('')
        print('NOTE: Using official Hailo implementation for optimal performance')
        print('='*70)
        print('')


def show_welcome():
    """Display welcome screen"""
    print('')
    print('='*70)
    print('  HAILO AI HAT WHISPER TRANSCRIPTION TOOL')
    print('  Hardware-accelerated speech-to-text on Hailo-8L')
    print('='*70)
    print('')


def menu_preset(config):
    """Show preset configuration menu"""
    options = [
        "Fastest (tiny model, 39M params, 10s chunks)",
        "Balanced (base model, 74M params, 5s chunks) [Recommended]",
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
        config.chunk_duration = 10  # Tiny model uses 10s chunks
        return False  # Skip custom menus
    elif choice == 1:  # Balanced (default)
        config.model_variant = 'base'
        config.chunk_duration = 5  # Base model uses 5s chunks
        return False
    else:  # Custom
        return True


def menu_model_variant(config):
    """Model variant selection menu"""
    options = [
        "tiny (fastest, 39M parameters, 10s chunks)",
        "base (balanced, 74M parameters, 5s chunks) [Recommended]"
    ]

    variant_map = ['tiny', 'base']
    current_idx = variant_map.index(config.model_variant) if config.model_variant in variant_map else 1

    menu = TerminalMenu(
        options,
        title="Select Whisper Model Variant:",
        cursor_index=current_idx,
        menu_cursor="→ ",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black")
    )

    choice = menu.show()
    config.model_variant = variant_map[choice]

    # Set chunk duration based on model
    config.chunk_duration = 10 if config.model_variant == 'tiny' else 5


def menu_audio_processing(config):
    """Audio processing configuration menu"""
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
        "Yes (configure energy threshold)",
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


def configure_transcription():
    """Main configuration workflow"""
    show_welcome()

    config = HailoTranscriptionConfig()

    # Show preset menu
    custom = menu_preset(config)

    if custom:
        # Model settings
        menu_model_variant(config)

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


def get_hef_paths(config):
    """
    Get HEF file paths from official Hailo registry.

    Returns:
        tuple: (encoder_path, decoder_path)
    """
    try:
        # Get paths from official registry
        encoder_rel = HEF_REGISTRY[config.model_variant][config.hw_arch]["encoder"]
        decoder_rel = HEF_REGISTRY[config.model_variant][config.hw_arch]["decoder"]

        # Convert to absolute paths
        encoder_path = os.path.join(HAILO_PATH, encoder_rel)
        decoder_path = os.path.join(HAILO_PATH, decoder_rel)

        # Verify files exist
        if not os.path.exists(encoder_path):
            raise FileNotFoundError(f"Encoder HEF not found: {encoder_path}")
        if not os.path.exists(decoder_path):
            raise FileNotFoundError(f"Decoder HEF not found: {decoder_path}")

        return encoder_path, decoder_path

    except KeyError as e:
        print(f"\n❌ Error: Model '{config.model_variant}' not available for hardware '{config.hw_arch}'")
        print("\nAvailable combinations:")
        for model in HEF_REGISTRY.keys():
            for hw in HEF_REGISTRY[model].keys():
                print(f"  - Model: {model}, Hardware: {hw}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("\nPlease run setup.py to download HEF models:")
        print("  cd ~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition")
        print("  python3 setup.py")
        sys.exit(1)


def detect_audio_devices():
    """
    Detect and display available audio recording devices.

    Returns:
        bool: True if at least one device found, False otherwise
    """
    print('')
    print('='*70)
    print('  AUDIO DEVICE DETECTION')
    print('='*70)
    print('')

    # List all audio devices
    print('Detecting audio recording devices...')
    print('')
    result = subprocess.run(
        ['arecord', '-l'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        print('❌ Error: Could not list audio devices')
        print(f'Error: {result.stderr}')
        return False

    print(result.stdout)

    # Check if any devices were found
    if 'no soundcards found' in result.stdout.lower():
        print('❌ No audio recording devices found!')
        print('')
        print('Troubleshooting:')
        print('1. Check microphone wiring (see PINOUT.md)')
        print('2. Verify I2S is enabled: dtparam i2s')
        print('3. Check kernel modules: lsmod | grep snd')
        print('4. Reboot and try again')
        return False

    return True


def check_audio_hardware_params(device='plughw:0,0', sample_rate=48000, channels=2):
    """
    Check hardware parameters supported by the audio device.

    Args:
        device: ALSA device name (default: 'plughw:0,0')
        sample_rate: Sample rate to test (default: 48000)
        channels: Number of channels to test (default: 2)

    Returns:
        bool: True if device supports required format, False otherwise
    """
    print('='*70)
    print(f'  HARDWARE CAPABILITIES: {device}')
    print('='*70)
    print('')
    print('Checking supported audio formats...')
    print(f'  Testing: {sample_rate}Hz, {channels} channel(s), S16_LE format')
    print('')

    try:
        result = subprocess.run(
            ['arecord', '--dump-hw-params', '-D', device,
             '-f', 'S16_LE', '-r', str(sample_rate), '-c', str(channels)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            print(f'❌ Error: Could not query device {device}')
            print(f'stderr: {result.stderr}')
            print(f'stdout: {result.stdout}')
            return False

        print(result.stdout)
        print(result.stderr)
        return True

    except subprocess.TimeoutExpired:
        print('❌ Error: Hardware capability check timed out after 5 seconds')
        print('')
        print('This typically happens with I2S microphones when:')
        print('  - The audio device expects specific parameters')
        print('  - The driver is not properly configured')
        print('  - Hardware connections are incorrect')
        print('')
        print('Skipping hardware capability check...')
        print('The actual recording test will verify if audio works.')
        print('')
        return False


def test_audio_recording(config, device='plughw:0,0'):
    """
    Perform a test recording to verify audio configuration works.

    Args:
        config: HailoTranscriptionConfig object
        device: ALSA device name (default: 'plughw:0,0')

    Returns:
        bool: True if test recording succeeded, False otherwise
    """
    print('='*70)
    print('  PRE-FLIGHT AUDIO TEST')
    print('='*70)
    print('')
    print('Testing audio recording with your configuration...')
    print(f'  Device: {device}')
    print(f'  Format: S16_LE')
    print(f'  Sample Rate: {config.audio_sample_rate} Hz')
    print(f'  Channels: {config.audio_channels}')
    print(f'  Duration: 1 second')
    print('')

    test_file = '/tmp/audio_test.wav'

    # Build the exact command we'll use
    cmd = [
        'arecord',
        '-D', device,
        '-f', 'S16_LE',
        '-r', str(config.audio_sample_rate),
        '-c', str(config.audio_channels),
        '-d', '1',
        test_file
    ]

    print('Running command:')
    print('  ' + ' '.join(cmd))
    print('')

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )

        print('--- arecord stdout ---')
        if result.stdout:
            print(result.stdout)
        else:
            print('(empty)')
        print('')

        print('--- arecord stderr ---')
        if result.stderr:
            print(result.stderr)
        else:
            print('(empty)')
        print('')

        if result.returncode != 0:
            print('❌ Test recording FAILED!')
            print(f'Return code: {result.returncode}')
            print('')
            print('Common issues:')
            print('1. Device does not support the requested sample rate or channels')
            print('2. Audio device is busy (close other audio applications)')
            print('3. I2S driver not loaded or microphone not connected')
            print('')
            print('Suggested fixes:')
            print('1. Run: arecord --dump-hw-params -D plughw:0,0')
            print('   to see supported formats')
            print('2. Update audio_sample_rate and audio_channels in')
            print('   HailoTranscriptionConfig (line ~67-68) to match')
            print('3. Check HAILO_SETUP.md Step 7 for configuration guide')

            # Cleanup
            try:
                os.remove(test_file)
            except:
                pass

            return False

        # Check file was created
        if not os.path.exists(test_file):
            print('❌ Test recording failed: file not created')
            return False

        file_size = os.path.getsize(test_file)
        if file_size == 0:
            print('❌ Test recording failed: file is empty')
            os.remove(test_file)
            return False

        print(f'✓ Test recording SUCCEEDED!')
        print(f'  File size: {file_size} bytes')
        print(f'  File: {test_file}')
        print('')

        # Cleanup
        try:
            os.remove(test_file)
        except:
            pass

        return True

    except subprocess.TimeoutExpired:
        print('❌ Test recording timed out!')
        print('The audio device may be unresponsive or misconfigured.')
        return False
    except Exception as e:
        print(f'❌ Test recording error: {e}')
        import traceback
        traceback.print_exc()
        return False


def preprocess_audio_for_hailo(audio_file, config):
    """
    Preprocess audio file for Hailo inference.
    Converts our recorded audio to the format expected by Hailo Whisper.

    Args:
        audio_file: Path to WAV file (48kHz stereo from INMP441)
        config: Configuration object

    Returns:
        numpy array: Preprocessed audio at 16kHz mono, float32 [-1, 1]
    """
    # Load audio
    audio, sr = sf.read(audio_file)

    # Mix both LEFT and RIGHT channels for stereo audio capture
    if len(audio.shape) > 1:
        audio = np.mean(audio, axis=1)

    # Resample to 16kHz (Whisper requirement)
    if sr != SAMPLE_RATE:
        audio = signal.resample(audio, int(len(audio) * SAMPLE_RATE / sr))

    # Apply gain
    audio = audio * config.gain

    # Clip to valid range
    audio = np.clip(audio, -1.0, 1.0)

    return audio.astype(np.float32)


def run_transcription(config):
    """Run transcription with configured parameters"""

    # Step 1: Detect audio devices
    if not detect_audio_devices():
        print('')
        print('❌ Cannot proceed without audio devices!')
        sys.exit(1)

    # Step 2: Check hardware capabilities
    print('')
    if not check_audio_hardware_params('plughw:0,0', config.audio_sample_rate, config.audio_channels):
        print('')
        print('⚠️  Warning: Could not check hardware capabilities')
        print('Proceeding anyway...')
        print('')

    # Step 3: Test recording with user's configuration
    print('')
    if not test_audio_recording(config, 'plughw:0,0'):
        print('')
        print('❌ Pre-flight audio test FAILED!')
        print('Cannot proceed until audio recording is working.')
        print('')
        print('Please fix the audio configuration and try again.')
        sys.exit(1)

    print('✓ Audio system check complete!')
    print('')

    print('')
    print('='*70)
    print('  LOADING HAILO MODEL')
    print('='*70)
    print('')

    # Get HEF file paths
    encoder_path, decoder_path = get_hef_paths(config)

    print(f'Encoder HEF: {os.path.basename(encoder_path)}')
    print(f'Decoder HEF: {os.path.basename(decoder_path)}')
    print('')

    # Initialize Hailo Whisper pipeline
    print(f'Loading {config.model_variant} model on {config.hw_arch.upper()} hardware...')

    try:
        pipeline = HailoWhisperPipeline(
            encoder_model_path=encoder_path,
            decoder_model_path=decoder_path,
            variant=config.model_variant,
            multi_process_service=False
        )
    except Exception as e:
        print(f"\n❌ Error initializing Hailo pipeline: {e}")
        print("\nTroubleshooting:")
        print("1. Verify Hailo device is detected: lspci | grep Hailo")
        print("2. Check HailoRT is working: hailortcli fw-control identify")
        print("3. Ensure you have hailo-all installed: dpkg -l | grep hailo")
        sys.exit(1)

    print('')
    print('='*70)
    print('  TRANSCRIPTION ACTIVE (HAILO ACCELERATED)')
    print('='*70)
    print('')
    print('Ready! Speak naturally - transcription will flow continuously.')
    print('Press Ctrl+C to stop')
    print('')
    print(f'NOTE: Using Hailo AI HAT with {config.model_variant} model')
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

            # Record audio using configured hardware parameters
            audio_file = f'/tmp/seg_{segment_num}.wav'

            # Build command
            cmd = [
                'arecord',
                '-D', 'plughw:0,0',
                '-f', 'S16_LE',
                '-r', str(config.audio_sample_rate),
                '-c', str(config.audio_channels),
                '-d', str(config.chunk_duration),
                audio_file
            ]

            # Show command for first recording
            if segment_num == 1:
                print(f"DEBUG: Recording command: {' '.join(cmd)}")
                print('')

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Check if recording succeeded
            if result.returncode != 0:
                print(f"\n❌ Error: Recording failed!")
                print(f"Return code: {result.returncode}")
                print('')
                print('--- Full Command ---')
                print(' '.join(cmd))
                print('')
                print('--- stderr output ---')
                print(result.stderr)
                print('')
                print('--- stdout output ---')
                print(result.stdout if result.stdout else '(empty)')
                print('')
                print("\nTroubleshooting:")
                print("1. Check audio hardware capabilities: arecord --dump-hw-params -D plughw:0,0")
                print("2. Test your audio device: arecord -l")
                print(f"3. Try manual recording with current config:")
                print(f"   arecord -D plughw:0,0 -f S16_LE -r {config.audio_sample_rate} -c {config.audio_channels} -d 3 test.wav")
                print(f"4. If recording fails, update audio_sample_rate and audio_channels in")
                print(f"   HailoTranscriptionConfig class (line ~67-68) to match your hardware")
                print("5. See HAILO_SETUP.md Step 7 for audio configuration help")
                pipeline.stop()
                sys.exit(1)

            # Check if file exists and has content
            if not os.path.exists(audio_file):
                print(f"\n❌ Error: Audio file was not created: {audio_file}")
                print(f"The arecord command returned success (code 0) but file doesn't exist!")
                print(f"This is very unusual - possibly a permissions or filesystem issue.")
                pipeline.stop()
                sys.exit(1)

            file_size = os.path.getsize(audio_file)
            if file_size == 0:
                print(f"\n❌ Error: Audio file is empty: {audio_file}")
                print(f"The arecord command returned success but created an empty file!")
                print(f"This may indicate a driver or hardware issue.")
                pipeline.stop()
                sys.exit(1)

            # Show recording success (for first 3 recordings to verify it's working)
            if segment_num <= 3:
                expected_size = config.audio_sample_rate * config.audio_channels * 2 * config.chunk_duration
                print(f"✓ Recording #{segment_num} successful: {file_size} bytes (expected ~{expected_size} bytes)")

            # Always show debug file size
            if segment_num == 1:
                print(f"DEBUG: S16_LE format = 2 bytes per sample")
                print(f"DEBUG: Expected size = {config.audio_sample_rate} Hz × {config.audio_channels} ch × 2 bytes × {config.chunk_duration}s = ~{config.audio_sample_rate * config.audio_channels * 2 * config.chunk_duration} bytes")
                print('')

            total_audio_duration += config.chunk_duration

            # Load and preprocess audio using ONLY Hailo's official pipeline
            try:
                # Import Hailo audio utilities
                from common.audio_utils import load_audio
                from common.preprocessing import preprocess

                # Load audio with Hailo's official loader (handles format conversion)
                # This function uses ffmpeg internally to resample to 16kHz mono
                print(f"DEBUG: Loading audio with Hailo's load_audio()...")
                audio_for_hailo = load_audio(audio_file)

                print(f"DEBUG: Loaded audio shape: {audio_for_hailo.shape}, dtype: {audio_for_hailo.dtype}")
                print(f"DEBUG: Audio array size: {audio_for_hailo.size} samples")

                if audio_for_hailo.size == 0:
                    print("\n❌ ERROR: Hailo's load_audio() returned empty array!")
                    print("This may indicate:")
                    print("  - ffmpeg is not installed or not working")
                    print("  - Audio file format is incompatible")
                    print("  - load_audio() has a bug")
                    try:
                        os.remove(audio_file)
                    except:
                        pass
                    continue

                # Apply gain adjustment (after Hailo's normalization)
                audio_for_hailo = audio_for_hailo * config.gain
                audio_for_hailo = np.clip(audio_for_hailo, -1.0, 1.0)

                # Check audio energy AFTER loading
                if not has_sufficient_audio(audio_for_hailo, config.min_audio_energy):
                    print("DEBUG: Audio energy too low, skipping...")
                    try:
                        os.remove(audio_file)
                    except:
                        pass
                    continue

                # Generate mel spectrograms using official preprocessing
                print(f"DEBUG: Generating mel spectrograms with chunk_length={config.chunk_duration}...")
                mel_spectrograms = preprocess(
                    audio_for_hailo,
                    is_nhwc=True,  # Hailo expects NHWC format
                    chunk_length=config.chunk_duration,
                    chunk_offset=0
                )

                print(f"DEBUG: Generated {len(mel_spectrograms)} mel spectrogram(s)")

                # Validate mel spectrograms
                if not mel_spectrograms or len(mel_spectrograms) == 0:
                    print("\n❌ ERROR: preprocess() returned no mel spectrograms!")
                    print("This may indicate:")
                    print("  - Audio duration doesn't match expected chunk_length")
                    print("  - preprocess() function has a bug or parameter mismatch")
                    try:
                        os.remove(audio_file)
                    except:
                        pass
                    continue

                # Process each mel spectrogram chunk
                text_chunks = []
                for i, mel in enumerate(mel_spectrograms):
                    print(f"DEBUG: Mel {i}: shape={mel.shape}, dtype={mel.dtype}")
                    print(f"DEBUG:   Elements: {mel.size}, Bytes: {mel.nbytes}")
                    print(f"DEBUG:   C-contiguous: {mel.flags['C_CONTIGUOUS']}, F-contiguous: {mel.flags['F_CONTIGUOUS']}")
                    print(f"DEBUG:   Memory layout: {mel.flags}")

                    if mel.size == 0:
                        print(f"\n⚠️  WARNING: Mel {i} is empty, skipping!")
                        continue

                    # Expected size for tiny-10s model: 320,000 bytes (80 x 1000 x 4)
                    expected_size = 320000 if config.model_variant == 'tiny' else 160000
                    if mel.nbytes != expected_size:
                        print(f"\n⚠️  WARNING: Mel size mismatch!")
                        print(f"   Expected: {expected_size} bytes")
                        print(f"   Got: {mel.nbytes} bytes")

                    # Fix shape: Model expects 3D (batch, time, features), not 4D NHWC
                    # Convert (1, 1, 1000, 80) → (1, 1000, 80) by removing dimension at index 1
                    if mel.ndim == 4 and mel.shape[1] == 1:
                        print(f"DEBUG: Removing extra dimension from NHWC format...")
                        mel = mel.squeeze(1)  # Remove dimension at index 1
                        print(f"DEBUG:   After squeeze - shape: {mel.shape}, nbytes: {mel.nbytes}")

                    # CRITICAL: Ensure C-contiguous layout (matches official Hailo pipeline)
                    # ascontiguousarray creates a copy only if needed
                    print(f"DEBUG: Before ascontiguousarray - C-contig: {mel.flags['C_CONTIGUOUS']}, OWNDATA: {mel.flags['OWNDATA']}")
                    mel = np.ascontiguousarray(mel)
                    print(f"DEBUG: After ascontiguousarray - C-contig: {mel.flags['C_CONTIGUOUS']}, OWNDATA: {mel.flags['OWNDATA']}")

                    try:
                        print(f"DEBUG: Final mel - shape: {mel.shape}, dtype: {mel.dtype}, nbytes: {mel.nbytes}")
                        pipeline.send_data(mel)
                        time.sleep(0.1)  # Match official app delay
                        transcription = pipeline.get_transcription()
                        if transcription:
                            # Clean transcription using official postprocessing
                            cleaned = clean_transcription(transcription)
                            if cleaned:
                                text_chunks.append(cleaned)
                    except Exception as e:
                        print(f"\n⚠️  WARNING: Pipeline error for mel {i}: {e}")
                        continue

                # Combine chunks
                text = ' '.join(text_chunks)
                text = normalize_whitespace(text)

            except Exception as e:
                print(f"\n⚠️  Warning: Audio preprocessing/inference error: {e}")
                import traceback
                traceback.print_exc()
                try:
                    os.remove(audio_file)
                except:
                    pass
                continue

            # Validation checks
            if text:
                word_count = len(text.split())

                if word_count < config.min_words:
                    try:
                        os.remove(audio_file)
                    except:
                        pass
                    continue

                if is_repetition(text, last_text):
                    try:
                        os.remove(audio_file)
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
        print(f'Configuration: Hailo {config.hw_arch.upper()}, {config.model_variant} model')
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

        # Cleanup Hailo resources
        try:
            pipeline.stop()
        except:
            pass
        sys.exit(0)


def main():
    """Main entry point"""

    # Check if Hailo SDK is available
    if not HAILO_AVAILABLE:
        print("\n" + "="*70)
        print("  ERROR: Hailo Modules Not Found")
        print("="*70)
        print("\nCould not import Hailo modules.")
        print("\nPlease ensure you've run setup.py:")
        print("  cd ~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition")
        print("  python3 setup.py")
        print("\nFor detailed instructions, see: HAILO_SETUP.md")
        print("="*70 + "\n")
        sys.exit(1)

    try:
        config = configure_transcription()
        run_transcription(config)
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)


if __name__ == "__main__":
    main()
