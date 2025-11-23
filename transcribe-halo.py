#!/usr/bin/env python3
"""
Minimal Hailo Whisper Transcription for Raspberry Pi 5 with Hailo-8L
Records audio and performs real-time transcription using hardware acceleration.
"""

import os
import sys
import time
import subprocess
import tempfile
import signal
import numpy as np

# Add Hailo examples to path
hailo_path = os.path.expanduser("~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition")
if os.path.exists(hailo_path):
    sys.path.insert(0, hailo_path)

try:
    # Import Hailo modules
    from app.hailo_whisper_pipeline import HailoWhisperPipeline
    from common.audio_utils import load_audio
    from common.preprocessing import preprocess
    from common.postprocessing import clean_transcription as postprocess_text
except ImportError as e:
    print(f"❌ Error importing Hailo modules: {e}")
    print("\nPlease ensure you've run setup.py in the Hailo repository:")
    print("  cd ~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition")
    print("  python3 setup.py")
    sys.exit(1)

# Configuration
class Config:
    # Hailo settings
    hw_arch = 'hailo8l'
    model_variant = 'base'  # 'tiny' for 10s chunks, 'base' for 5s chunks (FASTER & MORE REAL-TIME!)

    # Audio settings
    device = 'plughw:0,0'
    sample_rate = 48000
    channels = 2
    chunk_duration = 10 if model_variant == 'tiny' else 5

    # Paths (h8l is the directory name for hailo8l)
    hef_dir = os.path.join(hailo_path, 'app', 'hefs', 'h8l')
    decoder_dir = os.path.join(hailo_path, 'app', 'decoder_assets')

# Global variable for clean shutdown
running = True
pipeline = None

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global running
    print("\n\nStopping transcription...")
    running = False
    if pipeline:
        pipeline.stop()
    sys.exit(0)

def record_audio(duration=10):
    """Record audio from microphone and save to temp file"""
    # Create temp file for audio
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        audio_file = tmp.name

    # Record using arecord
    cmd = [
        'arecord',
        '-D', Config.device,
        '-f', 'S16_LE',
        '-r', str(Config.sample_rate),
        '-c', str(Config.channels),
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

def main():
    """Main transcription loop"""
    global pipeline

    print("\n" + "="*60)
    print("  HAILO WHISPER TRANSCRIPTION (MINIMAL)")
    print("  Model: {} | Hardware: {}".format(Config.model_variant, Config.hw_arch))
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
    if Config.device.split(':')[1] not in result.stdout:
        print("⚠️  Warning: Audio device may not be available")
    else:
        print("✓ Audio device found")

    # Test recording
    print("\nTesting audio recording...")
    test_file = record_audio(1)
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
        if Config.model_variant == 'tiny':
            encoder_hef = f"{Config.model_variant}-whisper-encoder-{Config.chunk_duration}s_15dB_h8l.hef"
        else:  # base model
            encoder_hef = f"{Config.model_variant}-whisper-encoder-{Config.chunk_duration}s_h8l.hef"

        decoder_hef = f"{Config.model_variant}-whisper-decoder-fixed-sequence-matmul-split_h8l.hef"

        encoder_path = os.path.join(Config.hef_dir, Config.model_variant, encoder_hef)
        decoder_path = os.path.join(Config.hef_dir, Config.model_variant, decoder_hef)

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
            variant=Config.model_variant,
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

    while running:
        recording_num += 1

        # Record audio
        print(f"\n[{recording_num}] Recording {Config.chunk_duration}s...", end='', flush=True)
        start_time = time.time()
        audio_file = record_audio(Config.chunk_duration)
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

            # Generate mel spectrograms
            mel_spectrograms = preprocess(
                audio,
                is_nhwc=True,
                chunk_length=Config.chunk_duration,
                chunk_offset=0
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
                        print(f" ✓\n📝 {text}", flush=True)
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