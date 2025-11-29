from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


def _normalize_text(text: str) -> str:
    normalized = re.sub(r"[^0-9a-zA-Z\s]", " ", text.lower())
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


class InterruptionDecision(str, Enum):
    """Possible actions for a user utterance."""

    PENDING = "pending"
    IGNORE = "ignore"
    INTERRUPT = "interrupt"
    RESPOND_LISTENING = "respond_listening"


@dataclass(slots=True)
class InterruptionFilterConfig:
    ignore_phrases: tuple[str, ...] = (
        "yeah",
        "yep",
        "yup",
        "ok",
        "okay",
        "hmm",
        "mhmm",
        "mm-hmm",
        "mm hmm",
        "mmhmm",
        "uh-huh",
        "uh huh",
        "uhuh",
        "right",
        "sure",
        "got it",
        "gotcha",
        "alright",
        "nice",
        "i see",
        "makes sense",
    )
    command_phrases: tuple[str, ...] = (
        "stop",
        "wait",
        "hold on",
        "hang on",
        "pause",
        "no",
    )
    semantic_model: str | None = None
    semantic_threshold: float = 0.75
    false_start_delay: float = 0.15


@dataclass(slots=True)
class _InterruptionCandidate:
    transcript: str = ""
    started_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)
    decision: InterruptionDecision = InterruptionDecision.PENDING


class BackchannelClassifier:
    def __init__(
        self,
        *,
        config: InterruptionFilterConfig,
        logger: logging.Logger,
    ) -> None:
        self._logger = logger
        self._ignore_phrases = tuple(_normalize_text(p) for p in config.ignore_phrases)
        self._command_phrases = tuple(_normalize_text(p) for p in config.command_phrases)
        self._semantic_model_name = config.semantic_model
        self._semantic_threshold = config.semantic_threshold
        self._model = None
        self._ignore_vectors = None
        self._command_vectors = None

        if self._semantic_model_name:
            self._load_semantic_model()

    def _load_semantic_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:  # pragma: no cover - optional dependency
            self._logger.warning(
                "Failed to import sentence-transformers for interruption semantics: %s", exc
            )
            return

        try:
            self._model = SentenceTransformer(self._semantic_model_name, device="cpu")
            base_ignore = [p for p in self._ignore_phrases if p]
            base_command = [p for p in self._command_phrases if p]
            if base_ignore:
                self._ignore_vectors = self._model.encode(
                    base_ignore, normalize_embeddings=True
                )
            if base_command:
                self._command_vectors = self._model.encode(
                    base_command, normalize_embeddings=True
                )
        except Exception as exc:  # pragma: no cover - optional dependency
            self._logger.warning(
                "Unable to load semantic model '%s': %s", self._semantic_model_name, exc
            )
            self._model = None

    def _semantic_similarity(self, text: str, reference_vectors) -> float | None:
        if not self._model or reference_vectors is None:
            return None

        import numpy as np  # type: ignore  # numpy is an existing dependency

        embedding = self._model.encode([text], normalize_embeddings=True)
        if embedding.size == 0:
            return None

        similarities = np.dot(reference_vectors, embedding[0])
        return float(similarities.max())

    def contains_command(self, normalized_text: str) -> bool:
        return any(phrase and phrase in normalized_text for phrase in self._command_phrases)

    def _only_contains_ignore_tokens(self, normalized_text: str) -> bool:
        if not normalized_text:
            return False

        tokens = normalized_text.split()
        ignore_tokens = {tok for phrase in self._ignore_phrases for tok in phrase.split()}
        return all(token in ignore_tokens for token in tokens)

    def classify(self, raw_text: str) -> InterruptionDecision:
        normalized_text = _normalize_text(raw_text)

        if not normalized_text:
            return InterruptionDecision.PENDING

        if self.contains_command(normalized_text):
            return InterruptionDecision.INTERRUPT

        if self._only_contains_ignore_tokens(normalized_text):
            return InterruptionDecision.IGNORE

        semantic_decision = self._semantic_decision(normalized_text)
        if semantic_decision is not None:
            return semantic_decision

        if self._looks_like_backchannel(normalized_text):
            return InterruptionDecision.IGNORE

        # default fallback is to interrupt because the utterance carries meaning
        return InterruptionDecision.INTERRUPT

    def _looks_like_backchannel(self, normalized_text: str) -> bool:
        if not normalized_text:
            return False

        tokens = normalized_text.split()
        # heurestics to check if backchannel
        if len(tokens) <= 2 and len(normalized_text) <= 5:
            if not self.contains_command(normalized_text):
                return True
        # do fuzzy matching
        for ignore_phrase in self._ignore_phrases:
            if ignore_phrase and len(ignore_phrase) >= 3:
                if ignore_phrase in normalized_text or normalized_text in ignore_phrase:
                    return True
                
                phrase_no_space = ignore_phrase.replace(" ", "")
                text_no_space = normalized_text.replace(" ", "")
                if phrase_no_space and (phrase_no_space in text_no_space or text_no_space in phrase_no_space):
                    if len(text_no_space) >= 3:
                        return True

        return False

    def _semantic_decision(self, normalized_text: str) -> InterruptionDecision | None:
        if not self._model:
            return None

        ignore_score = self._semantic_similarity(normalized_text, self._ignore_vectors)
        if ignore_score is not None and ignore_score >= self._semantic_threshold:
            return InterruptionDecision.IGNORE

        command_score = self._semantic_similarity(normalized_text, self._command_vectors)
        if command_score is not None and command_score >= self._semantic_threshold:
            return InterruptionDecision.INTERRUPT

        return None


