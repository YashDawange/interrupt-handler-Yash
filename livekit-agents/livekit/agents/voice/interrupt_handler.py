from __future__ import annotations
import re

IGNORE_WORDS = {"yeah", "ok", "okay", "hmm", "right", "uh-huh", "mm-hmm"}
HARD_COMMANDS = {"stop", "wait", "hold on", "no"}

class InterruptHandler:
    def __init__(self):
        # Pre-compile regex for better performance if needed, 
        # but simple string matching might suffice for this assignment.
        pass

    def should_interrupt(self, transcript: str) -> bool:
        """
        Decides if the agent should be interrupted based on the transcript.
        Returns True if interruption is required, False otherwise.
        """
        cleaned_transcript = self._clean_transcript(transcript)
        
        if not cleaned_transcript:
            return False

        if self.is_hard_command(cleaned_transcript):
            return True
            
        if self.is_ignore_word(cleaned_transcript):
            return False
            
        # Default behavior: if it's not an ignore word and not a hard command,
        # we treat it as a normal interruption (valid input).
        return True

    def is_hard_command(self, transcript: str) -> bool:
        """
        Checks if the transcript contains any hard commands.
        """
        cleaned_transcript = self._clean_transcript(transcript)
        # Check if any hard command is present in the transcript
        # We check for substring existence for phrases like "hold on"
        for cmd in HARD_COMMANDS:
            # simple containment check might be too aggressive (e.g. "not" contains "no")
            # so we tokenize or use word boundaries.
            # For "stop", "wait", "no" -> word boundary check is safer.
            # For "hold on" -> phrase check.
            
            # Using regex for word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(cmd) + r'\b'
            if re.search(pattern, cleaned_transcript):
                return True
        return False

    def is_ignore_word(self, transcript: str) -> bool:
        """
        Checks if the transcript consists ONLY of ignore words.
        """
        cleaned_transcript = self._clean_transcript(transcript)
        words = cleaned_transcript.split()
        if not words:
            return False
            
        for word in words:
            if word not in IGNORE_WORDS:
                return False
        return True

    def _clean_transcript(self, transcript: str) -> str:
        return transcript.lower().strip().replace(".", "").replace(",", "").replace("!", "").replace("?", "")
