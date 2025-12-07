# Intelligent Interruption Logic — README

## Purpose
This logic layer provides deterministic heuristics to decide whether incoming user speech should interrupt an assistant that is currently speaking (TTS). It is intentionally small and synchronous so it's easy to reason about and tune.

## Concepts
- **Filler / backchannel words** (e.g. "yeah", "ok"): these are typically not intended to interrupt the assistant while it speaks.
- **Interrupt commands** (e.g. "stop", "wait"): always considered an interrupt when the assistant is speaking.
- **Threshold-based content**: non-filler words in a short burst can be considered interruptive if they meet or exceed `min_words_for_interrupt`.

## Files
- `interrupt_handler.py` — the core logic. Exposes:
  - `InterruptHandler.should_interrupt(agent_state, transcribed_text) -> bool`
  - `InterruptHandler._tokenize(text) -> list[str]` (utility)
  - `InterruptHandler.get_stats()` / `reset_stats()`
  - `AgentState` enum with `SPEAKING` and `SILENT`.

- `interrupt_config.json` — words and threshold configuration:
  - `filler_words` (array)
  - `interrupt_words` (array)
  - `min_words_for_interrupt` (integer)

- `agent_layer.py` — a sample integration demonstrating how to wire `InterruptHandler` into an `AgentSession`.

## Decision policy (summary)
1. If agent is **SILENT** → treat any final user input as input (no special handling).
2. If agent is **SPEAKING**:
   - If transcript contains any `interrupt_words` → **interrupt**.
   - Else if all tokens are in `filler_words` → **ignore** (do not interrupt).
   - Else if count(non-filler tokens) >= `min_words_for_interrupt` → **interrupt**.
   - Else → **ignore**.

Notes:
- Interim STT transcripts are checked to allow quick manual interruption. Final transcripts are treated similarly and are more authoritative.
- The tokenization is intentionally simple (`\b[a-z]+\b`) to avoid complicated language-specific tokenizers and keep the system fast.

## Tuning guide
- To make the handler **more sensitive**:
  - Lower `min_words_for_interrupt` (e.g., `1` will make single non-filler words interrupt).
  - Add more words to `interrupt_words` (phrases like "hey", "excuse me").

- To make the handler **less sensitive**:
  - Increase `min_words_for_interrupt` (e.g., `3`).
  - Add common backchannels to `filler_words`.

## Debugging / logging
- `InterruptHandler` logs informational messages for decisions (interruption vs ignored) and debug logs for tokenization and empty transcripts.
- Use `get_stats()` to inspect counts during tests.

## Integration checklist
1. Place `interrupt_handler.py` in the same package path used by your app (the agent_layer imports it as `livekit.agents.voice.interrupt_handler`).
2. Ensure `interrupt_config.json` is discoverable in project root (or pass a path to `InterruptHandler(config_path=...)`).
3. In your session loop (STT callbacks), call:
   ```py
   should_interrupt = interrupter.should_interrupt(current_agent_state, transcript_text)
   if should_interrupt:
       session.interrupt()