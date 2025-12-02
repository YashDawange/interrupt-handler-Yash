# Interrupt Handler Implementation

## Summary

This PR implements a production-quality, rule-based Interrupt Handler that prevents voice agents from being cut off by backchannel words ("yeah", "ok", "hmm") while still allowing real interrupts ("stop", "wait", "no").

## Features

- **Rule-based interrupt detection**: Uses configurable soft/hard word lists to distinguish backchannel from real interrupts
- **Confirmation window**: Short 120-180ms window to collect STT partials before making interrupt decisions
- **Immediate routing**: When agent is silent, user speech is routed immediately without delay
- **Smart resume**: Soft backchannel words resume audio playback instead of interrupting
- **Hard interrupt detection**: Hard words trigger immediate interrupt even in partial transcripts

## Implementation Details

### Core Module
- `livekit/agents/voice/interrupt_handler.py`: Main InterruptHandler class with:
  - `on_vad()`: Called when VAD detects start-of-speech
  - `on_stt_partial()`: Called with streaming partial transcripts
  - `on_stt_final()`: Called with final transcripts
  - Configurable soft/hard word lists and timing values

### Testing
- `tests/test_interrupt_handler.py`: Comprehensive pytest test suite covering:
  - VAD while silent (immediate routing)
  - Soft backchannel ignored while speaking
  - Hard interrupt handled
  - Mixed utterance interrupts
  - Edge cases (empty transcripts, multiple soft words, custom word lists)

### Demo
- `scripts/run_demo.py`: Runnable demo script that simulates all four required scenarios

### Documentation
- `docs/README_INTERRUPT.md`: Complete documentation with purpose, usage, configuration, and demo instructions
- `docs/INTEGRATION_SNIPPETS.md`: Code snippets for integrating the handler into agent sessions

### CI
- `.github/workflows/ci.yml`: CI workflow to run pytest on PRs

## Behavior

1. **Agent Silent**: User speech routes immediately via `on_immediate_user_speech` callback
2. **Agent Speaking + Soft Words**: Audio pauses briefly, soft words detected, audio resumes (no interrupt)
3. **Agent Speaking + Hard Words**: Audio pauses, hard word detected in partial/final, audio stops, `on_interrupt` called
4. **Agent Speaking + Mixed**: Audio pauses, hard word detected, audio stops, `on_interrupt` called

## Configuration

Default configuration:
- **Soft words**: "yeah", "ok", "okay", "hmm", "uh-huh", "mhm", "mm-hmm", "right", "yah", "yep", "yup"
- **Hard words**: "stop", "wait", "no", "pause", "hold on", "hold up", "cut", "cancel"
- **Confirmation window**: 150ms (configurable)

## Testing

Run tests:
```bash
pytest tests/test_interrupt_handler.py -v
```

Run demo:
```bash
python scripts/run_demo.py
```

## Integration

See `docs/INTEGRATION_SNIPPETS.md` for detailed integration examples. The handler requires:
- Audio player with `is_playing()`, `pause()`, `resume()`, `stop()` methods
- VAD events routed to `on_vad()`
- STT partial/final results routed to `on_stt_partial()` and `on_stt_final()`

## Demo Video

See `DEMO_VIDEO_SCRIPT.md` for the demo video script (30-60 seconds).

