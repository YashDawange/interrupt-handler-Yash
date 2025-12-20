# edge cases : "ok!!!", "...!yeah...","ok#" etc.

INTERRUPT_IGNORE_WORDS = [
    # Short Fillers & Continuers
    "ah", "aha", "hm", "hmm", "mhm", "mhmm",
    "mm-hmm", "mmhmm", "uh-huh", "um", "uh", "uhhuh",

    # Affirmations & Agreement
    "absolutely", "exactly", "indeed", "right", "sure",
    "true", "understood", "correct", "definitely",

    # Casual Acknowledgments
    "alright", "cool", "fine", "nice", "ok", "okay",
    "yeah", "yep", "yes", "yup", "sounds good",

    # Phrases & Feedback
    "go on", "got it", "i see", "makes sense",
    "keep going", "tell me more",

    # Reactions
    "really", "wow", "for real", "seriously",
    "interesting", "no way",
]
