# Installation Guide

This project uses `uv` for dependency management. Follow these steps to install:

## Option 1: Using uv (Recommended)

From the repository root:

```bash
# Install with OpenAI and Silero plugins
uv sync --extra openai --extra silero

# Or install all extras (takes longer but ensures everything is available)
uv sync --all-extras
```

Then activate the virtual environment:
```bash
# On Windows PowerShell
.\.venv\Scripts\Activate.ps1

# On Windows CMD
.venv\Scripts\activate.bat

# On Linux/Mac
source .venv/bin/activate
```

## Option 2: Using pip (Alternative)

If you don't have `uv` installed, you can install the packages directly:

```bash
# Install from PyPI (if you want to use published packages)
pip install livekit-agents livekit-plugins-openai livekit-plugins-silero python-dotenv

# Or install in editable mode from the workspace
pip install -e ./livekit-agents
pip install -e ./livekit-plugins/livekit-plugins-openai
pip install -e ./livekit-plugins/livekit-plugins-silero
pip install python-dotenv
```

## Verify Installation

After installation, verify it works:

```bash
python -c "from livekit.agents import Agent; from livekit.plugins import openai, silero; print('Installation successful!')"
```

## Troubleshooting

### ModuleNotFoundError: No module named 'livekit'

This means the packages aren't installed or you're not in the virtual environment.

**Solution:**
1. Make sure you ran `uv sync` from the repository root
2. Activate the virtual environment (see above)
3. Verify with: `python -c "import livekit.agents; print('OK')"`

### Import errors

If you get import errors, make sure you're in the virtual environment and the packages are installed:

```bash
# Check if packages are installed
pip list | grep livekit

# Reinstall if needed
uv sync --extra openai --extra silero
```

