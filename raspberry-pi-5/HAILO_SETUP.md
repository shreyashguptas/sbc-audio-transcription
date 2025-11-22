# Hailo AI HAT Setup Guide for Raspberry Pi 5

**Complete step-by-step guide to set up hardware-accelerated Whisper transcription on a fresh Raspberry Pi 5.**

This guide assumes you're starting with a freshly installed Raspberry Pi OS and will walk you through every step to get `transcribe-halo.py` running.

---

## Quick Start

For experienced users, here's the condensed workflow:

```bash
# 1. Install HailoRT
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y hailo-all
sudo reboot

# 2. Verify Hailo hardware
lspci | grep Hailo
hailortcli fw-control identify

# 3. Test audio hardware
arecord -l
arecord --dump-hw-params -D plughw:0,0 2>&1 | grep -E "RATE|CHANNELS"

# 4. Clone project (if not already done)
cd ~
git clone https://github.com/shreyashguptas/sbc-audio-transcription.git

# 5. Create virtual environment (IMPORTANT: with --system-site-packages)
cd ~/sbc-audio-transcription/raspberry-pi-5
python3.11 -m venv --system-site-packages venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. Clone and setup Hailo Application Code Examples
cd ~
git clone https://github.com/hailo-ai/Hailo-Application-Code-Examples.git
cd Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition
python3 setup.py

# 7. Run transcription
cd ~/sbc-audio-transcription/raspberry-pi-5
source venv/bin/activate
python transcribe-halo.py
```

---

## Hardware Requirements

### What You Need

- **Raspberry Pi 5** (4GB or 8GB recommended)
- **Hailo AI HAT** (M.2 HAT+ with Hailo-8L accelerator)
  - Hailo-8L variant: 13 TOPS
  - Connects via M.2 M-Key slot
- **Audio Input Device** - One of:
  - 2x INMP441 I2S Microphones (stereo setup)
  - Google Voice HAT
  - USB microphone
  - Any ALSA-compatible audio device
- **Power Supply**: Official Raspberry Pi 5 27W USB-C power supply (required for stable Hailo operation)
- **MicroSD Card**: 32GB+ with Raspberry Pi OS Bookworm 64-bit

### Hardware Installation

1. **Power off** your Raspberry Pi 5 completely
2. **Install M.2 HAT+** on Raspberry Pi 5 GPIO header
3. **Connect Hailo AI HAT** to M.2 M-Key slot on the HAT+
4. **Secure with standoffs** to prevent movement
5. **Power on** and verify detection:
   ```bash
   lspci | grep -i hailo
   # Expected output:
   # 0001:01:00.0 Co-processor: Hailo Technologies Ltd. Hailo-8 AI Processor (rev 01)
   ```

---

## System Prerequisites

### Operating System

**Required:** Raspberry Pi OS Bookworm (64-bit)

```bash
# Check your OS version
cat /etc/os-release

# Should show:
# VERSION_CODENAME=bookworm
# Architecture must be: aarch64
```

**Important:** Hailo packages are only available for **Debian 12 (Bookworm)**. If you're running Debian 13 (Trixie) or another version, you must reinstall with Bookworm.

**Download:** https://www.raspberrypi.com/software/operating-systems/
- Select: **Raspberry Pi OS Lite (64-bit)** or **Raspberry Pi OS with Desktop (64-bit)**
- Both work equally well - Lite is recommended for headless/SSH use

### Python Version

**Available:** Python 3.11.2 (pre-installed on Bookworm)

```bash
python3 --version
# Should show: Python 3.11.x
```

### Kernel Version

**Recommended:** Kernel 6.6.31 or later

```bash
uname -r
# Should show: 6.x.x or higher
```

If older:
```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

### Architecture

**Required:** 64-bit ARM (aarch64)

```bash
uname -m
# Must show: aarch64
```

If you see `armv7l` or `arm64`, you're running 32-bit OS and must reinstall with 64-bit version.

---

## Step 1: Audio Hardware Detection

Before proceeding, verify your audio hardware is detected and determine its capabilities.

### Detect Audio Device

```bash
# List all audio capture devices
arecord -l

