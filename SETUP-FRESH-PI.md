# Fresh Raspberry Pi 5 Setup Guide for Hailo Whisper Transcription

This guide provides step-by-step instructions to set up a fresh Raspberry Pi 5 with the Hailo AI HAT and ReSpeaker 2-Mic Pi HAT for real-time speech transcription.

## Prerequisites

**Hardware assembled:**
- Raspberry Pi 5 (4GB or 8GB RAM)
- Hailo AI HAT (M.2 HAT+ with Hailo-8L) - installed in M.2 slot
- KEYESTUDIO ReSpeaker 2-Mic Pi HAT - stacked on GPIO pins
- 32GB+ MicroSD card with Raspberry Pi OS Bookworm 64-bit
- Official 27W USB-C power supply

**Software:**
- Fresh Raspberry Pi OS Bookworm (64-bit) installation
- Internet connection (Ethernet or Wi-Fi)

---

## Step 1: Verify System Requirements

```bash
# Verify OS version (must be Bookworm)
cat /etc/os-release | grep VERSION_CODENAME
# Expected output: VERSION_CODENAME=bookworm

# Verify architecture (must be 64-bit)
uname -m
# Expected output: aarch64

# Verify Python version (must be 3.11.x)
python3 --version
# Expected output: Python 3.11.x
```

If any of these don't match, you need to reinstall Raspberry Pi OS with the correct version.

---

## Step 2: Update System and Install Core Dependencies

```bash
# Update package lists and upgrade system
sudo apt update && sudo apt full-upgrade -y

# Install HailoRT (includes drivers, runtime, and Python bindings)
sudo apt install -y hailo-all

# Install Python development tools
sudo apt install -y python3-full python3-dev python3-pip

# Install audio system dependencies
sudo apt install -y alsa-utils libsndfile1

# Install git for cloning repositories
sudo apt install -y git

# Reboot to load Hailo kernel driver
sudo reboot
```

**Note:** After reboot, reconnect via SSH or terminal.

---

## Step 3: Install ReSpeaker 2-Mic HAT Drivers

```bash
# Clone the official ReSpeaker driver repository
cd ~
git clone https://github.com/respeaker/seeed-voicecard.git
cd seeed-voicecard

# Run the installation script
# This will automatically configure /boot/firmware/config.txt
sudo ./install.sh

# Reboot to load the ReSpeaker audio drivers
sudo reboot
```

**Note:** After reboot, reconnect via SSH or terminal.

---

## Step 4: Verify Hailo AI HAT

```bash
# Check if Hailo device is detected via PCIe
lspci | grep -i hailo
# Expected output: "Hailo Technologies Ltd. Hailo-8 AI Processor"

# Verify Hailo firmware
hailortcli fw-control identify
# Expected: Device information with Hailo-8L model, firmware version, serial number

# Test Hailo Python bindings
python3 -c "from hailo_platform import HEF; print('Hailo Python bindings: OK')"
# Expected output: Hailo Python bindings: OK
```

If any of these fail:
```bash
# Reinstall Hailo packages
sudo apt install --reinstall hailo-all
sudo reboot
```

---

## Step 5: Verify ReSpeaker 2-Mic HAT

```bash
# List audio capture devices
arecord -l
# Expected output should include: card 0: seeed2micvoicec [seeed-2mic-voicecard]

# Test 5-second stereo recording at 48kHz
arecord -D plughw:0,0 -f S16_LE -r 48000 -c 2 -d 5 ~/test-respeaker.wav

# Verify file was created and has correct size
ls -lh ~/test-respeaker.wav
# Expected: ~960KB file (5 sec * 48000 Hz * 2 channels * 2 bytes)
```

**To test audio playback on your Mac:**

```bash
# On your Mac, run this command to copy the audio file:
scp shreyash@pi-5-1:~/test-respeaker.wav /Users/shreyashgupta/Desktop/pi-audio-test/

# Then play it:
afplay /Users/shreyashgupta/Desktop/pi-audio-test/test-respeaker.wav
```

If you hear your voice, the microphones are working correctly!

---

## Step 6: Clone Hailo Example Repository

```bash
# Clone Hailo's official example code
cd ~
git clone https://github.com/hailo-ai/Hailo-Application-Code-Examples.git

# Navigate to the speech recognition example
cd Hailo-Application-Code-Examples/runtime/hailo-8/python/speech_recognition

# Run setup to download Whisper model files
python3 setup.py
# This downloads the Hailo-optimized Whisper HEF files (tiny and base models)
```

**Note:** This will download ~100-200MB of model files. Make sure you have internet connectivity.

---

## Step 7: Clone Your Transcription Project

```bash
# Clone your project repository
cd ~
git clone https://github.com/shreyashguptas/sbc-audio-transcription.git
cd sbc-audio-transcription

# Switch to the correct branch (if needed)
git checkout sleepy-dirac
```

---

## Step 8: Create Python Virtual Environment

**CRITICAL:** You MUST use `--system-site-packages` to access the system-installed HailoRT Python bindings.

```bash
# Create virtual environment with system site packages
python3 -m venv --system-site-packages venv

# Activate the virtual environment
source venv/bin/activate

# Upgrade pip to latest version
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt
```

**Verify installation:**

```bash
# Check that both PyTorch and Hailo are accessible
python3 -c "import torch; import hailo_platform; print(f'PyTorch: {torch.__version__}, Hailo: OK')"
# Expected output: PyTorch: 2.6.0, Hailo: OK
```

