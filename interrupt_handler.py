# interrupt_handler.py
import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Optional, Dict, Tuple
from difflib import SequenceMatcher
from dotenv import load_dotenv
_ = load_dotenv(override=True)

logger = logging.getLogger("dlai-agent")
logger.setLevel(logging.INFO)

from livekit import agents
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions
from livekit.plugins import openai, elevenlabs, silero
from livekit.agents.metrics import LLMMetrics, STTMetrics, TTSMetrics, EOUMetrics

# -------------------------
# Lazy import for sentence transformers (only loaded if needed)
# -------------------------
_semantic_model = None
_backchannel_embedding = None
_interrupt_embedding = None

def get_semantic_model():
    """Lazy load semantic model on first use"""
    global _semantic_model, _backchannel_embedding, _interrupt_embedding
    
    if _semantic_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            
            # Choose model based on strict latency requirement
            # paraphrase-MiniLM-L3-v2: 60MB, ~15ms encoding time
            # all-MiniLM-L6-v2: 80MB, ~25ms encoding time
            # Decision: Use L3 for speed (strict requirement: agent must NOT pause)
            model_name = os.getenv("SEMANTIC_MODEL", "paraphrase-MiniLM-L3-v2")
            logger.info(f"Loading semantic model: {model_name}")
            
            _semantic_model = SentenceTransformer(model_name)
            
            # Pre-compute embeddings at startup (one-time cost)
            logger.info("Pre-computing backchannel and interrupt embeddings...")
            _backchannel_embedding = _semantic_model.encode(
                "yeah okay right mmhmm uh huh got it understood sure alright yep gotcha"
            )
            _interrupt_embedding = _semantic_model.encode(
                "wait stop hold no pause halt hang on hold on actually"
            )
            logger.info("Semantic model loaded and embeddings pre-computed")
            
        except ImportError:
            logger.warning("sentence-transformers not installed. Semantic fallback disabled.")
            logger.warning("Install with: pip install sentence-transformers")
            return None
    
    return _semantic_model


# -------------------------
# Configuration
# -------------------------
IGNORE_WORDS = os.getenv("IGNORE_WORDS", "yeah,ok,okay,hmm,uh-huh,uhhuh,uh huh,alright,right,mmhmm,yep,gotcha,sure").split(",")
INTERRUPT_WORDS = os.getenv("INTERRUPT_WORDS", "stop,wait,no,hold on,hold,hang on,pause,stop it,halt,actually").split(",")

# Semantic similarity thresholds
BACKCHANNEL_THRESHOLD = float(os.getenv("BACKCHANNEL_THRESHOLD", "0.75"))
INTERRUPT_THRESHOLD = float(os.getenv("INTERRUPT_THRESHOLD", "0.30"))

# Fuzzy match threshold
FUZZY_MATCH_THRESHOLD = float(os.getenv("FUZZY_MATCH_THRESHOLD", "0.80"))

# Cache settings
SEMANTIC_CACHE_TTL = int(os.getenv("SEMANTIC_CACHE_TTL", "3600"))  # 1 hour

# Normalize strings
def normalize_text(s: str) -> str:
    return re.sub(r"[^\w\s]", "", s.lower()).strip()

IGNORE_SET = {normalize_text(w) for w in IGNORE_WORDS if w}
INTERRUPT_SET = {normalize_text(w) for w in INTERRUPT_WORDS if w}

def tokens_of(s: str):
    s = normalize_text(s)
    return [t for t in s.split() if t]


@dataclass
class TranscriptAnalysis:
    """Analysis result of a transcript"""
    is_backchannel: bool
    is_interrupt: bool
    is_mixed: bool
    reason: str
    confidence: float = 1.0  # How confident we are (1.0 = exact match, 0.0-1.0 = semantic)