# Example outputs:
# For Google Voice HAT:
# card 0: sndrpigooglevoi [snd_rpi_googlevoicehat_soundcar]
#
# For INMP441 I2S mics:
# card 0: seeed2micvoicec [seeed-2mic-voicecard]
```

### Test Audio Capabilities

```bash
# Dump hardware parameters to see what formats are supported
arecord --dump-hw-params -D plughw:0,0
```

Look for these lines in the output:
- **RATE**: Supported sample rates (e.g., 16000, 44100, 48000)
- **CHANNELS**: Supported channel count (1=mono, 2=stereo)

### Test Recording

Try recording a 3-second test file:

```bash
# For Google Voice HAT (typically 16kHz mono):
arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 -d 3 test.wav

# For INMP441 I2S mics (typically 48kHz stereo):
arecord -D plughw:0,0 -f S16_LE -r 48000 -c 2 -d 3 test.wav

# Play back to verify
aplay test.wav
```

**Important:** Note the working sample rate and channel count - you'll need to configure `transcribe-halo.py` to match your hardware.

### Common Audio Hardware Configurations

| Hardware | Sample Rate | Channels | arecord Command |
|----------|------------|----------|-----------------|
| **Google Voice HAT** | 16000 Hz | 1 (mono) | `arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1` |
| **INMP441 I2S (2 mics)** | 48000 Hz | 2 (stereo) | `arecord -D plughw:0,0 -f S16_LE -r 48000 -c 2` |
| **USB Microphone** | 44100 Hz | 1 (mono) | `arecord -D plughw:1,0 -f S16_LE -r 44100 -c 1` |

---

## Step 2: Installing HailoRT

### Installation

The **hailo-all** package includes everything you need:
- HailoRT runtime library
- Python bindings (hailo_platform module)
- Kernel driver (hailo-dkms)
- Firmware tools

```bash
# Update system
sudo apt update
sudo apt full-upgrade -y

# Install Hailo packages
sudo apt install -y hailo-all

# Reboot to load kernel driver
sudo reboot
```

### Verify Installation

After reboot, verify everything is working:

```bash
# 1. Check hardware detection
lspci | grep -i hailo
# Expected: "Hailo Technologies Ltd. Hailo-8 AI Processor"

# 2. Verify HailoRT
hailortcli fw-control identify
# Expected: Shows device info (Hailo-8L, firmware version, serial number)

# 3. Check Python bindings (system-wide)
python3 -c "from hailo_platform import HEF; print('PyHailoRT OK')"
# Expected: "PyHailoRT OK"

# 4. Verify kernel driver
lsmod | grep hailo
# Expected: Shows hailo_pci module loaded
```

**Troubleshooting:**

If `hailortcli` command not found:
```bash
dpkg -l | grep hailort
# Should show hailort and python3-hailort packages installed
```

If no Hailo device detected:
```bash
lspci  # Check if any PCIe devices are detected
# Verify HAT is properly seated and Pi is powered adequately
```

---

## Step 3: Clone Project Repository

```bash
# Navigate to home directory
cd ~

# Clone the project
git clone https://github.com/shreyashguptas/sbc-audio-transcription.git

# Navigate to Raspberry Pi 5 directory
cd sbc-audio-transcription/raspberry-pi-5

# Verify files are present
ls -l
# Should show: transcribe-halo.py, requirements.txt, HAILO_SETUP.md, etc.
```

---

## Step 4: Virtual Environment Setup

**CRITICAL:** The virtual environment **MUST** be created with the `--system-site-packages` flag to access the system-installed `hailo_platform` module.

### Why `--system-site-packages` is Required

- The `hailo_platform` module is installed system-wide via the `hailo-all` Debian package
- It cannot be installed via `pip` - it's only available as a system package
- Without `--system-site-packages`, your venv won't be able to import `hailo_platform`
- This flag allows the venv to access system packages while keeping project dependencies isolated

### Create Virtual Environment

```bash
# Ensure you're in the project directory
cd ~/sbc-audio-transcription/raspberry-pi-5

# Create venv with system site packages access
python3.11 -m venv --system-site-packages venv

# Activate the virtual environment
source venv/bin/activate

