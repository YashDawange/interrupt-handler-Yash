# LiveKit Intelligent Interruption Handling

### Why I built this

LiveKit’s voice agents work well until you hit a very real conversation problem:

If the agent is explaining something and the user says
**“yeah”, “ok”, “uh-huh”**,
the agent shuts up mid-sentence.

That’s not an interruption.
That’s *someone listening*.

This assignment is about fixing that **without touching LiveKit’s VAD**, only by adding a smarter logic layer on top.

---

## The actual problem 

* VAD fires **fast**
* STT arrives **later**
* VAD doesn’t know intent — it just hears sound

So the agent gets cut off **before** we even know what the user said.

Result: awkward, broken conversations.

---

## What I changed (high level)

I disabled LiveKit’s automatic interruption behavior and replaced it with:

* A **small FSM**
* A **word-level decision layer**
* A strict rule:

  > *Never stop speaking unless the transcript proves it’s a real interruption*

No VAD kernel changes.
No hacks.
Just logic in the event loop.

---

## State machine

The agent only needs three states:

| State                 | Meaning                            |
| --------------------- | ---------------------------------- |
| `SILENT`              | Agent is not speaking              |
| `SPEAKING`            | Agent is actively talking          |
| `POTENTIAL_INTERRUPT` | User spoke while agent was talking |

VAD only moves us into `POTENTIAL_INTERRUPT`.
STT decides what happens next.

---

## Word handling logic

Defined in `interrupt_config.py` so it’s easy to tweak:

```python
IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "uh-huh", "right"
}

INTERRUPT_WORDS = {
    "stop", "wait", "no", "hold"
}
```

Decision rules:

1. If **any interrupt word** appears → **interrupt**
2. If **only filler words** → **ignore**
3. Mixed input (e.g. “yeah wait”) → **interrupt**

---

## Why `allow_interruptions=False` matters

LiveKit normally interrupts as soon as VAD fires.

That’s the bug.

So I disabled automatic interruption and **manually call**:

```python
session.interrupt()
```

*only after* the transcript confirms intent.

This guarantees:

* No pause
* No stutter
* No “stop → resume” glitch

Either the agent keeps talking, or it stops cleanly.

---

## Edge cases handled

| User says      | Agent speaking? | Result              |
| -------------- | --------------- | ------------------- |
| “yeah”         | ✅               | ignored             |
| “yeah yeah ok” | ✅               | ignored             |
| “no stop”      | ✅               | interrupted         |
| “yeah wait”    | ✅               | interrupted         |
| “yeah”         | ❌               | treated as response |
| “hello”        | ❌               | normal conversation |

---

## Testing (what I can prove without API credits)

I added **pure logic tests** using `pytest`.

These tests cover:

* Tokenization
* Decision logic
* All assignment scenarios

Run them with:

```bash
pytest -v
```

All tests pass (15/15).

This proves the logic works even without running the live agent.

---

## Demo without LiveKit credits

Since API credits are limited, I added a **local simulation script**:
> “Due to API credit limits, I’ve included a deterministic simulation and unit tests that mirror LiveKit’s real event ordering. The same logic is used in the production agent.”

```bash
python demo_simulation.py
```

This script:

* Simulates agent speaking
* Feeds fake STT transcripts
* Shows whether the agent would interrupt or continue

This mirrors LiveKit’s real event order.

---

## Folder structure

```text
.
├── agent/
│   ├── __init__.py
│   ├── basic_agent.py         
│   ├── interrupt_config.py    
│   └── interrupt_logic.py      
│
├── demo_simulation.py         
│
├── tests/
│   ├── __init__.py
│   ├── test_tokenize.py
│   ├── test_decide_interrupt.py
│   └── test_assignment_scenarios.py
│
├── pytest.ini
├── requirements.txt
└── README.md


---