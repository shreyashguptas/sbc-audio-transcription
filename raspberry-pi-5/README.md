# Voice Transcription Setup for Raspberry Pi 5

Complete setup guide for real-time voice transcription using INMP441 I2S microphones and Faster-Whisper on a fresh Raspberry Pi 5.

## Hardware Requirements

- Raspberry Pi 5
- 2x INMP441 I2S MEMS microphones
- Jumper wires for connections
- Power supply for Raspberry Pi 5

## 1. Hardware Setup

### Wire the Microphones

Follow the wiring diagram in [PINOUT.md](./PINOUT.md) to connect both INMP441 microphones to your Raspberry Pi 5.

**Quick Reference:**
- Both microphones share: VDD (3.3V), GND, SD (GPIO20), WS (GPIO19), SCK (GPIO18)
- Mic 1: L/R → GND (LEFT channel)
- Mic 2: L/R → 3.3V (RIGHT channel)

## 2. I2S Audio Configuration

### Enable I2S Interface

Edit the boot configuration file:

```bash
sudo nano /boot/firmware/config.txt
```

Add these lines at the end of the file:

```
dtparam=i2s=on
dtoverlay=googlevoicehat-soundcard
```

Save and exit (Ctrl+X, then Y, then Enter).

### Reboot

```bash
sudo reboot
```

### Verify Audio Device

After rebooting, check that the audio device is recognized:

```bash
arecord -l
```

You should see a device like `card 0` or `plughw:0,0`.

### Test the Microphones

Record a 5-second test to verify the microphones are working:

```bash
arecord -D plughw:0,0 -f S16_LE -r 48000 -c 2 -d 5 test.wav
aplay test.wav
```

You should hear your recording played back.

## 3. System Dependencies

Install required system packages:

```bash
sudo apt update
sudo apt install -y \
    python3.13 \
    python3.13-venv \
    python3-pip \
    libasound2-dev \
    libportaudio2 \
    libsndfile1 \
    python3-pyaudio \
    alsa-utils \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    pkg-config
```

**Note**: `gfortran`, `libopenblas-dev`, and `liblapack-dev` are needed for building scipy if pre-built wheels aren't available for Python 3.13.

## 4. Python Virtual Environment Setup

### Create Project Directory

```bash
mkdir -p ~/voice_transcribe
cd ~/voice_transcribe
```

### Copy Project Files

Copy `transcribe.py` and `requirements.txt` to this directory.

### Create Virtual Environment

```bash
python3.13 -m venv venv
```

### Activate Virtual Environment

```bash
source venv/bin/activate
```

Your prompt should now show `(venv)` at the beginning.

### Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will install:
- `soundfile` - Audio file reading/writing
- `scipy` - Signal processing (resampling)
- `faster-whisper` - Whisper model for transcription
- `simple-term-menu` - Interactive configuration menus

**Note**: The first time you run the script, Faster-Whisper will download the selected model (~75MB for tiny, ~140MB for base, ~460MB for small). This may take a few minutes depending on your internet connection.

## 5. Running the Transcription

### Interactive Configuration Mode

The transcribe.py script now features an **interactive menu system** that lets you test different configurations to find the optimal performance for your setup.

```bash
python transcribe.py
```

### Configuration Options

You'll be guided through an interactive menu with arrow-key navigation:

#### 1. **Preset Selection**
Choose from quick presets or custom configuration:
- **Fastest** - tiny model, int8, beam=1, no VAD (maximum speed)
- **Balanced** - base model, int8, beam=5, VAD on (recommended)
- **Quality** - small model, int8, beam=5, VAD on (better accuracy)
- **Custom** - Configure all options manually

#### 2. **Model Settings** (if Custom)
- **Model Size**: tiny, base, small, medium, large-v3, turbo
  - `tiny` - Fastest, least accurate (39M parameters)
  - `base` - Balanced, recommended for Pi 5 (74M parameters)
  - `small` - Better quality, slower (244M parameters)
- **Compute Type**: int8 (recommended), int16, float32
  - `int8` - Best CPU performance with minimal quality loss
- **CPU Threads**: auto (recommended), 2, 4

#### 3. **Transcription Quality** (if Custom)
- **Beam Size**: 1 (fastest) to 10 (best quality)
  - Recommended: 5 for balanced performance
  - Use 1 for maximum speed (greedy search)
- **Temperature**: 0.0 (deterministic) or fallback
- **Condition on Previous Text**: Use context from previous chunks

#### 4. **Voice Activity Detection (VAD)** (if Custom)
- **Enable VAD**: Yes (filter silence) or No
- **VAD Threshold**: 0.2 (sensitive) to 0.6 (strict)
  - Lower = catches quiet speech, higher = ignores background noise
