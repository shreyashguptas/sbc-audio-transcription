#!/usr/bin/env python3
"""
Debug script to check what the Hailo model expects
"""

import sys
import os

# Add Hailo examples to path
sys.path.insert(0, os.path.expanduser('~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition'))

from hailo_platform import HEF, VDevice, HailoSchedulingAlgorithm, FormatType
from app.whisper_hef_registry import HEF_REGISTRY


def main():
    print("="*70)
    print("  HAILO MODEL SHAPE INSPECTOR")
    print("="*70)
    print("")

    variant = "tiny"
    hw_arch = "hailo8l"
    base_path = os.path.expanduser('~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition')

    encoder_path = os.path.join(base_path, HEF_REGISTRY[variant][hw_arch]["encoder"])
    decoder_path = os.path.join(base_path, HEF_REGISTRY[variant][hw_arch]["decoder"])

    print(f"Encoder HEF: {encoder_path}")
    print(f"Decoder HEF: {decoder_path}")
    print("")

    # Create VDevice
    params = VDevice.create_params()
    params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN

    with VDevice(params) as vdevice:
        print("Creating infer models...")
        encoder_infer_model = vdevice.create_infer_model(encoder_path)

        # Set format types
        encoder_infer_model.input().set_format_type(FormatType.FLOAT32)
        encoder_infer_model.output().set_format_type(FormatType.FLOAT32)

        print("")
        print("ENCODER INPUT:")
        print(f"  Name: {encoder_infer_model.input().name}")
        print(f"  Shape: {encoder_infer_model.input().shape}")
        print(f"  Format: {encoder_infer_model.input().format.type}")
        print("")

        print("ENCODER OUTPUT:")
        print(f"  Name: {encoder_infer_model.output().name}")
        print(f"  Shape: {encoder_infer_model.output().shape}")
        print(f"  Format: {encoder_infer_model.output().format.type}")
        print("")

        # Try to configure and check bindings
        with encoder_infer_model.configure() as configured:
            bindings = configured.create_bindings()
            print("ENCODER BINDINGS:")
            print(f"  Input binding shape: {configured.get_input_vstream_infos()[0].shape}")
            print(f"  Expected data type: {configured.get_input_vstream_infos()[0].format.type}")
            print("")

        print("✓ Model inspection complete")


if __name__ == "__main__":
    main()
