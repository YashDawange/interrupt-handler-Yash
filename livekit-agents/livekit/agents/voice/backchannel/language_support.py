"""
Multi-Language Support for Backchannel Detection

Provides language-specific backchannel word lists and patterns.
Supports auto-detection and 8+ languages.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Language(str, Enum):
    """Supported languages."""
    
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    MANDARIN = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    HINDI = "hi"
    ARABIC = "ar"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    ITALIAN = "it"


@dataclass
class LanguageProfile:
    """
    Language-specific backchannel patterns.
    """
    
    language: Language
    name: str
    backchannel_words: list[str]
    command_words: list[str]
    
    def __post_init__(self):
        # Normalize to lowercase
        self.backchannel_words = [w.lower() for w in self.backchannel_words]
        self.command_words = [w.lower() for w in self.command_words]


# Language profiles with common backchannel and command words
LANGUAGE_PROFILES = {
    Language.ENGLISH: LanguageProfile(
        language=Language.ENGLISH,
        name="English",
        backchannel_words=[
            "yeah", "yep", "yup", "yes",
            "ok", "okay", "alright",
            "uh-huh", "mm-hmm", "mhm", "mmm",
            "right", "sure", "exactly",
            "got it", "I see", "I understand",
            "aha", "oh", "wow",
            "interesting", "cool", "nice",
        ],
        command_words=[
            "wait", "hold on", "stop", "pause",
            "no", "nope", "not really",
            "what", "why", "how", "when", "where",
            "tell me", "show me", "explain",
            "repeat", "again", "sorry",
            "listen", "actually", "but",
        ],
    ),
    
    Language.SPANISH: LanguageProfile(
        language=Language.SPANISH,
        name="Spanish",
        backchannel_words=[
            "sí", "si", "vale", "venga",
            "claro", "por supuesto",
            "ajá", "uh-huh", "mmm",
            "entiendo", "ya veo",
            "exacto", "cierto", "bien",
            "de acuerdo", "okay",
        ],
        command_words=[
            "espera", "para", "alto",
            "no", "nada",
            "qué", "por qué", "cómo", "cuándo", "dónde",
            "dime", "explica", "muéstrame",
            "repite", "otra vez",
            "escucha", "pero",
        ],
    ),
    
    Language.FRENCH: LanguageProfile(
        language=Language.FRENCH,
        name="French",
        backchannel_words=[
            "oui", "ouais", "d'accord", "ok",
            "mmh", "euh", "ah",
            "je vois", "je comprends",
            "exactement", "c'est vrai", "bien",
            "absolument", "tout à fait",
        ],
        command_words=[
            "attends", "attendez", "arrête", "arrêtez",
            "non", "pas vraiment",
            "quoi", "pourquoi", "comment", "quand", "où",
            "dis-moi", "montre-moi", "explique",
            "répète", "encore",
            "écoute", "écoutez", "mais",
        ],
    ),
    
    Language.GERMAN: LanguageProfile(
        language=Language.GERMAN,
        name="German",
        backchannel_words=[
            "ja", "jaja", "okay", "gut",
            "mmh", "aha", "oh",
            "verstehe", "ich verstehe",
            "genau", "stimmt", "richtig",
            "klar", "sicher", "absolut",
        ],
        command_words=[
            "warte", "warten Sie", "halt", "stop",
            "nein", "nicht wirklich",
            "was", "warum", "wie", "wann", "wo",
            "sag mir", "zeig mir", "erkläre",
            "wiederhole", "nochmal",
            "hör zu", "hören Sie", "aber",
        ],
    ),
    
    Language.MANDARIN: LanguageProfile(
        language=Language.MANDARIN,
        name="Mandarin Chinese",
        backchannel_words=[
            # Pinyin representations
            "hao", "dui", "shi", "en",
            "mingbai", "zhidao",
            "duì", "hǎo", "shì",
            "mm", "ah", "oh",
        ],
        command_words=[
            "deng", "ting", "bu", "mei",
            "shenme", "weishenme", "zenme",
            "gaosu wo", "jieshi",
            "zai shuo yici",
        ],
    ),
    
    Language.JAPANESE: LanguageProfile(
        language=Language.JAPANESE,
        name="Japanese",
        backchannel_words=[
            # Romaji
            "hai", "ee", "un", "sou",
            "naruhodo", "wakatta", "wakarimashita",
            "aa", "eh", "nn",
            "sou desu ne", "honto",
        ],
        command_words=[
            "matte", "chotto matte", "yamete",
            "iie", "chigau",
            "nani", "naze", "dou", "itsu", "doko",
            "oshiete", "setsum", "mou ichido",
        ],
    ),
    
    Language.KOREAN: LanguageProfile(
        language=Language.KOREAN,
        name="Korean",
        backchannel_words=[
            # Romanized
            "ne", "ye", "eung", "geurae",
            "araso", "algesseumnida",
            "mm", "ah", "oh",
            "majayo", "geureoheyo",
        ],
        command_words=[
            "jamkkanman", "jamkan", "meomchwo",
            "ani", "aniya",
            "mwo", "wae", "eotteoke", "eonje", "eodi",
            "malhaejwo", "seolmyeonghae", "dasi",
        ],
    ),
    
    Language.HINDI: LanguageProfile(
        language=Language.HINDI,
        name="Hindi",
        backchannel_words=[
            # Romanized
            "haan", "ha", "theek", "acha",
            "samajh gaya", "pata hai",
            "mm", "ah", "oh",
            "sahi", "bilkul",
        ],
        command_words=[
            "ruko", "rukiye", "mat karo",
            "nahin", "nahi",
            "kya", "kyun", "kaise", "kab", "kahan",
            "batao", "samjhao", "phir se",
        ],
    ),
    
    Language.ARABIC: LanguageProfile(
        language=Language.ARABIC,
        name="Arabic",
        backchannel_words=[
            # Romanized
            "na'am", "aywa", "eh", "tayyib",
            "fahemt", "a'rif",
            "mm", "ah", "oh",
            "sah", "maz boot",
        ],
        command_words=[
            "intazir", "qif", "la",
            "matha", "limatha", "kayfa", "mata", "ayna",
            "qul li", "sharh", "mara okhra",
        ],
    ),
    
    Language.PORTUGUESE: LanguageProfile(
        language=Language.PORTUGUESE,
        name="Portuguese",
        backchannel_words=[
            "sim", "é", "tá", "ok",
            "certo", "claro", "exato",
            "entendo", "compreendo",
            "mm", "ah", "oh",
            "legal", "beleza",
        ],
        command_words=[
            "espera", "espere", "para", "pare",
            "não", "nada",
            "o que", "por que", "como", "quando", "onde",
            "me diga", "explica", "repete",
        ],
    ),
    
    Language.RUSSIAN: LanguageProfile(
        language=Language.RUSSIAN,
        name="Russian",
        backchannel_words=[
            # Romanized
            "da", "aga", "ugu", "nu",
            "ponimayu", "yasno",
            "mm", "ah", "oh",
            "tochno", "pravilno", "horosho",
        ],
        command_words=[
            "podozh", "podozhdite", "stoy",
            "net", "ne",
            "chto", "pochemu", "kak", "kogda", "gde",
            "skazhi", "obyasni", "povtori",
        ],
    ),
    
    Language.ITALIAN: LanguageProfile(
        language=Language.ITALIAN,
        name="Italian",
        backchannel_words=[
            "sì", "si", "va bene", "ok",
            "certo", "esatto", "giusto",
            "capisco", "ho capito",
            "mm", "ah", "oh",
            "bene", "perfetto",
        ],
        command_words=[
            "aspetta", "aspetti", "ferma", "stop",
            "no", "niente",
            "cosa", "perché", "come", "quando", "dove",
            "dimmi", "spiega", "ripeti",
        ],
    ),
}


class LanguageDetector:
    """
    Detects language from transcribed text.
    
    Uses simple heuristics based on characteristic words.
    """
    
    def __init__(self):
        """Initialize language detector."""
        self._confidence_threshold = 0.3
        
        # Build detection patterns from profiles
        self._detection_patterns = {
            lang: profile.backchannel_words + profile.command_words
            for lang, profile in LANGUAGE_PROFILES.items()
        }
    
    def detect_language(
        self,
        text: str,
        *,
        stt_language: str | None = None,
    ) -> tuple[Language, float]:
        """
        Detect language from text.
        
        Args:
            text: Transcribed text
            stt_language: Language hint from STT (if available)
            
        Returns:
            Tuple of (detected_language, confidence)
        """
        # If STT provides language, trust it
        if stt_language:
            detected = self._parse_stt_language(stt_language)
            if detected:
                return (detected, 0.95)
        
        # Otherwise detect from text
        text_lower = text.lower().strip()
        
        if not text_lower:
            return (Language.ENGLISH, 0.5)  # Default
        
        # Count matches for each language
        scores = {}
        for lang, patterns in self._detection_patterns.items():
            matches = sum(1 for pattern in patterns if pattern in text_lower)
            scores[lang] = matches / len(patterns)
        
        # Get best match
        best_lang = max(scores, key=scores.get)
        confidence = scores[best_lang]
        
        # If confidence is too low, default to English
        if confidence < self._confidence_threshold:
            return (Language.ENGLISH, 0.5)
        
        return (best_lang, confidence)
    
    def _parse_stt_language(self, stt_language: str) -> Language | None:
        """Parse STT language code to Language enum."""
        # Extract language code (e.g., "en-US" -> "en")
        lang_code = stt_language.split("-")[0].lower()
        
        try:
            return Language(lang_code)
        except ValueError:
            return None


class MultiLanguageBackchannelDetector:
    """
    Multi-language aware backchannel detector.
    
    Automatically detects language and uses appropriate word lists.
    """
    
    def __init__(
        self,
        *,
        default_language: Language = Language.ENGLISH,
        auto_detect: bool = True,
    ):
        """
        Initialize multi-language detector.
        
        Args:
            default_language: Default language to use
            auto_detect: Whether to auto-detect language
        """
        self._default_language = default_language
        self._auto_detect = auto_detect
        self._detector = LanguageDetector()
        self._current_language = default_language
        
        logger.info(
            f"MultiLanguageBackchannelDetector initialized: "
            f"default={default_language}, auto_detect={auto_detect}"
        )
    
    def get_backchannel_words(
        self,
        text: str | None = None,
        stt_language: str | None = None,
    ) -> list[str]:
        """
        Get backchannel words for detected or default language.
        
        Args:
            text: Text to detect language from
            stt_language: Language hint from STT
            
        Returns:
            List of backchannel words for the language
        """
        language = self._get_language(text, stt_language)
        profile = LANGUAGE_PROFILES[language]
        return profile.backchannel_words
    
    def get_command_words(
        self,
        text: str | None = None,
        stt_language: str | None = None,
    ) -> list[str]:
        """Get command words for detected or default language."""
        language = self._get_language(text, stt_language)
        profile = LANGUAGE_PROFILES[language]
        return profile.command_words
    
    def get_all_words(
        self,
        languages: list[Language] | None = None,
    ) -> tuple[list[str], list[str]]:
        """
        Get backchannel and command words for multiple languages.
        
        Useful for multilingual conversations.
        
        Args:
            languages: List of languages to include (None = all)
            
        Returns:
            Tuple of (backchannel_words, command_words)
        """
        if languages is None:
            languages = list(LANGUAGE_PROFILES.keys())
        
        backchannels = []
        commands = []
        
        for lang in languages:
            profile = LANGUAGE_PROFILES[lang]
            backchannels.extend(profile.backchannel_words)
            commands.extend(profile.command_words)
        
        # Remove duplicates
        backchannels = list(set(backchannels))
        commands = list(set(commands))
        
        return (backchannels, commands)
    
    def _get_language(
        self,
        text: str | None,
        stt_language: str | None,
    ) -> Language:
        """Determine language to use."""
        if self._auto_detect and (text or stt_language):
            detected, confidence = self._detector.detect_language(
                text or "",
                stt_language=stt_language,
            )
            if confidence > 0.5:
                self._current_language = detected
                return detected
        
        return self._current_language
    
    def set_language(self, language: Language) -> None:
        """Manually set language."""
        self._current_language = language
        logger.info(f"Language set to: {language.value}")
    
    @property
    def current_language(self) -> Language:
        """Get current language."""
        return self._current_language
    
    @property
    def supported_languages(self) -> list[Language]:
        """Get list of supported languages."""
        return list(LANGUAGE_PROFILES.keys())