- **Min Silence Duration**: 500ms to 2500ms
  - How long to wait before considering speech ended

#### 5. **Audio Processing** (if Custom)
- **Chunk Duration**: 3s to 15s
  - Shorter = lower latency, longer = more context
- **Overlap Duration**: 1s to 3s
  - Overlap between chunks to catch trailing words
- **Microphone Gain**: 10x to 50x
  - Adjust based on your microphone sensitivity
- **Min Audio Energy**: Threshold for silence detection

#### 6. **Advanced Settings** (if Custom)
- CPU thread control
- Energy threshold tuning
- Context management options

### Configuration Summary

After selecting your options, you'll see a summary:

```
======================================================================
  CONFIGURATION SUMMARY
======================================================================

MODEL SETTINGS:
  Model Size: base
  Compute Type: int8
  CPU Threads: auto

TRANSCRIPTION QUALITY:
  Beam Size: 5
  Temperature: 0.0
  Condition on Previous Text: Yes

VAD SETTINGS:
  VAD Enabled: Yes
  VAD Threshold: 0.25
  Min Silence Duration: 1500ms

AUDIO PROCESSING:
  Chunk Duration: 7s
  Overlap Duration: 2s
  Microphone Gain: 30.0x
  Min Audio Energy: 0.0002
======================================================================

Start transcription with these settings?
→ Yes, start transcription
  No, reconfigure
  Cancel
```

### During Transcription

Once started, you should see:

```
======================================================================
  CONTINUOUS VOICE TRANSCRIPTION
  (Overlapping chunks - captures all words)
============================================================

Loading model...

Ready! Speak naturally - transcription will flow continuously.
Press Ctrl+C to stop

------------------------------------------------------------
```

### Usage

- **Speak naturally** into the microphones
- Transcription appears **in real-time** as you speak
- **Ctrl+C** to stop and see performance statistics

### Performance Statistics

When you stop transcription (Ctrl+C), you'll see detailed performance metrics:

```
======================================================================
  PERFORMANCE STATISTICS
======================================================================

Configuration: base model, int8, beam=5
Total Runtime: 60.5s
Total Audio Processed: 105.0s
Total Words Transcribed: 234
Speed Factor: 1.74x real-time

======================================================================
Transcription stopped
======================================================================
```

**Speed Factor** shows how fast the system processes audio:
- **< 1.0x** = Slower than real-time (falling behind)
- **= 1.0x** = Exactly real-time
- **> 1.0x** = Faster than real-time (can handle continuous speech)

Use these statistics to compare different configurations and find the best balance between speed and quality for your use case.

### Testing Different Configurations

To find your optimal setup:

1. **Start with "Fastest" preset** - Test if tiny model quality is acceptable
2. **Try "Balanced" preset** - Good starting point for most use cases
3. **Test "Quality" preset** - See if small model runs fast enough
4. **Use Custom mode** - Fine-tune specific parameters

**Recommended Testing Workflow:**
- Test each configuration for 30-60 seconds of speech
- Note the Speed Factor in performance statistics
- Compare transcription accuracy
- Aim for Speed Factor > 1.5x for comfortable real-time use

### How It Works

The script:
- Records **audio chunks** (configurable: 3-15 seconds) with **overlap** (1-3 seconds)
- Mixes **both LEFT and RIGHT channels** for optimal audio quality
- Applies **configurable gain** (10-50x) and processes at **16kHz**
- Uses **Faster-Whisper** with your selected model and settings
- Implements **smart deduplication** to avoid repeating words
- Optionally filters silence with **VAD (Voice Activity Detection)**
- Tracks **performance metrics** for optimization

## 6. Troubleshooting

### No Audio Device Found

```bash
# Check if I2S is enabled
dtparam i2s
# Should show: i2s=on

# Reload audio modules
sudo modprobe snd-bcm2835
```

### Permission Denied for Audio

```bash
# Add your user to the audio group
sudo usermod -a -G audio $USER
# Log out and log back in
```

### Poor Transcription Quality

1. **Check microphone positioning** - Place mics facing the sound source
2. **Reduce background noise** - Test in a quieter environment
3. **Verify stereo input** - Run the test recording and listen to both channels
4. **Adjust gain** - If needed, modify the `audio * 30.0` line in `transcribe.py`

### Model Download Issues

```bash
# Manually download model (requires internet)
# The script will do this automatically on first run
# Models are cached in ~/.cache/huggingface/
```

### Import Errors

