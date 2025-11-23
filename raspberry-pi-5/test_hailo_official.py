#!/usr/bin/env python3
"""
Minimal test script using official Hailo Whisper Pipeline
This matches the official app_hailo_whisper.py flow exactly
"""

import sys
import os
import time
import numpy as np

# Add Hailo examples to path
sys.path.insert(0, os.path.expanduser('~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition'))

from app.hailo_whisper_pipeline import HailoWhisperPipeline
from common.audio_utils import load_audio
from common.preprocessing import preprocess
from app.whisper_hef_registry import HEF_REGISTRY


def get_hef_path(model_variant: str, hw_arch: str, component: str) -> str:
    """Get HEF file path from registry"""
    base_path = os.path.expanduser('~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition')

    try:
        relative_path = HEF_REGISTRY[model_variant][hw_arch][component]
    except KeyError as e:
        raise FileNotFoundError(
            f"HEF not available for model '{model_variant}' on hardware '{hw_arch}'."
        ) from e

    # Convert relative path to absolute
    hef_path = os.path.join(base_path, relative_path)

    if not os.path.exists(hef_path):
        raise FileNotFoundError(f"HEF file not found at: {hef_path}")
    return hef_path


def main():
    print("="*70)
    print("  OFFICIAL HAILO WHISPER TEST")
    print("="*70)
    print("")

    variant = "tiny"
    hw_arch = "hailo8l"

    print(f"Selected variant: Whisper {variant}")
    encoder_path = get_hef_path(variant, hw_arch, "encoder")
    decoder_path = get_hef_path(variant, hw_arch, "decoder")

    print(f"Encoder: {encoder_path}")
    print(f"Decoder: {decoder_path}")
    print("")

    # Initialize pipeline
    print("Initializing Hailo Whisper pipeline...")
    whisper_hailo = HailoWhisperPipeline(
        encoder_path,
        decoder_path,
        variant,
        multi_process_service=False
    )
    print("✓ Pipeline initialized successfully")
    print("")

    # Use a test audio file
    audio_path = "/tmp/seg_1.wav"  # Use the recording from transcribe-halo.py

    if not os.path.exists(audio_path):
        print(f"❌ Test audio file not found: {audio_path}")
        print("Please run transcribe-halo.py first to create a test recording")
        return

    print(f"Loading audio from: {audio_path}")
    audio = load_audio(audio_path)
    print(f"✓ Loaded audio: shape={audio.shape}, dtype={audio.dtype}")
    print("")

    # Preprocess
    is_nhwc = True
    chunk_length = 10
    chunk_offset = 0

    print(f"Preprocessing with:")
    print(f"  is_nhwc={is_nhwc}")
    print(f"  chunk_length={chunk_length}")
    print(f"  chunk_offset={chunk_offset}")

    mel_spectrograms = preprocess(
        audio,
        is_nhwc=is_nhwc,
        chunk_length=chunk_length,
        chunk_offset=chunk_offset
    )

    print(f"✓ Generated {len(mel_spectrograms)} mel spectrogram(s)")
    print("")

    # Process each mel
    for i, mel in enumerate(mel_spectrograms):
        print(f"Processing mel {i}:")
        print(f"  Original shape: {mel.shape}")
        print(f"  Original dtype: {mel.dtype}")
        print(f"  C-contiguous: {mel.flags['C_CONTIGUOUS']}")
        print(f"  OWNDATA: {mel.flags['OWNDATA']}")
        print(f"  Bytes: {mel.nbytes}")
        print("")

        try:
            print("Sending data to pipeline...")
            whisper_hailo.send_data(mel)

            print("Waiting for transcription...")
            time.sleep(0.1)

            transcription = whisper_hailo.get_transcription()
            print(f"✓ Transcription: {transcription}")
            print("")

        except Exception as e:
            print(f"❌ Error during inference: {e}")
            import traceback
            traceback.print_exc()
            break

    # Stop pipeline
    print("Stopping pipeline...")
    whisper_hailo.stop()
    print("✓ Done")


if __name__ == "__main__":
    main()
