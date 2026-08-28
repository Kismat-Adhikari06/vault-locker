# Contributing to VaultLock

Thanks for your interest in contributing!

## Development Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Install system packages: `sudo apt install gocryptfs fuse3 libgtk-4-dev libadwaita-1-dev python3-gi`
4. Run: `python3 main.py`

## Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Add docstrings for public functions
- Keep modules focused on a single responsibility

## Architecture

- `main.py` — Application lifecycle and CLI
- `window.py` — UI and dialogs
- `folder_item.py` — Reusable widget
- `storage.py` — JSON persistence
- `security.py` — Password hashing
- `locker.py` — gocryptfs operations

## Testing

1. Create test folder: `mkdir -p ~/VaultTest && echo "test" > ~/VaultTest/test.txt`
2. Run app: `python3 main.py`
3. Add folder → Set Password → Lock → Verify empty
4. Unlock → Verify files restored
