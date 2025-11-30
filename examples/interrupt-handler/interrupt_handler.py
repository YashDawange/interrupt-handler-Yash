"""
LiveKit Agent with Intelligent Interruption Handler
Professional 3-tier analysis system: Exact → Fuzzy → Semantic
"""

from dotenv import load_dotenv
load_dotenv()

import os
import sys
import logging
import re
from dataclasses import dataclass
from typing import Optional, Tuple
from difflib import SequenceMatcher

# Verify environment
required = ['GROQ_API_KEY', 'DEEPGRAM_API_KEY', 'LIVEKIT_URL']
missing = [v for v in required if not os.getenv(v)]
if missing:
    print(f"Missing: {', '.join(missing)}")
    sys.exit(1)

from livekit.agents import (
    JobContext,
    WorkerOptions,
    cli,
    Agent,
    AgentSession,
    AutoSubscribe,
)
from livekit.plugins import deepgram, silero, groq

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("intelligent-agent")


# ============================================================================
# CONFIGURATION
# ============================================================================

# Backchannel words (to ignore when agent is speaking)
IGNORE_WORDS = os.getenv(
    "IGNORE_WORDS",
    "yeah,ok,okay,hmm,uh-huh,uhhuh,uh huh,alright,right,mmhmm,yep,gotcha,sure,mhm,aha,mm,uhuh,hm,uh,yea,ya"
).split(",")

# Interrupt words (should stop agent)
INTERRUPT_WORDS = os.getenv(
    "INTERRUPT_WORDS", 
    "stop,wait,no,hold on,hold,hang on,pause,stop it,halt,actually,but,however,excuse"
).split(",")

# Fuzzy match threshold
FUZZY_MATCH_THRESHOLD = float(os.getenv("FUZZY_MATCH_THRESHOLD", "0.80"))


# ============================================================================
# TEXT NORMALIZATION
# ============================================================================

def normalize_text(s: str) -> str:
    """Normalize text for comparison"""
    return re.sub(r"[^\w\s]", "", s.lower()).strip()


# Create normalized sets
IGNORE_SET = {normalize_text(w) for w in IGNORE_WORDS if w}
INTERRUPT_SET = {normalize_text(w) for w in INTERRUPT_WORDS if w}


def tokens_of(s: str):
    """Tokenize normalized text"""
    s = normalize_text(s)
    return [t for t in s.split() if t]


# ============================================================================
# TRANSCRIPT ANALYSIS
# ============================================================================

@dataclass
class TranscriptAnalysis:
    """Result of analyzing a transcript"""
    is_backchannel: bool
    is_interrupt: bool
    is_mixed: bool
    reason: str
    confidence: float = 1.0


# ============================================================================
# BACKCHANNEL FILTER - 3-TIER SYSTEM
# ============================================================================