class InterruptionArbiter:
    def __init__(
        self,
        *,
        config: InterruptionFilterConfig | None = None,
        logger: logging.Logger | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config or InterruptionFilterConfig()
        self._logger = logger or logging.getLogger(__name__)
        self._clock = clock
        self._classifier = BackchannelClassifier(config=self._config, logger=self._logger)
        self._agent_speaking = False
        self._audio_playing = False 
        self._candidate: _InterruptionCandidate | None = None
        self._last_final: _InterruptionCandidate | None = None
        self._vad_interrupt_pending = False  # VAD flag

    @property
    def supports_semantics(self) -> bool:
        return True

    @property
    def is_agent_active(self) -> bool:
        return self._agent_speaking or self._audio_playing

    def update_agent_state(self, *, speaking: bool) -> None:
        if not speaking and not self._audio_playing:
            self._candidate = None
            self._vad_interrupt_pending = False
        self._agent_speaking = speaking

    def update_audio_playing(self, *, playing: bool) -> None:
        if not playing and not self._agent_speaking:
            self._candidate = None
            self._vad_interrupt_pending = False
        self._audio_playing = playing

    def should_gate_vad_interrupt(self) -> bool:
        return self.is_agent_active and self._vad_interrupt_pending

    def update_config(self, config: InterruptionFilterConfig) -> None:
        self._config = config
        self._classifier = BackchannelClassifier(config=config, logger=self._logger)

    def on_user_speech_detected(self) -> bool:
        if not self.is_agent_active:
            return False 
        
        if self._candidate is None:
            now = self._clock()
            self._candidate = _InterruptionCandidate(started_at=now, updated_at=now)
        
        # wait for STT to classify
        self._vad_interrupt_pending = True
        return True

    def handle_transcript(
        self,
        transcript: str,
        *,
        is_final: bool,
        user_still_speaking: bool | None,
    ) -> InterruptionDecision:
        decision = self._classify_transcript(transcript)

        if decision == InterruptionDecision.INTERRUPT:
            if not self._should_allow_interrupt():
                decision = InterruptionDecision.PENDING
        
        self._vad_interrupt_pending = False
        
        if is_final:
            self._last_final = _InterruptionCandidate(
                transcript=_normalize_text(transcript),
                decision=decision,
                updated_at=self._clock(),
            )
            if decision != InterruptionDecision.INTERRUPT:
                self._candidate = None
        else:
            if self._candidate:
                self._candidate.decision = decision
                self._candidate.transcript = _normalize_text(transcript)
                self._candidate.updated_at = self._clock()

        self._logger.debug(
            "Interruption classifier decision",
            extra={
                "decision": decision.value,
                "transcript": transcript,
                "agent_speaking": self._agent_speaking,
                "audio_playing": self._audio_playing,
                "is_agent_active": self.is_agent_active,
                "user_still_speaking": user_still_speaking,
            },
        )

        if decision == InterruptionDecision.INTERRUPT:
            self._candidate = None

        return decision

    def _classify_transcript(self, transcript: str) -> InterruptionDecision:
        if not transcript.strip():
            return InterruptionDecision.PENDING

        # Check if agent is active (speaking state OR audio still playing)
        if not self.is_agent_active:
            return InterruptionDecision.RESPOND_LISTENING

        self.on_user_speech_detected()

        if not self._candidate:
            return InterruptionDecision.PENDING

        decision = self._classifier.classify(transcript)
        self._candidate.transcript = _normalize_text(transcript)
        self._candidate.decision = decision
        self._candidate.updated_at = self._clock()
        return decision

    def _should_allow_interrupt(self) -> bool:
        if self._candidate is None:
            return True

        elapsed = self._clock() - self._candidate.started_at
        if elapsed >= self._config.false_start_delay:
            return True

        if self._candidate.decision == InterruptionDecision.INTERRUPT:
            return self._classifier.contains_command(self._candidate.transcript)

        return False

    def should_commit_turn(self, transcript: str) -> bool:
        if not transcript.strip():
            return False

        normalized = _normalize_text(transcript)
        if (
            self._last_final
            and self._last_final.decision == InterruptionDecision.IGNORE
            and normalized == self._last_final.transcript
        ):
            self._logger.debug(
                "Skipping turn commit because transcript was marked as passive acknowledgement",
                extra={"transcript": transcript},
            )
            self._last_final = None
            return False

        self._last_final = None
        return True

