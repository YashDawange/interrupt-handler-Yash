╔════════════════════════════════════════════════════════════════════════════╗
║          INTERRUPTION HANDLER - INTEGRATION FLOW DIAGRAM                   ║
║                                                                            ║
║ Visual guide to understand how everything fits together                   ║
╚════════════════════════════════════════════════════════════════════════════╝


OVERALL ARCHITECTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────┐
│                     LiveKit Voice Agent                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │        Agent Event Loop (Your Code)                     │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │                                                          │  │
│  │  1. TTS Starts      → on_agent_start_speaking()        │  │
│  │     └─→ state_manager.start_speaking()                 │  │
│  │                                                          │  │
│  │  2. User Speaks     → on_vad_event()          ⭐ KEY    │  │
│  │     └─→ interrupt_filter.should_interrupt()           │  │
│  │         Return: True/False                             │  │
│  │                                                          │  │
│  │  3. TTS Ends        → on_agent_stop_speaking()         │  │
│  │     └─→ state_manager.stop_speaking()                  │  │
│  │                                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│           ▲                                           │         │
│           │                                           ▼         │
│           │                              ┌────────────────────┐ │
│           │                              │ Interruption       │ │
│           └──────────────────────────────│ Handler (Our Code) │ │
│                                          │                    │ │
│                                          │ • StateManager     │ │
│                                          │ • Filter           │ │
│                                          │ • Configuration    │ │
│                                          └────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘


DETAILED EVENT FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Agent Starts Speaking (TTS)
──────────────────────────────────────────────────────────────────

   Your Agent                          Interruption Handler
        │                                        │
        ├─ TTS.start("Hello")                    │
        │                                        │
        ├─ on_agent_start_speaking("utt_123")───┤
        │                                        │
        │                          await start_speaking("utt_123")
        │                                        │
        │                          Store: {
        │                            is_speaking: True,
        │                            utterance_id: "utt_123",
        │                            speech_start_time: now(),
        │                          }
        │                                        │
        │◄─────────────────────────── Return OK ─┤
        │
        └─ Continue TTS playback
           (speech_duration keeps updating)


Step 2: VAD Detects User Speech (⭐ CRITICAL PART)
──────────────────────────────────────────────────────────────────

   Time:  0ms     50ms   100ms              300ms         500ms
   ───────────────────────────────────────────────────────────────

   t=0ms:  User starts speaking
           │
           ▼
   t=50ms: VAD fires (detects voice)
           │
           ├─ Your Agent calls on_vad_event(vad_event)
           │
           ▼ [Into Interruption Handler]
           ├─ Check: Is agent speaking?
           │   └─ YES (state.is_speaking = True)
           │
           ├─ Query state (< 1ms)
           │   └─ agent_state = get_state()
           │
           ├─ WAIT FOR STT (200-500ms)
           │   │
   t=100ms │   STT starts transcribing user audio
           │   │
   t=250ms │   STT working...
           │   │
   t=400ms │   STT completes: "yeah okay"
           │   │
           │   └─ text = "yeah okay"
           │
           ├─ Analyze text with filter
           │   ├─ Check: Is backchannel?
           │   │   └─ YES: "yeah" and "okay" are in ignore_words
           │   │
           │   ├─ Check: Contains command?
           │   │   └─ NO
           │   │
           │   └─ Decision: IGNORE
           │       (should_interrupt = False)
           │
           └─ Return False to agent
              (agent continues speaking without pause)


   Alternative 1: User says command
   ───────────────────────────────────
           ├─ STT: "stop speaking"
           │
           ├─ Analysis:
           │   └─ Contains "stop" (command_word)
           │
           └─ Decision: INTERRUPT (True)
              └─ Agent stops immediately


   Alternative 2: STT timeout
   ───────────────────────────
           ├─ Waiting for STT...
           ├─ 500ms passes (timeout!)
           │
           └─ Decision: INTERRUPT (True)
              └─ Safe default when STT is slow


Step 3: Agent Stops Speaking (TTS ends normally)
──────────────────────────────────────────────────────────────────

   Your Agent                          Interruption Handler
        │                                        │
        ├─ TTS.stop()                            │
        │                                        │
        ├─ on_agent_stop_speaking()──────────────┤
        │                                        │
        │                          await stop_speaking()
        │                                        │
        │                          Clear state: {
        │                            is_speaking: False,
        │                            utterance_id: None,
        │                            speech_duration: None,
        │                          }
        │                                        │
        │◄─────────────────────────── Return OK ─┤
        │
        └─ Ready for next interaction