# You should see (venv) prefix in your prompt
```

### Verify Hailo Platform Access

```bash
# Test that hailo_platform is accessible from venv
python -c "from hailo_platform import HEF; print('✓ hailo_platform accessible')"
# Expected: "✓ hailo_platform accessible"
```

If you get `ModuleNotFoundError`, your venv was likely created without `--system-site-packages`. Delete it and recreate:

```bash
deactivate  # Exit venv
rm -rf venv  # Remove old venv
python3.11 -m venv --system-site-packages venv  # Recreate with flag
source venv/bin/activate
```

---

## Step 5: Install Python Dependencies

With the virtual environment activated, install project dependencies:

```bash
# Ensure venv is activated (you should see (venv) in prompt)
# If not: source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install all project dependencies
pip install -r requirements.txt
```

### What Gets Installed

The `requirements.txt` includes:
- **soundfile** - Audio file I/O
- **scipy** - Signal processing (resampling)
- **numpy** - Array operations
- **simple-term-menu** - Interactive configuration menus
- **transformers** - Whisper tokenizer
- **torch** - Audio preprocessing
- **sounddevice** - Audio device interaction

**Note:** Some packages like `numpy` may show warnings about system packages - this is normal with `--system-site-packages`.

### Verify Installation

```bash
# Check key imports
python -c "import soundfile, scipy, numpy, transformers, torch; print('✓ All dependencies installed')"
# Expected: "✓ All dependencies installed"
```

---

## Step 6: Setting Up Hailo Application Code Examples

The official Hailo repository contains pre-trained Whisper models and inference code that our script uses.

### Clone Repository

```bash
cd ~
git clone https://github.com/hailo-ai/Hailo-Application-Code-Examples.git
cd Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition
```

### Run Setup Script

This downloads all Whisper HEF models and installs Hailo-specific dependencies:

```bash
python3 setup.py
```

**What this does:**
1. Creates its own virtual environment: `whisper_env/` (separate from your project venv)
2. Installs Python dependencies in whisper_env
3. Downloads HEF model files (~400MB total):
   - Tiny model encoder + decoder (for Hailo-8L)
   - Base model encoder + decoder (for Hailo-8L)
   - Files stored in `hefs/h8l/` directory
4. Downloads tokenization assets (~180MB)

**Time required:** 5-15 minutes depending on internet speed

**Note:** The Hailo repository creates its own `whisper_env`, but you don't need to activate it. Your project's venv will import the Hailo modules by adding the Hailo path to `sys.path`.

### Verify Setup

```bash
# Check HEF files were downloaded
ls ~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition/hefs/h8l/

# Expected structure:
# base/
#   base-whisper-encoder-5s_h8l.hef
#   base-whisper-decoder-fixed-sequence-matmul-split_h8l.hef
# tiny/
#   tiny-whisper-encoder-10s_15dB_h8l.hef
#   tiny-whisper-decoder-fixed-sequence-matmul-split_h8l.hef
```

---

## Step 7: Configure Audio for Your Hardware

The `transcribe-halo.py` script needs to be configured to match your audio hardware's capabilities.

### Check Current Configuration

Open `transcribe-halo.py` and look for the `arecord` command (around line 482-486):

```python
result = subprocess.run(
    ['arecord', '-D', 'plughw:0,0', '-f', 'S16_LE',
     '-r', '48000', '-c', '2', '-d', str(config.chunk_duration), audio_file],
    ...
)
```

### Update for Your Hardware

**For Google Voice HAT (16kHz mono):**
Change line ~483 to:
```python
     '-r', '16000', '-c', '1', '-d', str(config.chunk_duration), audio_file],
```

**For INMP441 I2S mics (48kHz stereo):**
Keep as is:
```python
     '-r', '48000', '-c', '2', '-d', str(config.chunk_duration), audio_file],
```

**For USB microphone (44.1kHz mono):**
Change line ~483 to:
```python
     '-r', '44100', '-c', '1', '-d', str(config.chunk_duration), audio_file],
