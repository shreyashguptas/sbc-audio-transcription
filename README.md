# Hailo-Accelerated Whisper Transcription on Raspberry Pi 5

Real-time speech-to-text transcription using OpenAI's Whisper model accelerated by the Hailo-8L AI processor on Raspberry Pi 5 with ReSpeaker 2-Mic Pi HAT.

**Features:**
- ⚡ Hardware-accelerated inference with Hailo-8L (13 TOPS)
- 🎤 High-quality 16kHz stereo audio recording with ReSpeaker 2-Mic HAT
- 🔄 Real-time continuous transcription
- 💻 CPU fallback mode available
- 🎯 Optimized for Raspberry Pi 5 with kernel 6.12+

---

## Hardware Requirements

### Essential Components
- **Raspberry Pi 5** (4GB or 8GB RAM)
- **Hailo AI HAT** (M.2 HAT+ with Hailo-8L accelerator)
- **KEYESTUDIO ReSpeaker 2-Mic Pi HAT** (shield for Raspberry Pi)
- **Official 27W USB-C Power Supply** (required for stable Hailo operation)
- **32GB+ MicroSD Card** with Raspberry Pi OS Bookworm 64-bit

### Hardware Setup
The ReSpeaker 2-Mic HAT is a plug-and-play shield that stacks directly on top of the Raspberry Pi GPIO pins. No wiring needed!

**Installation:**
1. Power off your Raspberry Pi 5
2. Stack the Hailo AI HAT on the M.2 slot (bottom layer)
3. Stack the ReSpeaker 2-Mic HAT on the GPIO pins (top layer)
4. Ensure all pins are properly aligned and seated
5. Power on the Raspberry Pi

---

## System Prerequisites

### Operating System
**Required:** Raspberry Pi OS Bookworm (64-bit)

```bash
# Verify your OS
cat /etc/os-release | grep VERSION_CODENAME
# Must show: VERSION_CODENAME=bookworm

uname -m
# Must show: aarch64
```

⚠️ **Important:** Hailo packages are ONLY available for Debian 12 (Bookworm). Other versions are not supported.

### Python Version
**Required:** Python 3.11

```bash
python3 --version
# Must show: Python 3.11.x
```

---

## Installation

### Step 1: Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt full-upgrade -y

# Install HailoRT (includes runtime, drivers, Python bindings)
sudo apt install -y hailo-all

# Install system Python packages
sudo apt install -y python3-full python3-dev python3-pip

# Install audio dependencies
sudo apt install -y alsa-utils libsndfile1

# Reboot to load Hailo kernel driver
sudo reboot
```

### Step 2: Install ReSpeaker 2-Mic HAT Drivers

The ReSpeaker HAT uses a WM8960 audio codec that requires special drivers for Raspberry Pi 5.

**Important:** The original `respeaker/seeed-voicecard` drivers have compatibility issues with Pi 5:
- Pi 5's RP1 chip doesn't provide MCLK (Master Clock) like older Pis
- Kernel 6.12+ has API changes that break the original drivers

**Use the automated installer (Recommended):**

```bash
# From this repository directory
cd ~/sbc-audio-transcription
sudo ./install-pi5.sh

# Reboot to load the drivers
sudo reboot
```

**Or install manually:**

```bash
# Clone the HinTak fork (kernel 6.12 compatible)
cd ~
git clone https://github.com/HinTak/seeed-voicecard
cd seeed-voicecard
git checkout v6.12

# Install the drivers
sudo ./install.sh

# Reboot to load the drivers
sudo reboot
```

**Note:** The `install-pi5.sh` script handles all dependencies, configuration, and uses the correct driver fork automatically.

### Step 3: Verify Hailo Hardware

```bash
# Check PCIe detection
lspci | grep -i hailo
# Expected: "Hailo Technologies Ltd. Hailo-8 AI Processor"

# Verify firmware
hailortcli fw-control identify
# Expected: Device info with Hailo-8L, firmware version, serial number

# Check Python bindings (system-wide)
python3 -c "from hailo_platform import HEF; print('Hailo Python bindings OK')"
# Expected: "Hailo Python bindings OK"
```

### Step 4: Verify Audio Hardware

```bash
# List audio devices
arecord -l
# Expected: card 0: seeed2micvoicec [seeed-2mic-voicecard]

# Test 16kHz stereo recording (5 seconds) - 16kHz is optimal for Whisper
arecord -D plughw:0,0 -f S16_LE -r 16000 -c 2 -d 5 ~/test-recording.wav