class BackchannelFilter:
    """
    Three-tier transcript analysis system:
    1. Exact match (< 1ms) - highest priority
    2. Fuzzy string match (1-3ms) - catches typos/variants
    3. Semantic similarity (15-25ms) - catches unknown phrases
    """
    
    def __init__(self):
        self._semantic_cache: Dict[str, Tuple[TranscriptAnalysis, float]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._tier_stats = {"exact": 0, "fuzzy": 0, "semantic": 0, "cache": 0}
    
    def analyze(self, text: str) -> TranscriptAnalysis:
        """
        Analyze transcript using three-tier hybrid approach.
        
        Returns:
            TranscriptAnalysis with classification
        """
        text_norm = normalize_text(text)
        toks = tokens_of(text_norm)
        
        if not toks:
            return TranscriptAnalysis(
                is_backchannel=True,
                is_interrupt=False,
                is_mixed=False,
                reason="empty",
                confidence=1.0
            )
        
        # ================== TIER 1: EXACT MATCH (< 1ms) ==================
        contains_interrupt = any(tok in INTERRUPT_SET for tok in toks)
        all_ignore = all(tok in IGNORE_SET for tok in toks)
        all_known = all(tok in IGNORE_SET or tok in INTERRUPT_SET for tok in toks)
        
        if contains_interrupt:
            self._tier_stats["exact"] += 1
            return TranscriptAnalysis(
                is_backchannel=False,
                is_interrupt=True,
                is_mixed=len(toks) > 1,
                reason=f"exact interrupt match: {text_norm}",
                confidence=1.0
            )
        
        if all_ignore:
            self._tier_stats["exact"] += 1
            return TranscriptAnalysis(
                is_backchannel=True,
                is_interrupt=False,
                is_mixed=False,
                reason=f"exact backchannel match: {text_norm}",
                confidence=1.0
            )
        
        # If all tokens are known (mix of ignore/interrupt), we already handled it
        if all_known:
            self._tier_stats["exact"] += 1
            return TranscriptAnalysis(
                is_backchannel=all_ignore,
                is_interrupt=contains_interrupt,
                is_mixed=True,
                reason=f"known words mixed: {text_norm}",
                confidence=1.0
            )
        
        # ================== TIER 2: FUZZY MATCH (1-3ms) ==================
        # Unknown words detected - try fuzzy matching first
        unknown_words = [tok for tok in toks if tok not in IGNORE_SET and tok not in INTERRUPT_SET]
        
        fuzzy_result = self._fuzzy_match_analysis(text_norm, unknown_words)
        if fuzzy_result is not None:
            self._tier_stats["fuzzy"] += 1
            return fuzzy_result
        
        # ================== TIER 3: SEMANTIC SIMILARITY (15-25ms) ==================
        # Check cache first
        if text_norm in self._semantic_cache:
            cached_result, timestamp = self._semantic_cache[text_norm]
            if time.time() - timestamp < SEMANTIC_CACHE_TTL:
                self._cache_hits += 1
                self._tier_stats["cache"] += 1
                logger.debug(f"Cache hit for: '{text_norm}'")
                return cached_result
            else:
                # Expired cache entry
                del self._semantic_cache[text_norm]
        
        self._cache_misses += 1
        
        # Perform semantic analysis
        semantic_result = self._semantic_analysis(text_norm)
        
        if semantic_result is not None:
            self._tier_stats["semantic"] += 1
            # Cache the result
            self._semantic_cache[text_norm] = (semantic_result, time.time())
            return semantic_result
        
        # ================== FALLBACK: TREAT AS INTERRUPT (SAFE DEFAULT) ==================
        logger.warning(f"No classification method succeeded for: '{text_norm}' - defaulting to interrupt")
        return TranscriptAnalysis(
            is_backchannel=False,
            is_interrupt=True,
            is_mixed=False,
            reason=f"unknown content (safe default): {text_norm}",
            confidence=0.5
        )
    
    def _fuzzy_match_analysis(self, text_norm: str, unknown_words: list) -> Optional[TranscriptAnalysis]:
        """
        Tier 2: Fuzzy string matching to catch typos and variants.
        Examples: "okey" → "okay", "waait" → "wait", "yep" → "yep"
        """
        fuzzy_matched_ignore = 0
        fuzzy_matched_interrupt = 0
        fuzzy_matches = []
        
        for word in unknown_words:
            # Find closest match in IGNORE_SET
            best_ignore_match, ignore_ratio = self._find_closest_match(word, IGNORE_SET)
            
            # Find closest match in INTERRUPT_SET
            best_interrupt_match, interrupt_ratio = self._find_closest_match(word, INTERRUPT_SET)
            
            if ignore_ratio >= FUZZY_MATCH_THRESHOLD:
                fuzzy_matched_ignore += 1
                fuzzy_matches.append(f"{word}→{best_ignore_match}")
            elif interrupt_ratio >= FUZZY_MATCH_THRESHOLD:
                fuzzy_matched_interrupt += 1
                fuzzy_matches.append(f"{word}→{best_interrupt_match}")
        
        # If we matched all unknown words via fuzzy matching
        if fuzzy_matched_ignore + fuzzy_matched_interrupt == len(unknown_words):
            if fuzzy_matched_interrupt > 0:
                return TranscriptAnalysis(
                    is_backchannel=False,
                    is_interrupt=True,
                    is_mixed=fuzzy_matched_ignore > 0,
                    reason=f"fuzzy interrupt match: {', '.join(fuzzy_matches)}",
                    confidence=0.85
                )
            else:
                return TranscriptAnalysis(
                    is_backchannel=True,
                    is_interrupt=False,
                    is_mixed=False,
                    reason=f"fuzzy backchannel match: {', '.join(fuzzy_matches)}",
                    confidence=0.85
                )
        
        return None
    
    def _find_closest_match(self, word: str, word_set: set) -> Tuple[str, float]:
        """Find closest match in word_set using SequenceMatcher"""
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
    
    def _semantic_analysis(self, text_norm: str) -> Optional[TranscriptAnalysis]:
        """
        Tier 3: Semantic similarity using sentence transformers.
        Only called for truly unknown phrases.
        """
        model = get_semantic_model()
        
        if model is None:
            logger.debug("Semantic model not available, skipping semantic analysis")
            return None
        
        try:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Encode user input
            start_time = time.time()
            user_embedding = model.encode(text_norm)
            encode_time = (time.time() - start_time) * 1000
            
            # Compute similarities
            backchannel_sim = cosine_similarity(
                user_embedding.reshape(1, -1),
                _backchannel_embedding.reshape(1, -1)
            )[0][0]
            
            interrupt_sim = cosine_similarity(
                user_embedding.reshape(1, -1),
                _interrupt_embedding.reshape(1, -1)
            )[0][0]
            
            logger.debug(f"Semantic analysis: '{text_norm}' | "
                        f"Backchannel: {backchannel_sim:.3f} | "
                        f"Interrupt: {interrupt_sim:.3f} | "
                        f"Time: {encode_time:.1f}ms")
            
            # Decision logic
            if backchannel_sim >= BACKCHANNEL_THRESHOLD:
                return TranscriptAnalysis(
                    is_backchannel=True,
                    is_interrupt=False,
                    is_mixed=False,
                    reason=f"semantic backchannel (sim={backchannel_sim:.2f}): {text_norm}",
                    confidence=float(backchannel_sim)
                )
            elif interrupt_sim >= BACKCHANNEL_THRESHOLD or backchannel_sim < INTERRUPT_THRESHOLD:
                # Either high interrupt similarity OR very low backchannel similarity
                return TranscriptAnalysis(
                    is_backchannel=False,
                    is_interrupt=True,
                    is_mixed=False,
                    reason=f"semantic interrupt (b_sim={backchannel_sim:.2f}, i_sim={interrupt_sim:.2f}): {text_norm}",
                    confidence=float(interrupt_sim) if interrupt_sim > backchannel_sim else float(1.0 - backchannel_sim)
                )
            else:
                # Ambiguous - default to interrupt for safety
                return TranscriptAnalysis(
                    is_backchannel=False,
                    is_interrupt=True,
                    is_mixed=False,
                    reason=f"semantic ambiguous (b={backchannel_sim:.2f}, i={interrupt_sim:.2f}): {text_norm}",
                    confidence=0.5
                )
        
        except Exception as e:
            logger.error(f"Semantic analysis error: {e}", exc_info=True)
            return None
    
    def get_stats(self) -> dict:
        """Get statistics about filter performance"""
        total_cache = self._cache_hits + self._cache_misses
        cache_hit_rate = (self._cache_hits / total_cache * 100) if total_cache > 0 else 0
        
        return {
            "tier_stats": self._tier_stats,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": f"{cache_hit_rate:.1f}%",
            "cache_size": len(self._semantic_cache)
        }


class ControlledAgentSession(AgentSession):
    """
    Extended AgentSession that implements backchannel filtering.
    
    Key strategy:
    1. Use high min_interruption_words to prevent automatic interruption on short utterances
    2. Subscribe to user_speech_committed events to analyze transcripts
    3. Use three-tier analysis: exact → fuzzy → semantic
    """
    
    def __init__(self, *args, **kwargs):
        # Configure session to be MORE restrictive about interruptions
        kwargs['min_interruption_words'] = kwargs.get('min_interruption_words', 3)
        kwargs['min_interruption_duration'] = kwargs.get('min_interruption_duration', 0.8)
        kwargs['false_interruption_timeout'] = kwargs.get('false_interruption_timeout', 1.5)
        kwargs['resume_false_interruption'] = kwargs.get('resume_false_interruption', True)
        
        super().__init__(*args, **kwargs)
        
        self._filter = BackchannelFilter()
        self._is_agent_speaking = False
        
        # Subscribe to events
        self.on("agent_started_speaking", self._on_agent_started_speaking)
        self.on("agent_stopped_speaking", self._on_agent_stopped_speaking)
        self.on("user_speech_committed", self._on_user_speech_committed)
        
        logger.info(f"Backchannel filtering enabled (3-tier hybrid system)")
        logger.info(f"  Ignore words: {len(IGNORE_SET)}, Interrupt words: {len(INTERRUPT_SET)}")
        logger.info(f"  Fuzzy threshold: {FUZZY_MATCH_THRESHOLD}, Semantic thresholds: B={BACKCHANNEL_THRESHOLD}, I={INTERRUPT_THRESHOLD}")
    
    def _on_agent_started_speaking(self, event):
        """Track when agent starts speaking"""
        self._is_agent_speaking = True
        logger.debug("Agent started speaking")
    
    def _on_agent_stopped_speaking(self, event):
        """Track when agent stops speaking"""
        self._is_agent_speaking = False
        # Log statistics periodically
        if hasattr(self, '_utterance_count'):
            self._utterance_count += 1
            if self._utterance_count % 20 == 0:
                stats = self._filter.get_stats()
                logger.info(f"Filter stats: {stats}")
        else:
            self._utterance_count = 1
        logger.debug("Agent stopped speaking")
    
    def _on_user_speech_committed(self, event):
        """Analyze committed user speech with three-tier system"""
        if not self._is_agent_speaking:
            logger.debug(f"User input (agent silent): '{event.item.text_content}'")
            return
        
        # Agent is speaking - analyze the transcript
        text = event.item.text_content or ""
        analysis = self._filter.analyze(text)
        
        if analysis.is_backchannel:
            logger.info(f"✓ Backchannel: '{text}' | {analysis.reason} | confidence={analysis.confidence:.2f}")
        elif analysis.is_interrupt:
            if event.item.interrupted:
                logger.info(f"✗ Interrupt: '{text}' | {analysis.reason} | confidence={analysis.confidence:.2f} [INTERRUPTED]")
            else:
                logger.info(f"⚠ Interrupt word but no stop: '{text}' | {analysis.reason} | confidence={analysis.confidence:.2f}")
        else:
            logger.debug(f"User speech: '{text}' | {analysis.reason}")


# -------------------------
# Agent Implementation
# -------------------------
class ControlledAgent(Agent):
    """Agent with integrated metrics tracking"""
    
    def __init__(self, *args, **kwargs):
        llm = openai.LLM(model=os.getenv("LLM_MODEL", "gpt-4o"))
        stt = openai.STT(model=os.getenv("STT_MODEL", "whisper-1"))
        tts = elevenlabs.TTS()
        vad = silero.VAD.load()
        
        super().__init__(
            instructions="You are a helpful assistant communicating via voice. Keep responses concise and natural.",
            stt=stt,
            llm=llm,
            tts=tts,
            vad=vad,
            *args,
            **kwargs
        )
        
        llm.on("metrics_collected", self._on_llm_metrics)
        stt.on("metrics_collected", self._on_stt_metrics)
        stt.on("eou_metrics_collected", self._on_eou_metrics)
        tts.on("metrics_collected", self._on_tts_metrics)
    
    def _on_llm_metrics(self, metrics: LLMMetrics):
        logger.info(f"[LLM] {metrics.prompt_tokens}+{metrics.completion_tokens} tok, "
                   f"{metrics.tokens_per_second:.1f} tok/s, TTFT: {metrics.ttft:.3f}s")
    
    def _on_stt_metrics(self, metrics: STTMetrics):
        logger.info(f"[STT] {metrics.duration:.3f}s, audio: {metrics.audio_duration:.3f}s")
    
    def _on_eou_metrics(self, metrics: EOUMetrics):
        logger.info(f"[EOU] delay: {metrics.end_of_utterance_delay:.3f}s")
    
    def _on_tts_metrics(self, metrics: TTSMetrics):
        logger.info(f"[TTS] TTFB: {metrics.ttfb:.3f}s, audio: {metrics.audio_duration:.3f}s")


# -------------------------
# Entrypoint
# -------------------------
async def entrypoint(ctx: JobContext):
    """Direct room join (bypasses LiveKit Jobs, perfect for testing)."""
    await ctx.connect()

    # Pre-load semantic model asynchronously
    asyncio.create_task(asyncio.to_thread(get_semantic_model))

    # FORCE the agent to join a room directly
    ROOM_NAME = os.getenv("ROOM_NAME", "test_room")

    logger.info(f"Joining room: {ROOM_NAME}")
    room = await ctx.join(ROOM_NAME)

    session = ControlledAgentSession(
        min_interruption_words=3,
        min_interruption_duration=0.8,
        false_interruption_timeout=1.5,
        resume_false_interruption=True,
    )

    await session.start(
        agent=ControlledAgent(),
        room=room,
    )

    logger.info("Agent session started (DIRECT ROOM MODE)")



if __name__ == "__main__":
    import asyncio
    from livekit import api

    async def _run_direct():
        # Direct-mode context to mimic JobContext
        class DirectContext:
            async def connect(self):
                # No-op for direct mode
                pass

            async def join(self, room_name: str):
                server_url = os.getenv("LIVEKIT_URL")
                api_key = os.getenv("LIVEKIT_API_KEY")
                api_secret = os.getenv("LIVEKIT_API_SECRET")

                if not server_url or not api_key or not api_secret:
                    raise RuntimeError(
                        "Missing LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET"
                    )

                # Create token for the agent
                token = (
                    api.AccessToken(api_key, api_secret)
                    .with_identity("agent-bot")
                    .with_name("VoiceAgent")
                    .with_grants(
                        api.VideoGrants(
                            room=room_name,
                            can_publish=True,
                            can_subscribe=True,
                        )
                    )
                    .to_jwt()
                )

                # Correct class for latest LiveKit Agents: Room
                from livekit.agents import Room
                room = Room(server_url, token)
                await room.connect()

                return room

        ctx = DirectContext()
        await entrypoint(ctx)

    asyncio.run(_run_direct())