```

**Note:** The script will automatically handle resampling to 16kHz (Whisper requirement) and channel mixing. You just need to match what your hardware supports for recording.

### Test Audio Recording

Before running the full script, test that audio recording works:

```bash
# From your project directory with venv activated
cd ~/sbc-audio-transcription/raspberry-pi-5
source venv/bin/activate

# Test recording (adjust -r and -c to match your hardware)
arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 -d 3 test.wav

# Play back
aplay test.wav

# Clean up
rm test.wav
```

---

## Step 8: Running transcribe-halo.py

Now you're ready to run the transcription script!

### Activate Environment and Run

```bash
# Navigate to project directory
cd ~/sbc-audio-transcription/raspberry-pi-5

# Activate virtual environment
source venv/bin/activate

# Run the script
python transcribe-halo.py
```

### Interactive Configuration Menu

You'll see an interactive menu to configure transcription:

1. **Preset Selection:**
   - **Fastest** - Tiny model, 10s chunks (2-5x real-time speed)
   - **Balanced** - Base model, 5s chunks (1.5-3x real-time) [Recommended]
   - **Custom** - Configure all options manually

2. **Model Selection** (if Custom):
   - `tiny` - Fastest, basic accuracy (39M parameters)
   - `base` - Better accuracy, still fast (74M parameters)

3. **Audio Processing** (if Custom):
   - Overlap duration (1-3 seconds)
   - Microphone gain (10-50x) - adjust if audio is too quiet/loud
   - Energy threshold - filters out silence

### Expected Output

```
======================================================================
  HAILO AI HAT WHISPER TRANSCRIPTION TOOL
  Hardware-accelerated speech-to-text on Hailo-8L
======================================================================

Loading base model on HAILO8L hardware...
Encoder HEF: base-whisper-encoder-5s_h8l.hef
Decoder HEF: base-whisper-decoder-fixed-sequence-matmul-split_h8l.hef

======================================================================
  TRANSCRIPTION ACTIVE (HAILO ACCELERATED)
======================================================================

Ready! Speak naturally - transcription will flow continuously.
Press Ctrl+C to stop

NOTE: Using Hailo AI HAT with base model
----------------------------------------------------------------------

[Your transcription appears here in real-time]
```

### Usage

- **Speak naturally** into your microphone
- Transcription appears in **real-time** as you speak
- **Ctrl+C** to stop and see performance statistics

### Performance Statistics

When you stop (Ctrl+C), you'll see:

```
======================================================================
  PERFORMANCE STATISTICS
======================================================================

Configuration: Hailo HAILO8L, base model
Total Runtime: 60.5s
Total Audio Processed: 105.0s
Total Words Transcribed: 234
Speed Factor: 1.74x real-time

======================================================================
Transcription stopped
======================================================================
```

**Speed Factor explained:**
- **< 1.0x** = Slower than real-time (falling behind)
- **= 1.0x** = Exactly real-time
- **> 1.0x** = Faster than real-time (can handle continuous speech)

---

## Performance Notes

### Expected Performance (Hailo-8L)

| Model | Chunk Size | Expected Speed | Accuracy | Best For |
|-------|-----------|----------------|----------|----------|
| `tiny` | 10 seconds | 2-5x real-time | Basic | Maximum speed |
| `base` | 5 seconds | 1.5-3x real-time | Good | Balanced (recommended) |

### Factors Affecting Performance

1. **Model size**: Tiny is faster, base is more accurate
2. **Chunk duration**: Longer chunks = more context but higher latency
3. **Background noise**: Clean audio = better accuracy
4. **CPU usage**: Preprocessing still runs on CPU (torch)
5. **Power supply**: Inadequate power can throttle Hailo accelerator

### Monitoring Hailo

```bash
# Check Hailo temperature
watch -n 1 hailortcli fw-control temp-info

# Monitor Hailo in top
htop
# Look for hailort process - CPU usage should be LOW (most work on Hailo)
```

### Current Limitations

- **English only**: Current HEF models support English language only
- **Torch dependency**: Audio preprocessing requires PyTorch (will be removed in future Hailo updates)
- **Two models**: Only tiny and base variants available (no small/medium/large)
- **Fixed chunk sizes**: Tiny uses 10s, base uses 5s (determined by HEF compilation)

---

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'hailo_platform'`