STATE MACHINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────┐
│   SILENT   │ (agent not speaking)
│ is_speaking│
│   = False  │
└─────┬──────┘
      │
      │ on_agent_start_speaking()
      ▼
┌────────────────────┐
│    SPEAKING        │ (agent is speaking)
│  is_speaking       │
│    = True          │
│  utterance_id: ... │
│  start_time: ...   │
└─────┬──────────────┘
      │
      │ on_agent_stop_speaking()
      │ OR auto_timeout (30s)
      ▼
┌────────────┐
│   SILENT   │
└────────────┘


DECISION LOGIC FLOWCHART
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    VAD Event (User speaks)
                            │
                            ▼
                    ┌─────────────────┐
                    │ Is agent        │
                    │ speaking?       │
                    └────┬────────┬───┘
                         │        │
                    NO   │        │   YES
                         │        │
                         ▼        ▼
                    ┌────────┐ ┌──────────────┐
                    │ Return │ │ Wait for STT │
                    │ False  │ │ (timeout: 500ms)
                    └────────┘ └──────┬───────┘
                                      │
                        ┌─────────────┼─────────────┐
                        │             │             │
                   Timeout        Success        Error
                        │             │             │
                        ▼             ▼             ▼
                    ┌─────┐     ┌────────────┐  ┌─────┐
                    │Return│    │ Analyze    │  │Return│
                    │ True │    │ Text       │  │ True │
                    │Inter-│    └────┬───────┘  │Inter-│
                    │rupt │         │         │ rupt │
                    └─────┘         ▼         └─────┘
                                  ┌────────────────┐
                                  │ Is backchannel │
                                  │ (ignore_words)?│
                                  └────┬───────┬───┘
                                       │       │
                                   YES │       │ NO
                                       │       │
                                       ▼       ▼
                                   ┌─────┐  ┌──────────────┐
                                   │Return│ │ Contains any │
                                   │False │ │ command word?│
                                   │Ignore│ └────┬────┬────┘
                                   └─────┘  YES  │    │ NO
                                               │    │
                                               ▼    ▼
                                           ┌────┐ ┌──────┐
                                           │Return│ │Return│
                                           │ True │ │ False│
                                           │Inter │ │Ignore│
                                           │rupt │ └──────┘
                                           └────┘


CODE INTEGRATION POINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your Agent Class
┌─────────────────────────────────────────────────────────────────┐
│ class MyAgent:                                                  │
│                                                                 │
│     def __init__(self):                                         │
│         # ┌─────────────────────────────────────────────────┐  │
│         # │ INIT: Import and setup handler components      │  │
│         # └─────────────────────────────────────────────────┘  │
│         self.config = load_config()                            │
│         self.state_mgr = AgentStateManager()                   │
│         self.filter = InterruptionFilter(...)                  │
│                                                                 │
│     async def on_tts_start(self, utterance):                   │
│         # ┌─────────────────────────────────────────────────┐  │
│         # │ POINT 1: Track when agent starts speaking      │  │
│         # └─────────────────────────────────────────────────┘  │
│         await self.state_mgr.start_speaking(utterance.id)      │
│                                                                 │
│     async def on_vad_event(self, vad_event):                   │
│         # ┌─────────────────────────────────────────────────┐  │
│         # │ POINT 2: Make smart interruption decision      │  │
│         # │          This is the KEY integration point!    │  │
│         # └─────────────────────────────────────────────────┘  │
│         state = self.state_mgr.get_state()                     │
│                                                                 │
│         if not state.is_speaking:                              │
│             return False                                        │
│                                                                 │
│         try:                                                    │
│             text = await asyncio.wait_for(                    │
│                 self.stt.transcribe(vad_event),               │
│                 timeout=0.5                                     │
│             )                                                   │
│         except asyncio.TimeoutError:                          │
│             return True  # Safe: interrupt if STT slow        │
│                                                                 │
│         should_interrupt, _ = self.filter.should_interrupt(   │
│             text,                                              │
│             state.to_dict()                                    │
│         )                                                       │
│                                                                 │
│         return should_interrupt                                │
│                                                                 │
│     async def on_tts_end(self):                                │
│         # ┌─────────────────────────────────────────────────┐  │
│         # │ POINT 3: Track when agent stops speaking       │  │
│         # └─────────────────────────────────────────────────┘  │
│         await self.state_mgr.stop_speaking()                   │
│                                                                 │
│     # Finally, hook into LiveKit events:                       │
│     #   agent.on_event(TTS_START, self.on_tts_start)          │
│     #   agent.on_event(VAD_EVENT, self.on_vad_event)          │
│     #   agent.on_event(TTS_END, self.on_tts_end)              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘


