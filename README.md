# Intelligent Interruption Handling for LiveKit Agents

## Problem Statement

LiveKit's default Voice Activity Detection (VAD) is too sensitive to user feedback. When a user says "yeah", "yay", "ok", or "hmm" to show they're listening (backchanneling), the agent incorrectly stops speaking mid-sentence.

## Solution

This implementation adds intelligent backchannel detection that distinguishes between:
- **Passive acknowledgments** ("yeah", "yay", "ok", "hmm") → Agent continues speaking
- **Active interruptions** ("stop", "wait", "no") → Agent stops immediately

---

## 🚀 How to Run

### 1. Setup Environment

Create a `.env` file in the root directory:

```env
# LLM Provider - Choose ONE (Groq recommended for free tier, OpenAI for paid)
GROQ_API_KEY=your_groq_api_key          # FREE - Fastest free option (recommended)
# OPENAI_API_KEY=your_openai_api_key   # PAID - Alternative (uncomment to use)

# Required: STT Provider (using Deepgram - free tier)
DEEPGRAM_API_KEY=your_deepgram_api_key

# Required: TTS Provider (using Cartesia - free tier)
CARTESIA_API_KEY=your_cartesia_api_key

# Required: LiveKit credentials
LIVEKIT_URL=wss://your-livekit-url
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
```

**Get API Keys:**
- **Groq (FREE - Recommended):** https://console.groq.com/
- **OpenAI (PAID - Alternative):** https://platform.openai.com/api-keys
- **Deepgram (FREE):** https://console.deepgram.com/
- **Cartesia (FREE):** https://play.cartesia.ai/
- **LiveKit (FREE):** https://cloud.livekit.io/

> **Note:** The agent auto-detects which LLM to use based on available API keys. If both `GROQ_API_KEY` and `OPENAI_API_KEY` are present, Groq takes priority. To use OpenAI, simply remove or comment out the Groq key.

### 2. Install Dependencies

**Option A: Using requirements.txt (Recommended)**
```bash
# Install all dependencies from examples/voice_agents/requirements.txt
pip install -r examples/voice_agents/requirements.txt
```

**Option B: Manual installation**
```bash
# Install the modified livekit-agents
pip install -e livekit-agents

# Install required plugins
pip install -e livekit-plugins/livekit-plugins-groq    # For Groq LLM
pip install -e livekit-plugins/livekit-plugins-openai  # For OpenAI (if using)
```

> **Note:** The `requirements.txt` file is located at `examples/voice_agents/requirements.txt`, not in the root directory.

### 3. Run the Agent

```bash
python examples/voice_agents/test_interrupt_free.py dev
```

### 4. Test in Browser

Open the LiveKit Agents Playground URL shown in terminal and connect your microphone.

---

## 🔧 How It Works

### Core Logic

The implementation solves the VAD-STT race condition problem:

**Problem:** VAD detects speech in ~100ms, but STT takes ~500ms to transcribe words. The old approach would stop the agent immediately on VAD, then resume if backchannel was detected - causing stutters.

**Solution:** Defer the interruption decision to STT:

```
1. VAD fires → Set flag (_interruption_pending = True)
2. Wait for STT transcript (~500ms)
3. STT analyzes words:
   - ALL words are backchannels? → IGNORE (agent never stopped)
   - ANY word is NOT backchannel? → INTERRUPT (stop agent now)
```

**Result:** Agent continues speaking seamlessly for backchannels, no pause or stutter.

### Implementation

**Modified Files:**

1. **`livekit-agents/livekit/agents/voice/agent_activity.py`**
   - Added `_interruption_pending` flag to track pending VAD events
   - Modified `on_vad_inference_done()`: Sets flag instead of interrupting immediately
   - Modified `on_interim_transcript()` and `on_final_transcript()`: Check if words are backchannels
   - Modified `_user_turn_completed_task()`: Skip sending backchannel-only inputs to LLM

2. **`livekit-agents/livekit/agents/voice/agent_session.py`**
   - Added `backchannel_words` parameter to configure ignore list

### Configurable Backchannel Words

The ignore list is easily configurable:

```python
session = agents.AgentSession(
    llm=llm_instance,
    stt=stt_instance,
    tts=tts_instance,
    vad=vad_instance,
    backchannel_words=[
        'yeah', 'yay', 'yes', 'yep', 'yup', 'ya', 'yea',
        'ok', 'okay', 'k', 'kay',
        'hmm', 'hm', 'mm', 'mmm', 'mhm',
        'right', 'alright', 'sure',
        'aha', 'ah', 'oh', 'ooh', 'uh',
    ]
)
```

