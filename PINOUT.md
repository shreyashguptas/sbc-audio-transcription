# INMP441 Microphone Pinout for Raspberry Pi 5

## Wiring Configuration

This project uses the **INMP441 I2S MEMS microphone** connected to the Raspberry Pi 5.

### Pin Connections

| INMP441 Pin | Function | Raspberry Pi 5 Pin | GPIO/Physical |
|-------------|----------|-------------------|---------------|
| VDD         | Power    | 3.3V              | Pin 1         |
| GND         | Ground   | GND               | Pin 6         |
| SD          | Data     | GPIO20            | Pin 38        |
| WS          | Word Select | GPIO19         | Pin 35        |
| SCK         | Clock    | GPIO18            | Pin 12        |
| L/R         | Channel  | GND               | Any GND       |

### Important Notes

- **Channel Selection**: L/R pin connected to GND = LEFT channel (we use LEFT channel only in the script)
- **Audio Device**: Configured as `plughw:0,0` in ALSA
- **Format**: 48kHz, Stereo, S16_LE
- **Processing**: LEFT channel only (RIGHT channel has noise)

### I2S Configuration

The I2S interface is enabled in `/boot/firmware/config.txt`:

```
dtparam=i2s=on
dtoverlay=googlevoicehat-soundcard
```

### Audio Processing

The script uses:
- **LEFT channel only**: `audio[:, 0]` (RIGHT channel contains noise)
- **Sample rate conversion**: 48kHz → 16kHz
- **Gain**: 30x amplification
- **Clipping protection**: Values clipped to [-1.0, 1.0]

### Testing the Microphone

To verify the microphone is working:

```bash
arecord -D plughw:0,0 -f S16_LE -r 48000 -c 2 -d 5 test.wav
aplay test.wav
```

---

**Last Updated**: 2025-11-18
**Project**: Voice Transcription with Faster-Whisper
