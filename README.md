# 🎙️ Voice Agent Kelly: Intelligent Interruption Handler

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/livekit/agents/main/.github/banner_dark.png">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/livekit/agents/main/.github/banner_light.png">
  <img style="width:100%;" alt="LiveKit Agents Banner" src="https://raw.githubusercontent.com/livekit/agents/main/.github/banner_light.png">
</picture>

---

> 🌟 **Kelly** is a sophisticated conversational AI that intelligently distinguishes between casual fillers and intentional commands—setting a new standard in real-time interruption handling.

---

## 📋 Table of Contents

- [✨ Project Overview](#-project-overview)
- [🧠 Challenge Logic](#-challenge-logic-interruption-handling)
- [🚀 Quick Start](#-quick-start)
- [⚙️ Installation & Setup](#️-installation--setup)
- [🎯 Usage Guide](#-usage-guide)
- [✅ Verification](#-verification-proof-of-functionality)
- [🏗️ Technical Stack](#️-technical-stack)
- [📚 Resources](#-resources)

---

## ✨ Project Overview

**Kelly** is a high-performance conversational AI engineered to tackle the **Intelligent Interruption Challenge**. Built on the powerful **LiveKit Agents framework**, Kelly seamlessly:

- 🎯 **Distinguishes** between conversational fillers ("yeah", "ok", "hmm") and intentional commands ("stop", "wait", "no")
- ⚡ **Responds intelligently** to user input while maintaining conversation flow
- 🔄 **Handles edge cases** like false starts and background noise with grace
- 💬 **Maintains context** across multiple interaction scenarios

---

## 🧠 Challenge Logic: Interruption Handling

Kelly satisfies four distinct behavioral scenarios through intelligent `AgentSession` configuration:

| User Input | Agent State | Action | Technical Logic |
| :---: | :---: | :---: | :--- |
| **"Yeah / Ok / Hmm"** | Speaking | 🚫 **IGNORE** | Suppressed via `min_interruption_words=2` and dynamic `IGNORE_WORDS` |
| **"Wait / Stop / No"** | Speaking | ⏹️ **INTERRUPT** | Meets word threshold to trigger `session.interrupt()` |
| **"Yeah / Ok / Hmm"** | Silent | 💬 **RESPOND** | Valid turn-taking when agent is silent |
| **"False Start / Noise"** | Speaking | ▶️ **RESUME** | Brief noises trigger pause and auto-resume via `resume_false_interruption` |

---

## 🚀 Quick Start

Get Kelly up and running in 30 seconds:

```bash
# 1. Install dependencies
pip install -r examples/voice_agents/requirements.txt

# 2. Set up environment (see below)
# 3. Run the agent
python examples/voice_agents/basic_agent.py dev
```

---

## ⚙️ Installation & Setup

### Step 1️⃣: Install Dependencies

```bash
pip install -r examples/voice_agents/requirements.txt
```

**Required Packages:**
- 🎤 **LiveKit Agents** - Orchestration framework
- 🔊 **Deepgram** - Speech-to-text (STT)
- 🧠 **Groq** - Large language model (LLM)
- 🎙️ **TTS Libraries** - Text-to-speech synthesis
- 🕵️ **Silero VAD** - Voice activity detection

---

### Step 2️⃣: Configure Environment Variables

Create a `.env` file in the root directory (**ensure it's in `.gitignore`**):

```env
# LiveKit Configuration
LIVEKIT_URL=your_url
LIVEKIT_API_KEY=your_key
LIVEKIT_API_SECRET=your_secret

# AI Provider Keys
GROQ_API_KEY=your_groq_key
DEEPGRAM_API_KEY=your_deepgram_key
```

> ⚠️ **Security Note:** Never commit `.env` files with sensitive credentials to version control!

---

## 🎯 Usage Guide

### Running the Agent

Start Kelly with hot-reloading and console logging for development:

```bash
python examples/voice_agents/basic_agent.py dev
```

**Features:**
- 🔄 Auto-reload on code changes
- 📊 Real-time console logging
- 🐛 Enhanced debugging output

---

## ✅ Verification: Proof of Functionality

Test Kelly's intelligent interruption handling in the LiveKit Sandbox with these scenarios:

### Test 1️⃣: Filler Test (Should NOT Interrupt) 🚫
```
👤 User: [While Kelly is speaking] "Yeah"
✅ Expected: Kelly continues without interruption
```

### Test 2️⃣: Command Test (Should Interrupt) ⏹️
```
👤 User: [While Kelly is speaking] "Stop right now"
✅ Expected: Kelly halts immediately
```

### Test 3️⃣: Turn-Taking Test (Should Respond) 💬
```
👤 User: [After Kelly finishes] "Ok"
✅ Expected: Kelly acknowledges and responds
```

---

## 🏗️ Technical Stack

A carefully selected ensemble of cutting-edge technologies:

| Component | Technology | Purpose |
| :---: | :--- | :--- |
| 🎼 **Orchestration** | **LiveKit Agents Framework** | Core agent coordination & lifecycle |
| 👂 **STT (Ears)** | **Deepgram Nova-3** | High-speed, accurate transcription |
| 🧠 **LLM (Brain)** | **Groq Llama-3.1-8B-instant** | Sub-500ms response latency |
| 🎙️ **TTS (Voice)** | **Deepgram Aura (Luna)** | Natural, realistic speech synthesis |
| 🕵️ **VAD** | **Silero VAD** | Precise voice activity detection |

### Why This Stack?

- ⚡ **Ultra-Low Latency** - Groq delivers sub-500ms responses for fluid conversation
- 🎯 **High Accuracy** - Deepgram's Nova-3 provides enterprise-grade transcription
- 🌍 **Wide Language Support** - Handles diverse accents and speech patterns
- 🔧 **Easy Integration** - LiveKit Agents provides seamless orchestration

---

## 📚 Resources

- 📖 [LiveKit Voice AI Agent Tutorial](https://drive.google.com/file/d/1Ng_Y-PLyeUqd4bYr6Sr6XZBHbgDHgzZK/view?usp=sharing) - Complete setup walkthrough
- 🔗 [LiveKit Documentation](https://docs.livekit.io/) - Official reference
- 🎓 [Groq API Docs](https://console.groq.com/docs) - LLM integration guide

---

<div align="center">

### 🌟 Made with ❤️ using LiveKit Agents

**Questions?** [Open an issue](../../issues) | **Found a bug?** [Report it](../../issues/new)

</div>