PERFORMANCE TIMELINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Event Timeline (milliseconds)
┌──────────────────────────────────────────────────────────────────┐
│ t=0ms        VAD fires (user speaks)                             │
│ t=1ms        └─→ get_state() query               [< 1ms] ✓      │
│ t=2ms        └─→ Check if speaking               [< 1ms] ✓      │
│ t=5ms        └─→ Start STT wait                                  │
│ t=10ms       └─→ ...                                             │
│ ...                                                              │
│ t=200ms      └─→ STT starts/completes                           │
│ t=250ms      └─→ Normalize & analyze text        [< 5ms] ✓      │
│ t=260ms      └─→ Fuzzy matching (if needed)     [< 10ms] ✓      │
│ t=270ms      └─→ Decision made                   [< 5ms] ✓      │
│ t=275ms      └─→ Return to agent (TOTAL < 50ms) ✅              │
│ t=276ms      Agent acts on decision (stop or continue)          │
│                                                                  │
│ Key: Agent never pauses for > 50ms (imperceptible)              │
└──────────────────────────────────────────────────────────────────┘


CONFIGURATION FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

         load_config()
              │
        ┌─────┴─────┐
        │           │
        ▼           ▼
   Check Env    Try JSON File
   Variables    (interruption_config.json)
        │           │
        └─────┬─────┘
              │
        ┌─────▼─────┐
        │ No?       │
        └─────┬─────┘
              │
              ▼
        Use Defaults
        (21 ignore words, 19 command words)
              │
              ▼
        InterruptionHandlerConfig object
              │
              ▼
        Create InterruptionFilter
              │
              ▼
        Ready to use!


TYPICAL SESSION TIMELINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Time    Event                  Handler Action              Result
────────────────────────────────────────────────────────────────────
0:00    Agent starts greeting  start_speaking()           is_speaking = True
        "Hello, how can I help?"
                                                          Speech duration: 0s

0:05    User starts speaking   VAD event fires            Query state
        "Yeah, I have a..."    Wait for STT               is_speaking = True

0:15    User still speaking    STT processing             Processing...
        "Yeah, I have a..."    

0:25    STT complete           Analyze: "yeah i have"     Decision: IGNORE ✅
        User is still making   (contains "yeah")          Continue agent
        more sounds            Return False               speaking

0:30    STT timesout (nothing) Timeout occurred           Decision: INTERRUPT
        User paused to listen  Safe default                Stop agent
                               Return True

0:35    Agent finishes         stop_speaking()            is_speaking = False
        "Sure, what is it?"                                State cleared
                               Speech duration: None

0:40    User speaks            VAD event fires            Query state
        "I need help with..."  Agent NOT speaking         Return False
                               Normal LiveKit flow        (normal behavior)

End of session


ERROR HANDLING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scenario                    Result              Why
─────────────────────────────────────────────────────────────────
STT timeout                 INTERRUPT (True)    Safe default - better to
                                                interrupt than miss command
STT service error           INTERRUPT (True)    Safe default - prevent
                                                agent from getting stuck
Empty transcription         IGNORE (False)      Don't interrupt for
("" or None)                                    nothing
Agent not speaking          PROCESS (False)     Let LiveKit handle normally
when VAD fires
State manager error         INTERRUPT (True)    Safe default - err on side
                                                of caution


FILES REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

File                           Purpose
────────────────────────────────────────────────────────────────────
state_manager.py               Track agent speaking state
interruption_filter.py         Make interruption decisions
config.py                      Load configuration
LIVEKIT_INTEGRATION_EXAMPLE.py  Working code with all 3 hooks
INTEGRATION_CHEATSHEET.md       Quick pattern lookup
INTEGRATION_GUIDE.md            Detailed integration guide
INTEGRATION_SUMMARY.txt        This high-level overview

