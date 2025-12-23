# Voice Agent Interruption Handling – Execution Plan

## Goal

Build a voice agent that can **speak smoothly** without getting interrupted by small user reactions like
“yeah”, “ok”, or “hmm”,
but **immediately stop** when the user actually wants to interrupt with words like
“stop”, “wait”, or “hold on”.

The main challenge is to **tell the difference** between:

* **polite listening signals** (backchanneling)
* **real interruptions**

---

## High-Level Idea

1. **Always know when the agent is speaking**
2. **Listen to what the user says during that time**
3. **Ignore harmless feedback**
4. **Interrupt only when the user clearly means to stop the agent**

No guessing, no timers, no delays.

---

## Step-by-Step Plan

### Step 1: Track When the Agent Is Speaking

* The system must always know:

  * Is the agent currently speaking?
  * Or is it silent?

**Why?**

* If the agent is *not* speaking, user speech is normal.
* Interruption logic only matters **while the agent is talking**.

**How we plan to do this**

* Listen to agent state changes (`speaking`, `listening`, etc.)
* Maintain a simple `agent_is_speaking = true/false` flag.

---

### Step 2: Capture User Speech Transcripts

* Listen to user speech events.
* Each transcript comes with:

  * The text
  * Whether it’s **final** or **interim**

**Rule**

* Ignore empty text.
* Ignore interim (partial) transcripts.
* Only make decisions on **final user input**.

---

### Step 3: Define Two Categories of User Words

Before writing logic, we classify words into two groups:

#### 1️⃣ Soft Backchannels (Safe to Ignore)

These mean:

> “I’m listening, keep going.”

Examples:

* yeah
* ok
* hmm
* uh-huh
* right
* got it
* makes sense

**Plan**

* If user speech contains *only* these words,
  → **do nothing**
  → let the agent continue speaking.

---

#### 2️⃣ Strong Interrupts (Must Stop the Agent)

These mean:

> “Stop. I want control.”

Examples:

* stop
* wait
* hold on
* no

**Plan**

* If *any* strong interrupt word appears,
  → immediately interrupt the agent.

---

### Step 4: Normalize User Speech

Speech recognition is messy:

* “Wait”
* “WAIT”
* “wait wait”
* “wait, hold on”

**Plan**

* Convert text to lowercase
* Split into clean word tokens
* Ignore punctuation and spacing differences

This makes matching reliable.

---

### Step 5: Decide What to Do When User Speaks During Agent Speech

When the agent is speaking **and** the user talks:

1. **If the input is only soft backchannel words**

   * Clear the user turn
   * Keep agent speaking

2. **If the input contains any strong interrupt**

   * Immediately interrupt the agent

3. **If the input is mixed or unclear**

   * Treat it as an interrupt (safe default)

---

### Step 6: Keep Configuration Flexible

Different products need different words.

**Plan**

* Allow backchannel and interrupt words to be:

  * Defined in code
  * Overridden using environment variables

This avoids changing logic later.

---

## Expected Behavior (Examples)

| User says while agent speaks | Result                  |
| ---------------------------- | ----------------------- |
| “yeah”                       | Agent keeps talking     |
| “hmm ok”                     | Agent keeps talking     |
| “wait”                       | Agent stops immediately |
| “hold on a second”           | Agent stops             |
| “no no stop”                 | Agent stops             |
| “I meant something else”     | Agent stops             |

---

## Why This Plan Works Well

* No VAD guessing
* No audio-based heuristics
* No delays
* Clear rules
* Predictable behavior
* Easy to tune later

---

## Summary

**In one sentence:**

> Let the agent speak freely, ignore polite listening noises, and stop instantly only when the user clearly asks to interrupt.