---

## Step 9: Run Your First Transcription

```bash
# Make sure you're in the project directory with venv activated
cd ~/sbc-audio-transcription
source venv/bin/activate

# Run the interactive transcription script
python transcribe-halo.py
```

You'll see an interactive menu where you can:
1. Choose preset configurations (Fastest, Balanced, Custom)
2. Select model variant (tiny or base)
3. Configure advanced options

**Recommended for first run:** Select "Balanced (base model, 5s chunks)"

The script will:
- Verify hardware (Hailo and audio devices)
- Test audio recording
- Initialize the Hailo pipeline
- Start continuous transcription

**To stop:** Press `Ctrl+C`

---

## Step 10: (Optional) Set Up Auto-Start on Boot

If you want transcription to start automatically when the Pi boots:

```bash
# Create a systemd service file
sudo nano /etc/systemd/system/hailo-transcribe.service
```

Add this content:

```ini
[Unit]
Description=Hailo Whisper Transcription Service
After=network.target sound.target

[Service]
Type=simple
User=shreyash
WorkingDirectory=/home/shreyash/sbc-audio-transcription
Environment="PATH=/home/shreyash/sbc-audio-transcription/venv/bin:/usr/bin"
ExecStart=/home/shreyash/sbc-audio-transcription/venv/bin/python /home/shreyash/sbc-audio-transcription/transcribe-halo.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

**Enable and start the service:**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable hailo-transcribe.service

# Start the service now
sudo systemctl start hailo-transcribe.service

# Check status
sudo systemctl status hailo-transcribe.service

# View logs
journalctl -u hailo-transcribe.service -f
```

---

## Troubleshooting

### Issue: "No module named 'hailo_platform'"

**Solution:** Recreate venv WITH `--system-site-packages`:

```bash
cd ~/sbc-audio-transcription
rm -rf venv
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue: "buffer size 0" Error

**Cause:** NumPy version incompatibility with Hailo C++ bindings.

**Solution:**

```bash
source venv/bin/activate
pip install --force-reinstall numpy==1.24.2
```

### Issue: No Audio Device Found

**Check driver installation:**

```bash
# Verify ReSpeaker driver loaded
lsmod | grep snd
# Should show multiple sound modules

# Check config.txt
cat /boot/firmware/config.txt | grep seeed
# Should show: dtoverlay=seeed-2mic-voicecard

# Reinstall drivers if needed
cd ~/seeed-voicecard
sudo ./install.sh
sudo reboot
```

### Issue: Hailo Not Detected

**Check PCIe connection:**

```bash
# Verify hardware detection
lspci | grep -i hailo
dmesg | grep -i hailo

# Reinstall Hailo software
sudo apt install --reinstall hailo-all
sudo reboot
```

### Issue: Audio Quality Poor

**Adjust microphone gain:**

```bash
# List available controls
amixer -c 0 controls

# Adjust capture volume (0-100%)
amixer -c 0 set Capture 80%

# You can also modify the gain parameter in transcribe-halo.py
# Look for: self.gain = 30.0 (line ~231 in config)
```

---

## Quick Reference Commands

**Activate virtual environment:**
```bash
cd ~/sbc-audio-transcription
source venv/bin/activate
```

**Run transcription:**
```bash
python transcribe-halo.py
```

**Test audio recording:**
```bash
arecord -D plughw:0,0 -f S16_LE -r 48000 -c 2 -d 5 test.wav
```

**Copy audio to Mac for testing:**
```bash
# On your Mac:
scp shreyash@pi-5-1:~/test.wav /Users/shreyashgupta/Desktop/pi-audio-test/
afplay /Users/shreyashgupta/Desktop/pi-audio-test/test.wav
```

**Check system status:**
```bash
# Hailo device
hailortcli fw-control identify

# Audio device
arecord -l

# Python packages
source venv/bin/activate
pip list | grep -E 'torch|numpy|hailo'
```

---

## Success Checklist

- [ ] Raspberry Pi OS Bookworm 64-bit installed
- [ ] Python 3.11.x installed
- [ ] Hailo AI HAT detected via `lspci`
- [ ] Hailo firmware verified via `hailortcli`
- [ ] ReSpeaker audio card detected via `arecord -l`
- [ ] Test recording successful
- [ ] Hailo example models downloaded
- [ ] Virtual environment created with `--system-site-packages`
- [ ] All requirements installed without errors
- [ ] `transcribe-halo.py` runs without errors
- [ ] Real-time transcription working

---

## Next Steps

Once everything is working:

1. **Optimize audio quality:** Adjust gain and VAD settings in the interactive menu
2. **Try different models:** Compare tiny (faster) vs base (more accurate)
3. **Monitor performance:** Use `htop` to check CPU/memory usage
4. **Save recordings:** Modify script to save transcriptions to files
5. **Integrate with other systems:** Use the transcription output in your applications

---

## Support

If you encounter issues not covered here:

1. Check the main README.md for detailed explanations
2. Review Hailo documentation: https://hailo.ai/developer-zone/
3. Check ReSpeaker wiki: https://wiki.seeedstudio.com/ReSpeaker_2_Mics_Pi_HAT/
4. Open an issue in the GitHub repository

---

**Last Updated:** 2025-11-25
**Hardware:** Raspberry Pi 5 + Hailo AI HAT + ReSpeaker 2-Mic Pi HAT
**Software:** Raspberry Pi OS Bookworm, Python 3.11, HailoRT