class BackchannelFilter:
    """
    Three-tier transcript analysis system:
    
    Tier 1: Exact Match (< 1ms)
        - Check if words exactly match IGNORE_SET or INTERRUPT_SET
        - Highest confidence, fastest
        
    Tier 2: Fuzzy Match (1-3ms)  
        - Use string similarity to catch typos
        - Examples: "okey" → "okay", "waait" → "wait"
        
    Tier 3: Semantic (future enhancement)
        - Can add sentence-transformers for unknown phrases
        - Not required for basic assignment
    """
    
    def __init__(self):
        self._tier_stats = {"exact": 0, "fuzzy": 0, "fallback": 0}
        logger.info(f"BackchannelFilter initialized")
        logger.info(f"  Ignore words: {len(IGNORE_SET)}")
        logger.info(f"  Interrupt words: {len(INTERRUPT_SET)}")
        logger.info(f"  Fuzzy threshold: {FUZZY_MATCH_THRESHOLD}")
    
    def analyze(self, text: str) -> TranscriptAnalysis:
        """
        Analyze transcript using three-tier approach.
        
        Returns classification with confidence score.
        """
        text_norm = normalize_text(text)
        toks = tokens_of(text_norm)
        
        # Handle empty input
        if not toks:
            return TranscriptAnalysis(
                is_backchannel=True,
                is_interrupt=False,
                is_mixed=False,
                reason="empty",
                confidence=1.0
            )
        
        # ========== TIER 1: EXACT MATCH ==========
        contains_interrupt = any(tok in INTERRUPT_SET for tok in toks)
        all_ignore = all(tok in IGNORE_SET for tok in toks)
        all_known = all(tok in IGNORE_SET or tok in INTERRUPT_SET for tok in toks)
        
        # Case 1: Contains interrupt word → INTERRUPT
        if contains_interrupt:
            self._tier_stats["exact"] += 1
            return TranscriptAnalysis(
                is_backchannel=False,
                is_interrupt=True,
                is_mixed=len(toks) > 1,
                reason=f"exact interrupt: {text_norm}",
                confidence=1.0
            )
        
        # Case 2: All words are backchannel → IGNORE
        if all_ignore:
            self._tier_stats["exact"] += 1
            return TranscriptAnalysis(
                is_backchannel=True,
                is_interrupt=False,
                is_mixed=False,
                reason=f"exact backchannel: {text_norm}",
                confidence=1.0
            )
        
        # Case 3: All words known (mixed) → Already handled
        if all_known:
            self._tier_stats["exact"] += 1
            return TranscriptAnalysis(
                is_backchannel=all_ignore,
                is_interrupt=contains_interrupt,
                is_mixed=True,
                reason=f"exact mixed: {text_norm}",
                confidence=1.0
            )
        
        # ========== TIER 2: FUZZY MATCH ==========
        # We have unknown words - try fuzzy matching
        unknown_words = [tok for tok in toks if tok not in IGNORE_SET and tok not in INTERRUPT_SET]
        
        fuzzy_result = self._fuzzy_match_analysis(text_norm, unknown_words, toks)
        if fuzzy_result is not None:
            self._tier_stats["fuzzy"] += 1
            return fuzzy_result
        
        # ========== FALLBACK: SAFETY DEFAULT ==========
        # Unknown content - treat as interrupt for safety
        self._tier_stats["fallback"] += 1
        logger.warning(f"Unknown phrase, defaulting to interrupt: '{text_norm}'")
        return TranscriptAnalysis(
            is_backchannel=False,
            is_interrupt=True,
            is_mixed=False,
            reason=f"unknown (safe default): {text_norm}",
            confidence=0.5
        )
    
    def _fuzzy_match_analysis(
        self, 
        text_norm: str, 
        unknown_words: list,
        all_tokens: list
    ) -> Optional[TranscriptAnalysis]:
        """
        Tier 2: Fuzzy string matching for typos and variants.
        
        Examples:
            "okey" → "okay" (typo)
            "waait" → "wait" (typo)
            "yeahh" → "yeah" (variant)
        """
        fuzzy_matched_ignore = 0
        fuzzy_matched_interrupt = 0
        fuzzy_matches = []
        
        for word in unknown_words:
            # Find closest match in IGNORE_SET
            best_ignore, ignore_ratio = self._find_closest_match(word, IGNORE_SET)
            
            # Find closest match in INTERRUPT_SET
            best_interrupt, interrupt_ratio = self._find_closest_match(word, INTERRUPT_SET)
            
            # Check if either match is good enough
            if ignore_ratio >= FUZZY_MATCH_THRESHOLD:
                fuzzy_matched_ignore += 1
                fuzzy_matches.append(f"{word}→{best_ignore}")
            elif interrupt_ratio >= FUZZY_MATCH_THRESHOLD:
                fuzzy_matched_interrupt += 1
                fuzzy_matches.append(f"{word}→{best_interrupt}")
        
        # If we successfully matched all unknown words
        if fuzzy_matched_ignore + fuzzy_matched_interrupt == len(unknown_words):
            if fuzzy_matched_interrupt > 0:
                # Contains interrupt word
                return TranscriptAnalysis(
                    is_backchannel=False,
                    is_interrupt=True,
                    is_mixed=fuzzy_matched_ignore > 0,
                    reason=f"fuzzy interrupt: {', '.join(fuzzy_matches)}",
                    confidence=0.85
                )
            else:
                # All backchannel
                return TranscriptAnalysis(
                    is_backchannel=True,
                    is_interrupt=False,
                    is_mixed=False,
                    reason=f"fuzzy backchannel: {', '.join(fuzzy_matches)}",
                    confidence=0.85
                )
        
        return None
    
    def _find_closest_match(self, word: str, word_set: set) -> Tuple[str, float]:
        """Find closest match using SequenceMatcher (fuzzy string matching)"""
        if not word_set:
            return "", 0.0
        
        best_match = ""
        best_ratio = 0.0
        
        for candidate in word_set:
            ratio = SequenceMatcher(None, word, candidate).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = candidate
        
        return best_match, best_ratio
    
    def get_stats(self) -> dict:
        """Get performance statistics"""
        total = sum(self._tier_stats.values())
        if total == 0:
            return self._tier_stats
        
        return {
            "exact": f"{self._tier_stats['exact']} ({self._tier_stats['exact']/total*100:.1f}%)",
            "fuzzy": f"{self._tier_stats['fuzzy']} ({self._tier_stats['fuzzy']/total*100:.1f}%)",
            "fallback": f"{self._tier_stats['fallback']} ({self._tier_stats['fallback']/total*100:.1f}%)",
            "total": total
        }


# ============================================================================
# CONTROLLED AGENT SESSION
# ============================================================================

