# Pisator

Pisator is a Python-based desktop application that automates text typing. It provides customizable typing speed, realistic typing simulation, typo correction, and an intuitive graphical user interface.

## Features

- Automated text typing
- Adjustable typing speed
- Speed presets: Slow, Normal, Fast, and Turbo
- Random typo simulation
- Automatic typo correction
- New line and Enter key support
- Pause and resume functionality
- Instant typing cancellation
- Character and word counter
- Estimated typing time
- Import and export TXT files
- Recently used text history
- Copy text to clipboard
- Adjustable interface scaling
- Automatic settings saving
- Automatic installation of required Python packages
- Error logging

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer
- Internet connection for the first launch

## Installation

1. Download or clone this repository.
2. Open the project folder.
3. Open a terminal in the project directory.
4. Run the following command:

```bash
py pisator.py
```

The application automatically checks for missing dependencies and installs them on the first launch.

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| F8 | Stop typing |
| F9 | Pause / Resume |

## Project Structure

| File | Description |
|---|---|
| `pisator.py` | Main application |
| `settings.json` | Saved application settings |
| `history.json` | Recently used texts |
| `pisator.log` | Application logs and errors |

## Technologies

- Python
- CustomTkinter
- PyAutoGUI
- Keyboard
- Windows API

## License

This project is intended for personal and educational use.