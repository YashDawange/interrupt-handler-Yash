import re

NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    return NORMALIZE_RE.sub(" ", text.lower()).strip()


def normalize_list(words: list[str]) -> set[str]:
    return {normalize(w) for w in words if w.strip()}


# Backchannels (ignore while agent speaks)
IGNORE_WORDS = [
    "hm", "hmm", "mhm", "mhmm",
    "mm-hmm", "mmhmm",
    "ok", "okay", "okayy",
    "yeah", "yeahh", "yep", "yes", "yup",
    "right", "sure", "got it", "i see"
]

# Explicit interrupt commands
INTERRUPT_WORDS = [
    "stop",
    "wait",
    "no",
    "pause",
    "hold",
    "hold on",
    "hang on",
    "one moment",
    "actually",
    "never mind",
]

START_WORDS = [
    "start",
    "continue",
    "go ahead",
    "go on",
]


START_SET = normalize_list(START_WORDS)

IGNORE_SET = normalize_list(IGNORE_WORDS)
INTERRUPT_SET = normalize_list(INTERRUPT_WORDS)
