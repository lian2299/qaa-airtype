# Auto Mute Feature (Experimental)

## Overview

This experimental feature automatically mutes the system volume when receiving input from the mobile device, and restores the original volume state after input is complete. This helps prevent audio feedback or echo when using voice input.

## Requirements

For Windows systems, this feature requires additional dependencies:

```bash
pip install pycaw comtypes pywin32
```

## How It Works

1. When enabled, the system detects incoming input from the mobile device
2. Before processing the input, the system:
   - Records the current mute state
   - Mutes the system audio
3. After the input is processed and sent to the active window:
   - The system restores the original mute state

## Usage

1. Open the web interface on your mobile device
2. Click "⚙️ Advanced Options"
3. Enable "Experimental: Auto Mute System During Input"
4. The setting is saved locally and synced with the server

## Notes

- This feature is **experimental** and currently only works on Windows
- The feature requires `pycaw` and `comtypes` libraries
- If the libraries are not installed, the feature will be disabled with a warning message
- The original mute state is always restored, even if an error occurs

## Troubleshooting

If the feature doesn't work:

1. Make sure you're on Windows
2. Install the required dependencies:
   ```bash
   pip install pycaw comtypes pywin32
   ```
3. Check the console output for error messages
4. Try restarting the application after installing dependencies

## Technical Details

- Uses Windows COM interfaces (via `pycaw`) to control system audio
- Accesses `IAudioEndpointVolume` interface for mute control
- Maintains state across multiple input operations
- Gracefully falls back if dependencies are missing