**Cause:** Virtual environment created without `--system-site-packages` flag.

**Solution:**
```bash
cd ~/sbc-audio-transcription/raspberry-pi-5
deactivate  # If venv is active
rm -rf venv
python3.11 -m venv --system-site-packages venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue: `audio open error: Invalid argument` when recording

**Cause:** Audio parameters don't match hardware capabilities.

**Solution:**
1. Detect what your hardware supports:
   ```bash
   arecord --dump-hw-params -D plughw:0,0 2>&1 | grep -E "RATE|CHANNELS"
   ```

2. Test recording with supported parameters:
   ```bash
   # Try 16kHz mono (Google Voice HAT)
   arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 -d 3 test.wav

   # Or try 48kHz stereo (INMP441)
   arecord -D plughw:0,0 -f S16_LE -r 48000 -c 2 -d 3 test.wav
   ```

3. Update `transcribe-halo.py` line ~483 to match working parameters.

### Issue: `Input buffer size 0 is different than expected`

**Cause:** Audio preprocessing pipeline returning empty mel spectrograms.

**Solution:**
1. Check debug output - the script now shows audio array sizes
2. Verify ffmpeg is installed: `sudo apt install -y ffmpeg`
3. Check that Hailo's `load_audio()` function is working correctly
4. Verify audio file is not empty after recording

### Issue: Hailo device not detected

**Solution:**
```bash
# Check if Hailo HAT is visible on PCIe bus
lspci | grep -i hailo

# If not visible:
# 1. Power off completely
sudo poweroff
# 2. Check HAT is properly seated
# 3. Ensure adequate power supply (27W recommended)
# 4. Power on and check again
```

### Issue: `hailortcli: command not found`

**Solution:**
```bash
# Verify hailo packages are installed
dpkg -l | grep hailo