# Check file was created
ls -lh ~/test-recording.wav
# Expected: ~320KB file (5 sec * 16000 Hz * 2 ch * 2 bytes)
```

**To test audio on your Mac:**

```bash
# On your Mac, copy the test file from the Raspberry Pi:
scp shreyash@pi-5-1:~/test-recording.wav /Users/shreyashgupta/Desktop/pi-audio-test/

# Play it:
afplay /Users/shreyashgupta/Desktop/pi-audio-test/test-recording.wav
```

### Step 5: Clone Hailo Examples

```bash
cd ~
git clone https://github.com/hailo-ai/Hailo-Application-Code-Examples.git
cd Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition

# Download Whisper model files (tiny model for Hailo-8L)
python3 setup.py
```

### Step 6: Clone This Repository

```bash
cd ~
git clone https://github.com/shreyashguptas/sbc-audio-transcription.git
cd sbc-audio-transcription
```

### Step 7: Create Virtual Environment

⚠️ **REQUIRED:** Use `--system-site-packages` flag to access system-installed Hailo packages (`hailo_platform`). This is the official Hailo standard for Raspberry Pi 5.

⚠️ **NOTE:** PyTorch 2.6.0 is required and included in `requirements.txt`. This matches the official Hailo speech recognition setup.

```bash
# Create Python 3.11 virtual environment with system site packages
# This allows access to HailoRT Python bindings installed via apt
python3 -m venv --system-site-packages venv

# Activate it
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies (includes PyTorch 2.6.0)
pip install -r requirements.txt
```

---

## Running Transcription

### Hailo-Accelerated Mode (Recommended)

```bash
cd ~/sbc-audio-transcription
source venv/bin/activate
python transcribe-halo.py
```

**Features:**
- Hardware-accelerated inference on Hailo-8L
- Real-time continuous transcription
- 16kHz stereo audio recording (Whisper's native rate)
- Automatic chunking with overlap
- Low latency

### CPU Mode (Fallback)

```bash
cd ~/sbc-audio-transcription
source venv/bin/activate
python transcribe.py
```

**When to use:**
- Testing without Hailo hardware
- Debugging audio issues
- Comparing accuracy

---

## Configuration

Audio and processing parameters are configured in `transcribe-halo.py`:

```python
class HailoTranscriptionConfig:
    # Audio hardware (16kHz stereo - optimal for Whisper)
    audio_sample_rate = 16000  # Hz (Whisper's native rate)
    audio_channels = 2         # Stereo

    # Processing
    chunk_duration = 10        # seconds (for tiny model)
    overlap_duration = 2       # seconds
    gain = 30.0               # Microphone gain multiplier
    min_audio_energy = 0.0002 # Energy threshold for silence detection

    # Hailo hardware
    hw_arch = 'hailo8l'       # For Raspberry Pi 5 AI HAT
    model_variant = 'tiny'    # tiny or base
```

---

## Known Issues & Solutions

### Issue: "Input buffer size 0" Error

**Cause:** This error typically occurs when the virtual environment is not set up correctly or when using incompatible PyTorch versions.

**Solution:**
1. Ensure you're using `--system-site-packages` when creating the venv
2. Use the exact PyTorch version from requirements.txt (2.6.0)
3. Recreate the environment:
   ```bash
   rm -rf venv
   python3 -m venv --system-site-packages venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

**Verify correct setup:**
```bash
source venv/bin/activate
python3 -c "import torch; import hailo_platform; print(f'torch: {torch.__version__}, hailo: OK')"
# Should print: torch: 2.6.0, hailo: OK
```

### Issue: "No module named 'hailo_platform'" Error

**Cause:** Virtual environment was created WITHOUT `--system-site-packages` flag, blocking access to system-installed HailoRT Python bindings.

