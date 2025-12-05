# Fix OpenTelemetry Import Error

If you're getting this error:
```
ImportError: cannot import name 'LogData' from 'opentelemetry.sdk._logs'
```

This is due to OpenTelemetry version conflicts. Here's how to fix it:

## Solution 1: Use uv sync (Recommended)

From the repository root:

```powershell
# Remove any existing installations
pip uninstall opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp -y

# Use uv to install with proper dependency resolution
uv sync --extra openai --extra silero

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

## Solution 2: Fix OpenTelemetry versions manually

If you can't use uv, upgrade OpenTelemetry packages:

```powershell
pip install --upgrade "opentelemetry-api>=1.34" "opentelemetry-sdk>=1.34.1" "opentelemetry-exporter-otlp>=1.34.1"
```

## Solution 3: Reinstall everything properly

From repository root:

```powershell
# Uninstall all livekit packages
pip uninstall livekit-agents livekit-plugins-openai livekit-plugins-silero -y

# Reinstall in correct order
pip install -e ./livekit-agents
pip install -e ./livekit-plugins/livekit-plugins-openai
pip install -e ./livekit-plugins/livekit-plugins-silero

# Ensure OpenTelemetry is correct version
pip install --upgrade "opentelemetry-api>=1.34" "opentelemetry-sdk>=1.34.1" "opentelemetry-exporter-otlp>=1.34.1"
```

## Verify Installation

After fixing, verify:

```powershell
python -c "from opentelemetry.sdk._logs import LogData; print('OpenTelemetry OK')"
python -c "from livekit.agents import Agent; print('LiveKit OK')"
```

