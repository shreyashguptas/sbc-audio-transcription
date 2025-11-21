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

**Note**: The first time you run the script, Faster-Whisper will download the `base` model (~140MB). This may take a few minutes depending on your internet connection.

## 5. Running the Transcription

### Start Transcription

```bash
python transcribe.py
```

You should see:

```
============================================================
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
- **Ctrl+C** to stop

### How It Works

The script:
- Records **7-second audio chunks** with **2-second overlap**
- Mixes **both LEFT and RIGHT channels** for optimal audio quality
- Applies **30x gain** and processes at **16kHz**
- Uses **Faster-Whisper base model** for transcription
- Implements **smart deduplication** to avoid repeating words
- Filters silence automatically with **VAD (Voice Activity Detection)**

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

1. Record 7-second stereo audio at 48kHz
2. Mix LEFT and RIGHT channels (average)
3. Resample to 16kHz for Whisper
4. Apply 30x gain amplification
5. Clip to [-1.0, 1.0] range
6. Transcribe with Faster-Whisper
7. Deduplicate overlapping words
8. Display real-time results

## 8. Advanced Configuration

### Change Whisper Model

Edit `transcribe.py` line 24:

```python
# Options: tiny, base, small, medium, large-v2, large-v3
model = WhisperModel('base', device='cpu', compute_type='int8')
```

**Model Sizes:**
- `tiny` - Fastest, less accurate (~75MB)
- `base` - Balanced (default) (~140MB)
- `small` - Better accuracy (~460MB)
- `medium` - High accuracy (~1.5GB)
- `large-v3` - Best accuracy (~3GB)

### Adjust Recording Duration

Edit `transcribe.py` line 36:

```python
CHUNK_DURATION = 7  # Seconds per recording chunk
```

### Modify Overlap

Edit `transcribe.py` line 37:

```python
OVERLAP_DURATION = 2  # Overlap between chunks
```

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

# Run transcription
python transcribe.py

# Test microphones
arecord -D plughw:0,0 -f S16_LE -r 48000 -c 2 -d 5 test.wav && aplay test.wav

# Check audio devices
arecord -l

# Deactivate environment
deactivate
```

---

**Last Updated**: 2025-11-21
**Python Version**: 3.13+
**Raspberry Pi**: Pi 5
**Microphones**: 2x INMP441 I2S (Stereo)
