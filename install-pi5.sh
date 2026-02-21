#!/bin/bash
#
# install-pi5.sh - Complete ReSpeaker 2-Mic HAT setup for Raspberry Pi 5 + Bookworm
#
# Usage:
#   1. Clone this repo: git clone https://github.com/shreyashguptas/sbc-audio-transcription.git
#   2. Run: cd sbc-audio-transcription && sudo ./install-pi5.sh
#   3. Reboot when prompted
#
# This script handles everything:
#   - Installs all dependencies (dkms, i2c-tools, kernel headers, etc.)
#   - Clones the HinTak/seeed-voicecard driver (kernel 6.12 compatible fork)
#   - Configures /boot/firmware/config.txt correctly for Pi 5
#   - Compiles and installs kernel modules via DKMS
#
# Why HinTak fork?
#   The original respeaker/seeed-voicecard and waveshare drivers have issues:
#   - "No MCLK configured" error on Pi 5 (RP1 chip doesn't provide MCLK like older Pis)
#   - Compilation errors on kernel 6.12+ due to API changes
#   The HinTak fork (v6.12 branch) fixes these issues.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration - Using HinTak fork with kernel 6.12 support
VOICECARD_REPO="https://github.com/HinTak/seeed-voicecard"
VOICECARD_BRANCH="v6.12"
VOICECARD_DIR="/tmp/seeed-voicecard"
CONFIG="/boot/firmware/config.txt"

echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}  ReSpeaker 2-Mic HAT Installer for Pi 5 + Bookworm  ${NC}"
echo -e "${GREEN}         (Kernel 6.12 Compatible - HinTak Fork)       ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo

# ------------------------------------------------------------------------------
# Pre-flight checks
# ------------------------------------------------------------------------------

# Check for root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root (use sudo)${NC}" 1>&2
   exit 1
fi

# Get the actual user (not root) for home directory
ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)

# Check for Pi 5
echo -e "${BLUE}Checking system...${NC}"
if grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Raspberry Pi 5 detected"
else
    echo -e "${YELLOW}Warning: This script is designed for Raspberry Pi 5${NC}"
    echo "Detected: $(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo 'Unknown')"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for Bookworm
if grep -q "bookworm" /etc/os-release 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Debian Bookworm detected"
else
    echo -e "${YELLOW}Warning: This script is designed for Debian Bookworm${NC}"
    echo "Detected: $(grep VERSION_CODENAME /etc/os-release 2>/dev/null || echo 'Unknown')"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check architecture
if [[ "$(uname -m)" == "aarch64" ]]; then
    echo -e "  ${GREEN}✓${NC} 64-bit ARM architecture"
else
    echo -e "${RED}Error: This script requires 64-bit ARM (aarch64)${NC}"
    echo "Detected: $(uname -m)"
    exit 1
fi

# Check kernel version
KERNEL_VERSION=$(uname -r)
echo -e "  ${GREEN}✓${NC} Kernel: $KERNEL_VERSION"

echo

# ------------------------------------------------------------------------------
# Step 1: Update system and install dependencies
# ------------------------------------------------------------------------------
echo -e "${GREEN}[1/4] Updating system and installing dependencies...${NC}"
apt-get update
apt-get upgrade -y
apt-get install -y \
    dkms \
    git \
    i2c-tools \
    libasound2-plugins \
    raspberrypi-kernel-headers \
    alsa-utils

echo -e "  ${GREEN}✓${NC} Dependencies installed"
echo

# ------------------------------------------------------------------------------
# Step 2: Clone HinTak seeed-voicecard repository (kernel 6.12 compatible)
# ------------------------------------------------------------------------------
echo -e "${GREEN}[2/4] Cloning HinTak/seeed-voicecard (v6.12 branch)...${NC}"

# Clean up any previous clone
if [[ -d "$VOICECARD_DIR" ]]; then
    echo "  Removing previous clone..."
    rm -rf "$VOICECARD_DIR"
fi

# Clone and checkout the v6.12 branch
git clone "$VOICECARD_REPO" "$VOICECARD_DIR"
cd "$VOICECARD_DIR"
git checkout "$VOICECARD_BRANCH"

echo -e "  ${GREEN}✓${NC} Repository cloned (branch: $VOICECARD_BRANCH)"
echo

# ------------------------------------------------------------------------------
# Step 3: Backup config and clean up any previous failed attempts
# ------------------------------------------------------------------------------
echo -e "${GREEN}[3/4] Preparing system configuration...${NC}"

# Backup config
cp "$CONFIG" "${CONFIG}.backup.$(date +%Y%m%d%H%M%S)"
echo "  - Created backup of config.txt"

# Remove any previous failed overlay entries
sed -i '/seeed-2mic-voicecard/d' "$CONFIG"
sed -i '/wm8960-soundcard/d' "$CONFIG"
echo "  - Cleaned previous overlay entries"

echo -e "  ${GREEN}✓${NC} System prepared"
echo

# ------------------------------------------------------------------------------
# Step 4: Run the HinTak install script
# ------------------------------------------------------------------------------
echo -e "${GREEN}[4/4] Installing drivers (this may take several minutes)...${NC}"
echo "  Running install.sh from HinTak/seeed-voicecard..."
echo

cd "$VOICECARD_DIR"
./install.sh

echo
echo -e "  ${GREEN}✓${NC} Driver installation complete"
echo

# ------------------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------------------
echo -e "${BLUE}Cleaning up...${NC}"
rm -rf "$VOICECARD_DIR"
echo "  - Removed temporary files"
echo

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}          Installation Complete!                      ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo
echo -e "Please ${YELLOW}reboot${NC} your Raspberry Pi to apply changes:"
echo
echo -e "  ${BLUE}sudo reboot${NC}"
echo
echo "After reboot, verify the installation with:"
echo
echo "  arecord -l"
echo "  # Expected: card 0: seeed2micvoicec [seeed-2mic-voicecard]"
echo
echo "  # Test recording (5 seconds at 16kHz stereo):"
echo "  arecord -D plughw:0,0 -f S16_LE -r 16000 -c 2 -d 5 ~/test-recording.wav"
echo
echo "  # Play back on Mac (copy first):"
echo "  # scp pi-hostname:~/test-recording.wav ~/Desktop/"
echo
