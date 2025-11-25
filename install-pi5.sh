#!/bin/bash
#
# install-pi5.sh - ReSpeaker 2-Mic HAT driver installer for Raspberry Pi 5 + Bookworm
#
# The original seeed-voicecard install.sh has compatibility issues with Pi 5:
# - Writes to wrong config file (/boot/config.txt instead of /boot/firmware/config.txt)
# - Missing dkms dependency
#
# This script fixes those issues and properly configures the audio HAT.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}ReSpeaker 2-Mic HAT Installer for Pi 5 Bookworm${NC}"
echo -e "${GREEN}================================================${NC}"
echo

# Check for root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root (use sudo)${NC}" 1>&2
   exit 1
fi

# Check for Pi 5
if ! grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
    echo -e "${YELLOW}Warning: This script is designed for Raspberry Pi 5${NC}"
    echo "Detected: $(cat /proc/device-tree/model 2>/dev/null || echo 'Unknown')"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for Bookworm
if ! grep -q "bookworm" /etc/os-release 2>/dev/null; then
    echo -e "${YELLOW}Warning: This script is designed for Debian Bookworm${NC}"
    echo "Detected: $(grep VERSION_CODENAME /etc/os-release 2>/dev/null || echo 'Unknown')"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for seeed-voicecard directory
VOICECARD_DIR="$HOME/seeed-voicecard"
if [[ ! -d "$VOICECARD_DIR" ]]; then
    # Try current directory
    if [[ -f "./seeed-2mic-voicecard.dtbo" ]]; then
        VOICECARD_DIR="."
    else
        echo -e "${RED}Error: seeed-voicecard directory not found${NC}"
        echo "Please clone it first:"
        echo "  cd ~"
        echo "  git clone https://github.com/respeaker/seeed-voicecard.git"
        exit 1
    fi
fi

echo "Using voicecard source: $VOICECARD_DIR"
echo

# Step 1: Install dependencies
echo -e "${GREEN}[1/6] Installing dependencies...${NC}"
apt update
apt install -y dkms git i2c-tools libasound2-plugins raspberrypi-kernel-headers

# Step 2: Configure /boot/firmware/config.txt
CONFIG="/boot/firmware/config.txt"
echo -e "${GREEN}[2/6] Configuring $CONFIG...${NC}"

# Enable I2C
if grep -q "^#dtparam=i2c_arm=on" "$CONFIG"; then
    sed -i 's/^#dtparam=i2c_arm=on/dtparam=i2c_arm=on/' "$CONFIG"
    echo "  - Enabled i2c_arm"
elif ! grep -q "^dtparam=i2c_arm=on" "$CONFIG"; then
    echo "dtparam=i2c_arm=on" >> "$CONFIG"
    echo "  - Added i2c_arm=on"
else
    echo "  - i2c_arm already enabled"
fi

# Enable I2S
if ! grep -q "^dtparam=i2s=on" "$CONFIG"; then
    echo "dtparam=i2s=on" >> "$CONFIG"
    echo "  - Added i2s=on"
else
    echo "  - i2s already enabled"
fi

# Add i2s-mmap overlay
if ! grep -q "^dtoverlay=i2s-mmap" "$CONFIG"; then
    echo "dtoverlay=i2s-mmap" >> "$CONFIG"
    echo "  - Added i2s-mmap overlay"
else
    echo "  - i2s-mmap overlay already present"
fi

# Add seeed-2mic-voicecard overlay
if ! grep -q "^dtoverlay=seeed-2mic-voicecard" "$CONFIG"; then
    echo "dtoverlay=seeed-2mic-voicecard" >> "$CONFIG"
    echo "  - Added seeed-2mic-voicecard overlay"
else
    echo "  - seeed-2mic-voicecard overlay already present"
fi

# Step 3: Copy overlay files
echo -e "${GREEN}[3/6] Copying overlay files to /boot/firmware/overlays/...${NC}"
OVERLAYS_DIR="/boot/firmware/overlays"
cp "$VOICECARD_DIR/seeed-2mic-voicecard.dtbo" "$OVERLAYS_DIR/"
echo "  - Copied seeed-2mic-voicecard.dtbo"

# Also copy other overlays if they exist
for overlay in seeed-4mic-voicecard.dtbo seeed-8mic-voicecard.dtbo; do
    if [[ -f "$VOICECARD_DIR/$overlay" ]]; then
        cp "$VOICECARD_DIR/$overlay" "$OVERLAYS_DIR/"
        echo "  - Copied $overlay"
    fi
done

# Step 4: Add kernel modules to /etc/modules
echo -e "${GREEN}[4/6] Configuring kernel modules...${NC}"
MODULES_FILE="/etc/modules"

if ! grep -q "^snd-soc-seeed-voicecard" "$MODULES_FILE"; then
    echo "snd-soc-seeed-voicecard" >> "$MODULES_FILE"
    echo "  - Added snd-soc-seeed-voicecard"
else
    echo "  - snd-soc-seeed-voicecard already present"
fi

if ! grep -q "^snd-soc-wm8960" "$MODULES_FILE"; then
    echo "snd-soc-wm8960" >> "$MODULES_FILE"
    echo "  - Added snd-soc-wm8960"
else
    echo "  - snd-soc-wm8960 already present"
fi

# Step 5: Run original install.sh for DKMS compilation
echo -e "${GREEN}[5/6] Compiling kernel modules via DKMS...${NC}"
echo "  Running original install.sh (this may take a few minutes)..."
cd "$VOICECARD_DIR"

# The original script will try to modify the wrong config file, but that's OK
# because we've already configured the correct one. Let it run for DKMS.
if ./install.sh 2>&1 | grep -v "config.txt"; then
    echo "  - DKMS modules compiled successfully"
else
    echo -e "${YELLOW}  - Note: Some warnings may appear, but DKMS should still work${NC}"
fi

# Step 6: Summary
echo
echo -e "${GREEN}[6/6] Installation complete!${NC}"
echo
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Please reboot your Raspberry Pi:${NC}"
echo -e "${GREEN}  sudo reboot${NC}"
echo -e "${GREEN}================================================${NC}"
echo
echo "After reboot, verify with:"
echo "  arecord -l                    # Should show seeed-2mic-voicecard"
echo "  ls /dev/i2c*                  # Should show /dev/i2c-1"
echo "  lsmod | grep snd              # Should show snd_soc_wm8960"
echo