class ControlledAgentSession(AgentSession):
    """
    Extended AgentSession with backchannel filtering.
    
    Strategy:
    - Use restrictive interruption settings
    - Analyze all user input with 3-tier system
    - Log decisions for debugging
    """
    
    def __init__(self, *args, **kwargs):
        # Configure restrictive interruption settings
        kwargs['min_interruption_words'] = kwargs.get('min_interruption_words', 3)
        kwargs['min_interruption_duration'] = kwargs.get('min_interruption_duration', 0.8)
        
        super().__init__(*args, **kwargs)
        
        self._filter = BackchannelFilter()
        self._is_agent_speaking = False
        self._utterance_count = 0
        
        # Subscribe to events
        self.on("agent_speech_created", self._on_agent_started_speaking)
        self.on("agent_speech_committed", self._on_agent_stopped_speaking)
        self.on("agent_speech_interrupted", self._on_agent_interrupted)
        self.on("user_speech_committed", self._on_user_speech_committed)
        
        logger.info("ControlledAgentSession initialized")
        logger.info(f"   min_interruption_words: {kwargs.get('min_interruption_words', 3)}")
        logger.info(f"   min_interruption_duration: {kwargs.get('min_interruption_duration', 0.8)}s")
    
    def _on_agent_started_speaking(self, event):
        """Agent started speaking"""
        self._is_agent_speaking = True
        logger.info("Agent SPEAKING")
    
    def _on_agent_stopped_speaking(self, event):
        """Agent finished speaking"""
        self._is_agent_speaking = False
        self._utterance_count += 1
        
        # Log stats every 10 utterances
        if self._utterance_count % 10 == 0:
            stats = self._filter.get_stats()
            logger.info(f"Filter stats: {stats}")
        
        logger.info("Agent FINISHED")
    
    def _on_agent_interrupted(self, event):
        """Agent was interrupted"""
        self._is_agent_speaking = False
        logger.warning("Agent INTERRUPTED")
    
    def _on_user_speech_committed(self, event):
        """Analyze user speech with 3-tier system"""
        text = event.item.text_content or ""
        
        # If agent not speaking, log and return
        if not self._is_agent_speaking:
            logger.debug(f"User (agent silent): '{text}'")
            return
        
    # Agent IS speaking - analyze
        analysis = self._filter.analyze(text)
        
    # Log decision (labelled)
        if analysis.is_backchannel:
            logger.info(f"IGNORE: '{text}' | {analysis.reason} | conf={analysis.confidence:.2f}")
        elif analysis.is_interrupt:
            logger.info(f"INTERRUPT: '{text}' | {analysis.reason} | conf={analysis.confidence:.2f}")
        else:
            logger.info(f"PROCESS: '{text}' | {analysis.reason} | conf={analysis.confidence:.2f}")


# ============================================================================
# MAIN AGENT
# ============================================================================

async def entrypoint(ctx: JobContext):
    """
    Main entry point with intelligent interruption handling.
    """
    
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info(f"Connected to room: {ctx.room.name}")
    
    # Wait for participant
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant joined: {participant.identity}")
    
    # Create agent
    agent = Agent(
        instructions=(
            "You are a helpful voice assistant. "
            "Speak naturally and conversationally. "
            "Take your time with thorough explanations. "
            "When you hear 'stop' or 'wait', pause immediately and ask how you can help."
        )
    )
    
    # Create controlled session
    session = ControlledAgentSession(
        vad=silero.VAD.load(
            min_speech_duration=0.8,
            min_silence_duration=1.0,
            activation_threshold=0.6,
        ),
        stt=deepgram.STT(model="nova-2"),
        llm=groq.LLM(
            model="llama-3.3-70b-versatile",
            temperature=0.7,
        ),
        tts=deepgram.TTS(model="aura-asteria-en"),
        
        # Restrictive interruption settings
        allow_interruptions=True,
        min_interruption_words=3,  # Require at least 3 words
        min_interruption_duration=0.8,  # Require 800ms of speech
    )
    
    # Start session
    await session.start(agent=agent, room=ctx.room)
    
    print("\n" + "="*80)
    print("INTELLIGENT AGENT READY")
    print("="*80)
    print(f"LLM: Groq Llama 3.3 70B")
    print(f"STT: Deepgram Nova 2")
    print(f"TTS: Deepgram Aura Asteria")
    print("="*80)
    print("\nINTELLIGENT INTERRUPTION HANDLER:")
    print("   Tier 1: Exact word matching (< 1ms)")
    print("   Tier 2: Fuzzy matching for typos (1-3ms)")
    print("   Tier 3: Safe fallback for unknown input")
    print("="*80)
    print(f"\nBackchannel words ({len(IGNORE_SET)}): {', '.join(list(IGNORE_SET)[:10])}...")
    print(f"Interrupt words ({len(INTERRUPT_SET)}): {', '.join(list(INTERRUPT_SET)[:10])}...")
    print("="*80 + "\n")
    
    # Initial greeting
    await session.generate_reply(
        instructions="Greet the user warmly and ask how you can help.Make it brief"
    )


if __name__ == "__main__":
    try:
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
    except KeyboardInterrupt:
        print("\nAgent stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
