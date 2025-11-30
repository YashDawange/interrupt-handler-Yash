import asyncio
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from ..log import logger

if TYPE_CHECKING:
    from .agent_activity import AgentActivity


class InterruptionHandler:
 
    def __init__(
        self,
        ignore_words: list[str] | None = None,
        interrupt_words: list[str] | None = None,
        use_embeddings: bool | None = None,
        embedding_similarity_threshold: float = 0.75,
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        """
        Initialize the interruption handler.

        Args:
            ignore_words: List of words to ignore when agent is speaking.
                         Defaults to common backchanneling words.
            interrupt_words: List of words that should always interrupt.
                             Defaults to common interruption commands.
            use_embeddings: Whether to use OpenAI embeddings for semantic similarity.
                          If None, checks LIVEKIT_AGENT_USE_EMBEDDINGS env var.
            embedding_similarity_threshold: Cosine similarity threshold for backchanneling (0.0-1.0).
                                           Higher = more strict. Default: 0.75
            embedding_model: OpenAI embedding model to use. Default: text-embedding-3-small
        """
        # Get ignore words from environment variable or use defaults
        env_ignore = os.getenv("LIVEKIT_AGENT_IGNORE_WORDS")
        if env_ignore:
            self._ignore_words = [
                word.strip().lower() for word in env_ignore.split(",") if word.strip()
            ]
        elif ignore_words is None:
            # Default backchanneling words
            self._ignore_words = [
                "yeah", "ok", "okay", "hmm", "uh-huh", "right", "sure", "yep", 
                "mhm", "aha", "mm-hmm", "uh-huh", "got it", "i see", "alright"
            ]
        else:
            self._ignore_words = ignore_words

        # Get interrupt words from environment variable or use defaults
        env_interrupt = os.getenv("LIVEKIT_AGENT_INTERRUPT_WORDS")
        if env_interrupt:
            self._interrupt_words = [
                word.strip().lower() for word in env_interrupt.split(",") if word.strip()
            ]
        elif interrupt_words is None:
            # Default interrupt words
            self._interrupt_words = ["stop", "wait", "no", "halt", "cancel", "pause"]
        else:
            self._interrupt_words = interrupt_words

        # Normalize all words to lowercase for comparison
        self._ignore_words = [word.lower() for word in self._ignore_words]
        self._interrupt_words = [word.lower() for word in self._interrupt_words]

        # Embedding-based checking configuration
        if use_embeddings is None:
            self._use_embeddings = os.getenv("LIVEKIT_AGENT_USE_EMBEDDINGS", "").lower() in ("true", "1", "yes")
        else:
            self._use_embeddings = use_embeddings
        
        self._embedding_similarity_threshold = float(
            os.getenv("LIVEKIT_AGENT_EMBEDDING_THRESHOLD", embedding_similarity_threshold)
        )
        self._embedding_model = os.getenv("LIVEKIT_AGENT_EMBEDDING_MODEL", embedding_model)
        
        # Cache for embeddings
        self._backchanneling_embeddings: dict[str, list[float]] = {}
        self._embedding_cache_lock = asyncio.Lock()
        self._embeddings_initialized = False
        self._embeddings_initialization_task: asyncio.Task | None = None
        self._transcript_embedding_cache: dict[str, tuple[list[float], float]] = {}  # transcript -> (embedding, timestamp)
        self._cache_ttl = 3600.0  # Cache embeddings for 1 hour
        self._pending_transcript_embeddings: set[str] = set()  # Transcripts being fetched

        logger.info(
            f"InterruptionHandler initialized with ignore_words={self._ignore_words}, "
            f"interrupt_words={self._interrupt_words}, "
            f"use_embeddings={self._use_embeddings}, "
            f"embedding_threshold={self._embedding_similarity_threshold}"
        )
    
    async def initialize_embeddings(self) -> None:
        """
        Initialize backchanneling embeddings in an async context (main thread).
        This should be called from AgentActivity.start() to ensure plugins are registered.
        """
        if self._use_embeddings and not self._embeddings_initialized:
            try:
                await self._initialize_backchanneling_embeddings()
            except Exception as e:
                logger.error(f"Failed to initialize embeddings: {e}. Disabling embedding-based checking.")
                self._use_embeddings = False

    @property
    def ignore_words(self) -> list[str]:
        """Get the list of words to ignore when agent is speaking."""
        return self._ignore_words.copy()

    @property
    def interrupt_words(self) -> list[str]:
        """Get the list of words that should always interrupt."""
        return self._interrupt_words.copy()

    def should_interrupt(
        self, transcript: str, agent_is_speaking: bool, activity: "AgentActivity | None" = None
    ) -> bool:
        """
        Determine if an interruption should occur based on the transcript and agent state.
        """
        if not transcript or not transcript.strip():
            return False

        # Normalize transcript to lowercase for comparison
        transcript_lower = transcript.lower().strip()
        
        logger.debug(
            f"Checking should_interrupt for transcript: '{transcript}' "
            f"(normalized: '{transcript_lower}', agent_speaking={agent_is_speaking})"
        )

        # Split transcript into words, handling punctuation
        words = self._extract_words(transcript_lower)

        if not words:
            logger.debug(f"No words extracted from transcript: '{transcript}'")
            return False

        # Check for interrupt words first (these always interrupt)
        for word in words:
            if word in self._interrupt_words:
                logger.info(
                    f"Interrupt word detected: '{word}' in transcript '{transcript}' "
                    f"(agent_speaking={agent_is_speaking})"
                )
                return True

        # If agent is not speaking, always process the input
        if not agent_is_speaking:
            logger.debug(
                f"Agent is silent, processing input: '{transcript}' "
                f"(agent_speaking={agent_is_speaking})"
            )
            return True

        # Agent is speaking - check if transcript is backchanneling
        # Try embedding-based check first if enabled, then fall back to word matching
        is_backchanneling = False
        
        if self._use_embeddings:
            try:
                is_backchanneling = self._check_backchanneling_with_embeddings(transcript)
                if is_backchanneling:
                    logger.debug(
                        f"Embedding-based check: '{transcript}' identified as backchanneling "
                        f"(similarity >= {self._embedding_similarity_threshold})"
                    )
            except Exception as e:
                logger.warning(
                    f"Embedding-based check failed for '{transcript}': {e}. "
                    f"Falling back to word-based matching."
                )
                # Fall through to word-based check
        
        # Fall back to word-based matching if embeddings not used or failed
        if not is_backchanneling:
            # Use fuzzy matching to handle variations (e.g., "mhmm" vs "mhm")
            all_ignored = all(self._is_ignorable_word(word) for word in words)
            
            logger.debug(
                f"Agent speaking - checking if all words ignored: words={words}, "
                f"all_ignored={all_ignored}, ignore_words={self._ignore_words}"
            )

            is_backchanneling = all_ignored

        if is_backchanneling:
            # All words are backchanneling - ignore this interruption
            logger.info(
                f"Ignoring backchanneling while agent is speaking: '{transcript}' "
                f"(words={words}, agent_speaking={agent_is_speaking})"
            )
            return False
        
        # Debug: Log when words are NOT all ignored
        if words:
            ignored_words = [w for w in words if self._is_ignorable_word(w)]
            non_ignored_words = [w for w in words if not self._is_ignorable_word(w)]
            if non_ignored_words:
                logger.debug(
                    f"Not all words ignored: ignored={ignored_words}, non_ignored={non_ignored_words} "
                    f"from transcript '{transcript}'"
                )

        # Mixed input: contains both ignore words and non-ignore words
        # This should interrupt (e.g., "yeah okay but wait")
        logger.debug(
            f"Mixed input detected, interrupting: '{transcript}' "
            f"(words={words}, agent_speaking={agent_is_speaking})"
        )
        return True

    def _is_ignorable_word(self, word: str) -> bool:
        """
        Check if a word is ignorable, handling variations and fuzzy matching.
        """
        word_lower = word.lower().strip()
        
        # Exact match
        if word_lower in self._ignore_words:
            return True
        
        # Handle variations of common backchanneling words
        # "mhmm", "mmhmm", "mm-hmm" should match "mhm"
        if word_lower in ["mhmm", "mmhmm", "mm-hmm", "mmhmm"]:
            return "mhm" in self._ignore_words
        
        # "hmmm", "hmm" variations
        if word_lower.startswith("hmm") and "hmm" in self._ignore_words:
            return True
        
        # "uhm", "umm" variations of "um"
        if word_lower in ["uhm", "umm"] and "um" in self._ignore_words:
            return True
        
        return False

    def _extract_words(self, text: str) -> list[str]:
        """
        Extract words from text, handling punctuation and contractions.
        """
        if not text:
            return []
            
        # Normalize text - remove extra whitespace and convert to lowercase
        text = text.lower().strip()
        
        # Remove punctuation and split into words
        # Keep hyphens for words like "uh-huh"
        # This regex matches word boundaries and includes hyphens
        words = re.findall(r"\b[\w-]+\b", text)
        result = [word.strip().lower() for word in words if word.strip()]
        
        # Debug logging to help troubleshoot
        logger.debug(f"Extracted words from '{text}': {result}")
        
        return result

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        Returns a value between -1 and 1, where 1 means identical.
        """
        if not NUMPY_AVAILABLE:
            # Manual implementation if numpy not available
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            magnitude1 = sum(a * a for a in vec1) ** 0.5
            magnitude2 = sum(b * b for b in vec2) ** 0.5
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            return dot_product / (magnitude1 * magnitude2)
        
        # Use numpy for better performance
        vec1_array = np.array(vec1)
        vec2_array = np.array(vec2)
        dot_product = np.dot(vec1_array, vec2_array)
        magnitude1 = np.linalg.norm(vec1_array)
        magnitude2 = np.linalg.norm(vec2_array)
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return float(dot_product / (magnitude1 * magnitude2))

    async def _initialize_backchanneling_embeddings(self) -> None:
        """
        Initialize embeddings for backchanneling words/phrases.
        This is called lazily on first use to avoid blocking initialization.
        """
        if self._embeddings_initialized:
            return
        
        async with self._embedding_cache_lock:
            # Double-check after acquiring lock
            if self._embeddings_initialized:
                return
            
            try:
                # Use direct HTTP call to avoid plugin registration issues
                # This bypasses the plugin system and calls OpenAI API directly
                import aiohttp
                import base64
                import struct
                from livekit.agents import utils
                
                # Create embeddings for all ignore words/phrases
                texts_to_embed = self._ignore_words.copy()
                
                # Also add common backchanneling phrases
                backchanneling_phrases = [
                    "got it", "i see", "i understand", "makes sense", 
                    "that's right", "exactly", "absolutely", "for sure",
                    "gotcha", "understood", "affirmative", "roger that",
                    "sounds good", "i get it", "makes sense", "that makes sense"
                ]
                texts_to_embed.extend(backchanneling_phrases)
                
                # Pre-cache embeddings for common words that frequently appear
                # This helps avoid the "embedding not cached yet" fallback for common words
                common_words = [
                    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
                    "what", "when", "where", "why", "how", "who", "which", "that",
                    "this", "these", "those", "can", "could", "should", "would", "will"
                ]
                texts_to_embed.extend(common_words)
                
                backchanneling_count = len(self._ignore_words) + len(backchanneling_phrases)
                total_count = len(texts_to_embed)
                
                logger.info(
                    f"Initializing embeddings for {backchanneling_count} backchanneling texts "
                    f"and pre-caching {total_count - backchanneling_count} common words..."
                )
                
                # Call OpenAI API directly
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY must be set")
                
                http_session = utils.http_context.http_session()
                
                async with http_session.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": self._embedding_model,
                        "input": texts_to_embed,
                        "encoding_format": "base64",
                    },
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise RuntimeError(f"OpenAI API error: {resp.status} - {error_text}")
                    
                    json_data = await resp.json()
                    embedding_data_list = []
                    for d in json_data["data"]:
                        bytes_data = base64.b64decode(d["embedding"])
                        num_floats = len(bytes_data) // 4
                        floats = list(struct.unpack("f" * num_floats, bytes_data))
                        embedding_data_list.append((d["index"], floats))
                
                # Store embeddings in cache (sort by index to match input order)
                embedding_data_list.sort(key=lambda x: x[0])
                
                # Separate backchanneling embeddings from common word embeddings
                import time
                current_time = time.time()
                
                for i, (_, embedding) in enumerate(embedding_data_list):
                    text = texts_to_embed[i]
                    if i < backchanneling_count:
                        # This is a backchanneling word/phrase - store in backchanneling embeddings
                        # These are used for similarity comparison
                        self._backchanneling_embeddings[text] = embedding
                    else:
                        # This is a common word - pre-cache it for faster future lookups
                        # When these words appear, we can immediately use embedding-based checking
                        self._transcript_embedding_cache[text] = (embedding, current_time)
                
                logger.info(
                    f"Pre-cached {len(common_words)} common word embeddings for immediate use"
                )
                
                self._embeddings_initialized = True
                logger.info(
                    f"Successfully initialized {len(self._backchanneling_embeddings)} backchanneling embeddings"
                )
            except Exception as e:
                logger.error(
                    f"Failed to initialize backchanneling embeddings: {e}. "
                    f"Falling back to word-based matching."
                )
                self._use_embeddings = False
                raise

    async def _get_transcript_embedding(self, transcript: str) -> list[float]:
        """
        Get embedding for a transcript. Uses caching to avoid repeated API calls.
        Uses direct HTTP call to avoid plugin registration issues.
        """
        import time
        import aiohttp
        import base64
        import struct
        from livekit.agents import utils
        
        # Check cache first
        transcript_lower = transcript.lower().strip()
        if transcript_lower in self._transcript_embedding_cache:
            embedding, timestamp = self._transcript_embedding_cache[transcript_lower]
            if time.time() - timestamp < self._cache_ttl:
                logger.debug(f"Using cached embedding for transcript: '{transcript}'")
                return embedding
            else:
                # Cache expired, remove it
                del self._transcript_embedding_cache[transcript_lower]
        
        try:
            # Call OpenAI API directly (bypasses plugin system)
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY must be set")
            
            http_session = utils.http_context.http_session()
            
            async with http_session.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": self._embedding_model,
                    "input": [transcript],
                    "encoding_format": "base64",
                },
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"OpenAI API error: {resp.status} - {error_text}")
                
                json_data = await resp.json()
                if json_data.get("data") and len(json_data["data"]) > 0:
                    d = json_data["data"][0]
                    bytes_data = base64.b64decode(d["embedding"])
                    num_floats = len(bytes_data) // 4
                    embedding = list(struct.unpack("f" * num_floats, bytes_data))
                    
                    # Cache the result
                    self._transcript_embedding_cache[transcript_lower] = (embedding, time.time())
                    return embedding
            
            return []
        except Exception as e:
            logger.error(f"Failed to get embedding for transcript '{transcript}': {e}")
            raise

    def _check_backchanneling_with_embeddings(self, transcript: str) -> bool:
        """
        Check if transcript is backchanneling using embedding similarity.
        This is a synchronous method that uses cached embeddings.
        If transcript embedding is not cached, falls back to word matching and
        schedules a background task to cache it for future use.
        """
        # Check if embeddings are initialized
        if not self._embeddings_initialized:
            logger.debug("Embeddings not initialized yet, falling back to word-based matching.")
            return False
        
        if not self._backchanneling_embeddings:
            logger.debug("No backchanneling embeddings available, falling back to word-based matching.")
            return False
        
        # Check cache first
        transcript_lower = transcript.lower().strip()
        import time
        transcript_embedding = None
        
        if transcript_lower in self._transcript_embedding_cache:
            embedding, timestamp = self._transcript_embedding_cache[transcript_lower]
            if time.time() - timestamp < self._cache_ttl:
                transcript_embedding = embedding
            else:
                # Cache expired
                del self._transcript_embedding_cache[transcript_lower]
        
        # If not cached, try to get it from background task (non-blocking)
        if transcript_embedding is None:
            # Check if we're already fetching it
            if transcript_lower not in self._pending_transcript_embeddings:
                # Schedule background task to fetch and cache embedding
                try:
                    loop = asyncio.get_running_loop()
                    self._pending_transcript_embeddings.add(transcript_lower)
                    task = loop.create_task(self._fetch_and_cache_transcript_embedding(transcript))
                    logger.debug(
                        f"Scheduled background task to cache embedding for transcript: '{transcript}'"
                    )
                except RuntimeError:
                    # No event loop, can't fetch async
                    logger.debug(f"No event loop available to cache embedding for '{transcript}'")
                    pass
            
            # For now, fall back to word matching
            logger.debug(
                f"Transcript '{transcript}' embedding not cached yet, "
                "using word-based matching. Embedding will be cached for future use."
            )
            return False
        
        # We have the embedding, check similarity
        max_similarity = 0.0
        best_match = None
        
        for backchanneling_text, backchanneling_embedding in self._backchanneling_embeddings.items():
            similarity = self._cosine_similarity(transcript_embedding, backchanneling_embedding)
            if similarity > max_similarity:
                max_similarity = similarity
                best_match = backchanneling_text
        
        logger.debug(
            f"Embedding similarity check: transcript='{transcript}', "
            f"best_match='{best_match}', similarity={max_similarity:.3f}, "
            f"threshold={self._embedding_similarity_threshold}"
        )
        
        return max_similarity >= self._embedding_similarity_threshold
    
    async def _fetch_and_cache_transcript_embedding(self, transcript: str) -> None:
        """Background task to fetch and cache transcript embedding."""
        transcript_lower = transcript.lower().strip()
        try:
            embedding = await self._get_transcript_embedding(transcript)
            # Embedding is now cached, can be used in future checks
            logger.info(
                f"✓ Successfully cached embedding for transcript: '{transcript}' "
                f"(will use embedding-based checking for future occurrences)"
            )
        except Exception as e:
            logger.warning(f"Failed to fetch embedding for '{transcript}': {e}")
        finally:
            self._pending_transcript_embeddings.discard(transcript_lower)

    async def _check_backchanneling_with_embeddings_async(self, transcript: str) -> bool:
        """
        Async method to check if transcript is backchanneling using embeddings.
        """
        # Initialize embeddings if not already done
        if not self._embeddings_initialized:
            await self._initialize_backchanneling_embeddings()
        
        if not self._backchanneling_embeddings:
            logger.warning("No backchanneling embeddings available, falling back to word matching")
            return False
        
        # Get embedding for transcript
        try:
            transcript_embedding = await self._get_transcript_embedding(transcript)
        except Exception as e:
            logger.warning(f"Failed to get transcript embedding: {e}. Falling back to word matching.")
            return False
        
        if not transcript_embedding:
            return False
        
        # Check similarity against all backchanneling embeddings
        max_similarity = 0.0
        best_match = None
        
        for backchanneling_text, backchanneling_embedding in self._backchanneling_embeddings.items():
            similarity = self._cosine_similarity(transcript_embedding, backchanneling_embedding)
            if similarity > max_similarity:
                max_similarity = similarity
                best_match = backchanneling_text
        
        logger.debug(
            f"Embedding similarity check: transcript='{transcript}', "
            f"best_match='{best_match}', similarity={max_similarity:.3f}, "
            f"threshold={self._embedding_similarity_threshold}"
        )
        
        # If similarity exceeds threshold, it's backchanneling
        return max_similarity >= self._embedding_similarity_threshold




