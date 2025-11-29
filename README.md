# Aditya Anjan - 21ME31002

### Demo Video
[Click here to watch the recording](./video_recording.mp4)

drive link for video - https://drive.google.com/file/d/1XuPPXEhgjs4FvkbrXF6NoEuCdLQawBRx/view?usp=drive_link

# Logic

## Smart Interruption & Backchannel Handling

### Overview

This update introduces "Human-Like Interruption Logic" to the `AgentActivity` class. It addresses the issue where standard Voice Activity Detection (VAD) triggers premature interruptions.

**The Problem:**
In standard implementations, *any* detected audio or short text returned by the STT engine causes the Agent to immediately stop speaking. This results in a choppy experience where the Agent cuts itself off if the user coughs, pauses, or uses backchannels (e.g., "uh-huh", "right") to show they are listening.

**The Solution:**
A filtering layer has been implemented to analyze user input in real-time. The Agent will now **ignore** the input and continue speaking if:

1.  **VAD Stutter:** Audio is detected but the transcript is empty (processing lag or noise).
2.  **Backchannels:** The spoken words consist entirely of passive affirmations.

-----

### Configuration

The logic relies on a predefined set of "safe" words that should not trigger an interruption.

**`IGNORE_WORDS` Set:**

```python
IGNORE_WORDS = {
    'yeah', 'ok', 'okay', 'mhmm', 'hmm', 'hm', 'aha', 
    'uh-huh', 'right', 'sure', 'yep', 'yes'
}
```

*Note: The system normalizes input (lowercasing, removing punctuation) so `Yeah!` and `yeah` are treated identically.*

-----

### Implementation Details

The custom logic is injected into two critical points of the conversation lifecycle in `AgentActivity`.

#### 1\. Active Speech Filtering (`_interrupt_by_audio_activity`)

This logic prevents the `stop()` command from being sent to the agent while it is speaking (`self._current_speech` is active).

**Logic Flow:**

1.  **Check Transcript:** If `transcript` is empty/None, return immediately (ignore VAD stutter).
2.  **Clean Text:** Lowercase and remove punctuation.
3.  **Check Backchannels:** If the transcript contains text, check if *every* word belongs to `IGNORE_WORDS`. If true, return immediately (ignore interruption).

**Code Block:**

```python
# --- START CUSTOM LOGIC ---
if self._current_speech is not None and not self._current_speech.done():
    transcript = ""
    if self._audio_recognition:
        transcript = self._audio_recognition.current_transcript

    # 1. PREVENT VAD STUTTER
    # If transcript is empty, return immediately so audio continues 
    # while VAD is active but STT is processing.
    if not transcript or not transcript.strip():
        return

    # 2. IGNORE BACKCHANNELS
    IGNORE_WORDS = {'yeah', 'ok', 'okay', 'mhmm', 'hmm', 'hm', 'aha', 'uh-huh', 'right', 'sure', 'yep', 'yes'}
    import string
    cleaned_text = transcript.lower().translate(str.maketrans('', '', string.punctuation))
    words = cleaned_text.split()
    
    # If all detected words are backchannels, ignore the interruption
    if words and all(w in IGNORE_WORDS for w in words):
        return
# --- END CUSTOM LOGIC ---
```

#### 2\. Turn Completion Filtering (`on_end_of_turn`)

This logic handles the event where the user finishes speaking (End of Utterance).

**Logic Flow:**

1.  **Analyze Final Transcript:** Look at the fully processed text of the user's turn.
2.  **Filter:** If the turn consists *only* of backchannels, return `False`.
3.  **Result:** The turn is discarded. The agent does not generate a response to "uh-huh" and either maintains silence or continues its previous context.

**Code Block:**

```python
# --- START CUSTOM LOGIC ---
# Prevent EOU from triggering an interruption if it's just a backchannel
if self._current_speech is not None and not self._current_speech.done():
    IGNORE_WORDS = {'yeah', 'ok', 'okay', 'mhmm', 'hmm', 'hm', 'aha', 'uh-huh', 'right', 'sure', 'yep', 'yes'}
    import string
    cleaned_text = info.new_transcript.lower().translate(str.maketrans('', '', string.punctuation))
    words = cleaned_text.split()
    
    if words and all(w in IGNORE_WORDS for w in words):
            return False
# --- END CUSTOM LOGIC ---
```

-----

### Behavior Comparison Matrix

| User Action | Detected Text | Old Behavior | New Behavior |
| :--- | :--- | :--- | :--- |
| **User coughs / Background Noise** | `""` (Empty) | Agent stops speaking immediately. | **Agent ignores.** Continues speaking. |
| **User says "Mhmm"** | `"mhmm"` | Agent stops. Processes "mhmm" as a prompt. | **Agent ignores.** Continues speaking. |
| **User says "Yeah, exactly."** | `"yeah exactly"` | Agent stops. | **Agent stops.** ("Exactly" is not in the ignore list). |
| **User says "Wait."** | `"wait"` | Agent stops. | **Agent stops.** ("Wait" is not in the ignore list). |

-----

### Dependencies

  * Python `string` module (for punctuation removal).
  * Standard Python `set` for O(1) lookups.



# How to run the agent

## LiveKit Voice Agent (Gemini Edition)

This repository contains a voice agent (`my_agent.py`) powered by **Google Gemini**, **Deepgram**, and **ElevenLabs**.

### Prerequisites

* **Python 3.9+**
* **LiveKit Cloud** Project (or self-hosted)
* **API Keys** for Google (Gemini), Deepgram, and ElevenLabs.

### Setup & Installation

We use a standard `requirements.txt` to manage the agent's dependencies separately from the workspace configuration.

1.  **Create a Virtual Environment:**
    ```bash
    python -m venv venv
    
    # Windows
    venv\Scripts\activate
    
    # macOS/Linux
    source venv/bin/activate
    ```

2.  **Install Agent Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Configuration

1.  Create a `.env` file in the root directory.
2.  Add your API keys:

    ```env
    # LiveKit
    LIVEKIT_URL=wss://<your-project>.livekit.cloud
    LIVEKIT_API_KEY=<your-api-key>
    LIVEKIT_API_SECRET=<your-api-secret>

    # Plugins
    GOOGLE_API_KEY=<your-google-api-key>
    DEEPGRAM_API_KEY=<your-deepgram-api-key>
    ELEVEN_API_KEY=<your-elevenlabs-api-key>
    ```

### Running the Agent

**Development Mode:**
Use this command to run the agent locally. It enables hot-reloading (restarts when you save the file).

```bash
python my_agent.py dev