# If not installed:
sudo apt update
sudo apt install -y hailo-all
sudo reboot
```

### Issue: Low transcription accuracy

**Solutions:**
1. **Increase microphone gain** in the configuration menu (try 40-50x)
2. **Use base model** instead of tiny for better accuracy
3. **Reduce background noise** - get closer to microphone
4. **Check microphone positioning** - should point toward sound source
5. **Test audio quality**: Record and play back to verify clear audio

### Issue: Slow performance (< 1.0x real-time)

**Solutions:**
1. **Use tiny model** for faster processing
2. **Check power supply** - use official 27W adapter
3. **Monitor temperature**: `hailortcli fw-control temp-info`
4. **Close other applications** to free CPU for preprocessing
5. **Verify Hailo is being used**: Check that HEF models loaded successfully

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    transcribe-halo.py                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Microphone] → [arecord at native rate/channels]              │
│         ↓                                                       │
│  [Hailo load_audio() - resample to 16kHz, convert to mono]    │
│         ↓                                                       │
│  [Apply gain adjustment]                                       │
│         ↓                                                       │
│  [Official Hailo Preprocessing]                                │
│         ↓                                                       │
│  [Generate Mel Spectrogram - 80 bins]                          │
│         ↓                                                       │
│  ┌─────────────────────────────────────┐                       │
│  │   Hailo-8L AI Accelerator (PCIe)    │                       │
│  │                                      │                       │
│  │  Encoder HEF → Decoder HEF           │                       │
│  │     (Hardware acceleration)          │                       │
│  └─────────────────────────────────────┘                       │
│         ↓                                                       │
│  [Tokenizer - Decode to text]                                  │
│         ↓                                                       │
│  [Postprocessing - Remove repetitions]                         │
│         ↓                                                       │
│  [Deduplication - Handle overlaps]                             │
│         ↓                                                       │
│  [Display real-time transcription]                             │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

1. **Your code** (transcribe-halo.py):
   - Interactive menu system
   - Audio recording via arecord
   - Gain adjustment
   - Deduplication logic for overlapping chunks
   - Performance tracking

2. **Official Hailo code** (imported):
   - `HailoWhisperPipeline` - Manages Hailo inference
   - `load_audio()` - Handles format conversion and resampling
   - `preprocess()` - Generates mel spectrograms
   - Tokenization (Whisper tokenizer from transformers)
   - Post-processing (repetition removal, text cleaning)

3. **Hailo hardware**:
   - Encoder and decoder run on Hailo-8L accelerator
   - PCIe interface for low latency
   - ~10W power consumption during inference

---

## Comparison: CPU vs Hailo

| Feature | transcribe.py (CPU) | transcribe-halo.py (Hailo) |
|---------|-------------------|--------------------------|
| **Hardware** | Raspberry Pi 5 CPU | Hailo-8L accelerator |
| **Models** | All sizes (tiny → large-v3) | tiny, base only |
| **Languages** | 100+ languages | English only (current) |
| **Speed (base)** | 1-2x real-time | 1.5-3x real-time |
| **Power** | ~8-12W | ~15-18W (CPU + Hailo) |
| **Setup** | pip install | Requires hailo-all + setup |
| **Flexibility** | Highly configurable | Fixed models |

**When to use each:**

- **Use transcribe.py (CPU):**
  - Need multilingual support
  - Want larger models (small/medium/large)
  - Prefer maximum flexibility
  - Don't have Hailo HAT

- **Use transcribe-halo.py (Hailo):**
  - English-only transcription
  - Need maximum speed
  - Have Hailo HAT installed
  - Want to offload CPU

---

## File Locations Reference

| Description | Path |
|------------|------|
| **Your project** | `~/sbc-audio-transcription/raspberry-pi-5/` |
| **Project venv** | `~/sbc-audio-transcription/raspberry-pi-5/venv/` |
| **transcribe-halo.py** | `~/sbc-audio-transcription/raspberry-pi-5/transcribe-halo.py` |
| **requirements.txt** | `~/sbc-audio-transcription/raspberry-pi-5/requirements.txt` |
| **Hailo repo** | `~/Hailo-Application-Code-Examples/` |
| **Whisper code** | `~/Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition/` |
| **Hailo's venv** | `~/Hailo-Application-Code-Examples/.../whisper_env/` (separate from yours) |
| **HEF models** | `~/Hailo-Application-Code-Examples/.../hefs/h8l/base/` |
| **Tokenization assets** | `~/Hailo-Application-Code-Examples/.../decoder_assets/base/` |

---

## Useful Commands Reference

```bash
# === Hailo ===
# Check Hailo status
hailortcli fw-control identify

# Monitor temperature
hailortcli fw-control temp-info

# List all Hailo packages
dpkg -l | grep hailo

# === Audio ===
# List capture devices
arecord -l

# Test what formats hardware supports
arecord --dump-hw-params -D plughw:0,0

# Test recording (adjust -r and -c for your hardware)
arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 -d 3 test.wav

# Play back recorded audio
aplay test.wav

# === Virtual Environment ===
# Activate project venv
cd ~/sbc-audio-transcription/raspberry-pi-5 && source venv/bin/activate

# Deactivate venv
deactivate

# Recreate venv if needed
rm -rf venv && python3.11 -m venv --system-site-packages venv

# === System ===
# Check OS version
cat /etc/os-release

# Check Python version
python3 --version

# Check architecture
uname -m

# Update system
sudo apt update && sudo apt full-upgrade -y
```

---

## Additional Resources

### Documentation

- **Hailo Developer Zone:** https://hailo.ai/developer-zone/
- **Hailo Community:** https://community.hailo.ai/
- **Official Examples:** https://github.com/hailo-ai/Hailo-Application-Code-Examples
- **Raspberry Pi Documentation:** https://www.raspberrypi.com/documentation/

### Getting Help

1. **Check the debug output** - The script shows detailed information about audio processing
2. **Verify each step** - Use the verification commands after each section
3. **Check audio hardware first** - Most issues are audio-related
4. **Ensure proper power supply** - Inadequate power causes random failures
5. **Ask the community** - Hailo Community forums are very responsive

---

**Last Updated:** 2025-11-22
**Python Version:** 3.11.2
**Raspberry Pi:** Pi 5
**Hailo HAT:** Hailo-8L (13 TOPS)
**Models:** tiny, base (English only)
**OS:** Raspberry Pi OS Bookworm (64-bit)