**Solution:**
1. Delete the existing venv: `rm -rf venv`
2. Recreate with system site packages:
   ```bash
   cd ~/sbc-audio-transcription
   python3 -m venv --system-site-packages venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

**Verify Hailo access:**
```bash
source venv/bin/activate
python3 -c "import hailo_platform; print('Hailo OK')"
# Should print: Hailo OK
```

**Why this flag is needed:** On Raspberry Pi 5, HailoRT is installed system-wide via `sudo apt install hailo-all`. The `--system-site-packages` flag allows the venv to access these system packages while still maintaining isolation for pip-installed packages. This is the official Hailo standard for RPi5.

### Issue: Audio Recording Fails

**Check driver loading:**
```bash
lsmod | grep snd
arecord -l
```

**Check for "No MCLK configured" error:**
```bash
dmesg | grep -i mclk
```

If you see `wm8960 1-001a: No MCLK configured`, you're using incompatible drivers. Fix by reinstalling with the HinTak fork:

```bash
cd ~
git clone https://github.com/HinTak/seeed-voicecard
cd seeed-voicecard
git checkout v6.12
sudo ./install.sh
sudo reboot
```

**Verify config.txt:**
```bash
cat /boot/firmware/config.txt | grep -E 'seeed|voice'
```

Should show ReSpeaker device tree overlays:
```
dtoverlay=seeed-2mic-voicecard
```

### Issue: Hailo Not Detected

**Check PCIe:**
```bash
lspci | grep -i hailo
dmesg | grep -i hailo
```

**Reinstall driver:**
```bash
sudo apt install --reinstall hailo-all
sudo reboot
```

---

## Audio Quality Tips

1. **Microphone Placement:** The ReSpeaker HAT has dual omnidirectional microphones. Position the Raspberry Pi 15-30cm from the speaker for best results
2. **Gain Adjustment:** Modify `self.gain = 30.0` in config if audio is too quiet/loud
3. **Test Recording:**
   ```bash
   # Adjust ReSpeaker HAT gain (if needed)
   amixer -c 0 set Capture 80%

   # The ReSpeaker HAT also has onboard LEDs that indicate audio activity
   ```
4. **Verify Stereo:** Both channels should show waveforms in audio analysis tools

---

## Project Structure

```
sbc-audio-transcription/
├── README.md                 # This file - comprehensive setup guide
├── install-pi5.sh            # Automated driver installer for Pi 5 + kernel 6.12
├── requirements.txt          # Python dependencies
├── transcribe-halo.py        # Hailo-accelerated transcription
├── transcribe.py             # CPU fallback version
└── .gitignore               # Git ignore rules
```

---

## Technical Details

### Audio Pipeline
1. **Recording:** arecord → 16kHz stereo S16_LE (native Whisper rate)
2. **Preprocessing:** Convert to mono (Whisper requirement)
3. **Feature Extraction:** Convert to mel spectrogram
4. **Inference:** Hailo-8L accelerated encoder/decoder
5. **Postprocessing:** Token to text conversion

### Hailo Models
- **Encoder:** `tiny-whisper-encoder-10s_15dB_h8l.hef`
- **Decoder:** `tiny-whisper-decoder-fixed-sequence-matmul-split_h8l.hef`
- **Quantization:** INT8 for Hailo-8L
- **Chunk Size:** 10 seconds (tiny model)

### Performance
- **Hailo-8L (13 TOPS):** ~2-3x real-time (processes 10s audio in ~3-5s)
- **CPU Only:** ~0.1x real-time (very slow)
- **Latency:** 3-5 seconds from speech to transcription

---

## Troubleshooting

### Debug Audio

```bash
# Test microphone levels with ReSpeaker HAT (16kHz for Whisper compatibility)
arecord -D plughw:0,0 -f S16_LE -r 16000 -c 2 -d 10 ~/test-debug.wav

# Check file size (should be ~640KB for 10 seconds at 16kHz stereo)
ls -lh ~/test-debug.wav

# Copy to Mac for playback testing
scp shreyash@pi-5-1:~/test-debug.wav /Users/shreyashgupta/Desktop/pi-audio-test/
```

### Check Hailo Logs

```bash
# Real-time logs
tail -f ~/sbc-audio-transcription/hailort.log

# Search for errors
grep -i error ~/sbc-audio-transcription/hailort.log
```

### Verify Dependencies

```bash
source venv/bin/activate

# Check for conflicts
pip list | grep -E 'torch|tensorflow|keras'
# Should be EMPTY!

# Verify required packages
pip list | grep -E 'numpy|soundfile|transformers|scipy'
```

---

## Contributing

Contributions welcome! Please ensure:
1. Code works on Raspberry Pi 5 with Hailo-8L
2. No PyTorch/TensorFlow dependencies added
3. Audio tested at 48kHz stereo
4. Documentation updated

---

## License

MIT License - See LICENSE file for details

---

## Acknowledgments

- [Hailo AI](https://hailo.ai/) for the Hailo-8L accelerator and examples
- [OpenAI](https://openai.com/) for the Whisper model
- [Raspberry Pi Foundation](https://www.raspberrypi.org/) for the incredible Pi 5 hardware
- [HinTak](https://github.com/HinTak/seeed-voicecard) for the kernel 6.12 compatible seeed-voicecard driver fork
- [Seeed Studio](https://www.seeedstudio.com/) for the ReSpeaker 2-Mic HAT

---

## Support

**Issues?** Open a GitHub issue with:
- Error messages
- Output of `hailortcli fw-control identify`
- Output of `arecord -l`
- Python version: `python3 --version`
- OS version: `cat /etc/os-release`