### Semantic Interruption

The logic checks if **ALL** words are backchannels:

```python
word_list = ["yeah", "okay", "but", "wait"]
is_backchannel_only = all(word in backchannel_words for word in word_list)
# Result: False (because "but" and "wait" are NOT backchannels)
# Action: INTERRUPT
```

This handles mixed input like "yeah okay but wait" correctly - the agent stops because "but" and "wait" are not in the ignore list.

---

## ✅ Test Scenarios

### Scenario 1: Backchannels Ignored (Agent Speaking)
```
Agent: "A refrigerator is designed to keep food cool..."
User: "yeah" → Agent continues speaking ✅
User: "okay" → Agent continues speaking ✅
User: "hmm" → Agent continues speaking ✅
```

**Terminal logs:**
```
DEBUG  livekit.agents   VAD detected speech - STT will decide if interrupt is needed
DEBUG  livekit.agents   STT decision: IGNORE - backchannel detected
                        {"transcript": "yeah.", "words": ["yeah"]}
DEBUG  livekit.agents   Skipping user turn - backchannel only (agent was speaking)
```

### Scenario 2: Backchannels Responded (Agent Silent)
```
Agent: "Are you ready?" [stops speaking]
User: "yeah" → Agent responds: "Great, let's begin" ✅
```

**Terminal logs:**
```
[TRANSCRIPT] Yeah.
[AGENT STATE] listening -> thinking  (Agent treats as valid input)
```

### Scenario 3: Commands Interrupt (Agent Speaking)
```
Agent: "The capital of France is..."
User: "stop" → Agent stops immediately ✅
User: "wait" → Agent stops immediately ✅
```

**Terminal logs:**
```
DEBUG  livekit.agents   STT decision: INTERRUPT - command detected
                        {"transcript": "stop.", "words": ["stop"]}
INFO   agent            [AGENT STATE] speaking -> listening
```

### Scenario 4: Mixed Input (Semantic Interruption)
```
Agent: "Water has the formula H2O..."
User: "yeah okay but wait" → Agent stops ✅
```

**Terminal logs:**
```
DEBUG  livekit.agents   STT decision: INTERRUPT - command detected
                        {"transcript": "yeah okay but wait", "words": ["yeah", "okay", "but", "wait"]}
INFO   agent            [AGENT STATE] speaking -> listening
```

---

## 📋 Requirements Met

| Requirement | Implementation | Status |
|------------|----------------|---------|
| **Configurable Ignore List** | `backchannel_words` parameter | ✅ |
| **State-Based Filtering** | Only applies when `agent_state == "speaking"` | ✅ |
| **Semantic Interruption** | Checks if ANY word is not backchannel | ✅ |
| **No VAD Modification** | Logic layer in `agent_activity.py` only | ✅ |
| **Real-time Latency** | <1ms for word matching | ✅ |
| **Documentation** | This README | ✅ |

---

## 🎯 Technical Details

### Performance

- **Latency:** <1ms for word matching (simple set membership check)
- **Memory:** <1KB for backchannel word set
- **No additional API calls:** Uses existing STT transcripts

### Code Quality

- **Modular:** Logic isolated in `agent_activity.py`
- **Configurable:** Easy to modify backchannel words per-session or globally
- **Maintainable:** Clear log messages for debugging
- **No breaking changes:** Backward compatible with existing agents

---

## 🐛 Troubleshooting

### Issue: Agent still interrupts on "yeah"

**Solution:**
```bash
# Make sure you installed the LOCAL modified version
pip uninstall livekit-agents
pip install -e livekit-agents

# Verify it's using your local code
pip show livekit-agents
# Should show: Location: /path/to/agents-assignment/livekit-agents
```

### Issue: "Model not found" error

**Solution:** Install the Groq plugin:
```bash
pip install -e livekit-plugins/livekit-plugins-groq
```

### Issue: Rate limit errors (429)

**Solution:** Free API tiers have limits. Wait 30-60 minutes or use different API keys.

---

## 📦 Files Modified

### Core Implementation (2 files)
- `livekit-agents/livekit/agents/voice/agent_activity.py` - Main interruption logic
- `livekit-agents/livekit/agents/voice/agent_session.py` - Configuration parameter

### Test Agent (1 file)
- `examples/voice_agents/test_interrupt_free.py` - Demo agent with backchannel detection

### Requirements (1 file)
- `examples/voice_agents/requirements.txt` - Added `groq` dependency

---

## 📄 License

This project follows the original LiveKit Agents license (Apache 2.0).

---

## 🙏 Credits

Built on [LiveKit Agents Framework](https://github.com/livekit/agents).