```bash
# Ensure virtual environment is activated
source ~/voice_transcribe/venv/bin/activate

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

## 7. Audio Configuration Details

### Recording Format

- **Sample Rate**: 48kHz (hardware) → 16kHz (processing)
- **Channels**: 2 (Stereo) → 1 (Mixed to mono)
- **Format**: S16_LE (16-bit signed little-endian)
- **Device**: `plughw:0,0` (ALSA)

### Processing Pipeline

1. Record audio chunks (configurable) as stereo at 48kHz
2. Mix LEFT and RIGHT channels (average)
3. Resample to 16kHz for Whisper
4. Apply gain amplification (configurable)
5. Clip to [-1.0, 1.0] range
6. Transcribe with Faster-Whisper
7. Deduplicate overlapping words
8. Display real-time results
9. Track performance metrics

## 8. Configuration Options Reference

All configuration is done through the interactive menu system. No manual code editing required!

### Model Sizes and Performance

| Model | Parameters | Size | Speed on Pi 5 | Quality | Use Case |
|-------|-----------|------|---------------|---------|----------|
| `tiny` | 39M | ~75MB | Fastest (2-3x RT) | Basic | Maximum speed |
| `base` | 74M | ~140MB | Fast (1.5-2x RT) | Good | Recommended default |
| `small` | 244M | ~460MB | Moderate (0.8-1.2x RT) | Better | Quality focus |
| `medium` | 769M | ~1.5GB | Slow (0.3-0.5x RT) | High | Offline processing |
| `large-v3` | 1550M | ~3GB | Very slow | Best | Maximum quality |
| `turbo` | Optimized | Varies | Fast | Good | Speed-optimized |

**RT = Real-time** (Speed factor estimates for Pi 5 with int8 compute type)

### Compute Types

| Type | Speed | Quality | Memory | Use on Pi 5 |
|------|-------|---------|--------|-------------|
| `int8` | Fastest | Excellent | Low | ✅ Recommended |
| `int16` | Moderate | Slightly better | Medium | ⚠️ If quality critical |
| `float32` | Slowest | Marginal gain | High | ❌ Not recommended |

### Beam Size Impact

| Beam Size | Speed | Quality | Best For |
|-----------|-------|---------|----------|
| 1 | Fastest (3-4x faster) | Good | Speed priority |
| 3 | Fast | Better | Balanced |
| 5 | Moderate | Good | Default recommended |
| 7-10 | Slower | Marginal improvement | Quality focus |

### VAD (Voice Activity Detection)

**Enable VAD** to filter silence and improve efficiency:
- **Threshold**: Lower (0.2-0.3) = catch quiet speech, Higher (0.5-0.6) = ignore background noise
- **Min Silence Duration**: How long to wait before considering speech ended
  - 500-1000ms = Responsive, may cut off trailing words
  - 1500-2000ms = Balanced (recommended)
  - 2500ms+ = Patient, catches all speech

### Chunk Duration vs Latency

| Duration | Latency | Context | Best For |
|----------|---------|---------|----------|
| 3s | Low | Minimal | Real-time interaction |
| 5s | Moderate | Good | Balanced |
| 7s | Higher | Better | Recommended default |
| 10-15s | High | Maximum | Quality transcription |

### Microphone Gain

Adjust based on your microphone sensitivity and environment:
- **10-20x**: For sensitive microphones or loud environments
- **30x**: Default, works well with INMP441
- **40-50x**: For quiet microphones or distant speakers

## 9. Deactivating Virtual Environment

When you're done:

```bash
deactivate
```

## 10. Auto-Start on Boot (Optional)

To run transcription automatically on boot:

```bash
# Create systemd service
sudo nano /etc/systemd/system/voice-transcribe.service
```

Add:

```ini
[Unit]
Description=Voice Transcription Service
After=network.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/voice_transcribe
ExecStart=/home/pi/voice_transcribe/venv/bin/python /home/pi/voice_transcribe/transcribe.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable voice-transcribe.service
sudo systemctl start voice-transcribe.service
```

---

## Quick Reference Commands

```bash
# Activate environment
source ~/voice_transcribe/venv/bin/activate

# Run transcription (interactive mode)
python transcribe.py

# Test microphones
arecord -D plughw:0,0 -f S16_LE -r 48000 -c 2 -d 5 test.wav && aplay test.wav

# Check audio devices
arecord -l

# Deactivate environment
deactivate
```

### Interactive Menu Navigation

- **Arrow Keys (↑/↓)**: Navigate options
- **Enter**: Select option
- **Ctrl+C**: Stop transcription and show performance stats

### Quick Testing Strategy

1. Start with **"Balanced"** preset - Test for 30-60 seconds
2. If Speed Factor < 1.5x, try **"Fastest"** preset
3. If Speed Factor > 2.0x, try **"Quality"** preset
4. Use **"Custom"** to fine-tune specific parameters
5. Compare transcription accuracy vs performance trade-offs

---

**Last Updated**: 2025-11-21
**Python Version**: 3.13+
**Raspberry Pi**: Pi 5
**Microphones**: 2x INMP441 I2S (Stereo)
