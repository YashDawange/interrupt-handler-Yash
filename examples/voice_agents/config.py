# Interruption Handler Configuration
# This file defines the behavior of the intelligent interruption handler

# Passive Acknowledgment Words
# These words/phrases will be IGNORED when the agent is speaking
# The agent will continue speaking without interruption
IGNORE_WORDS = [
    'yeah',
    'ok',
    'okay',
    'hmm',
    'uh-huh',
    'right',
    'aha',
    'mhm',
    'mm-hmm',
    'sure',
    'yep',
    'yes',
    'got it',
    'i see',
    'understand',
    'alright',
    'cool',
    'nice',
]

# Active Interruption Words
# These words/phrases will ALWAYS interrupt the agent
# Even if only part of a sentence
INTERRUPT_WORDS = [
    'wait',
    'stop',
    'no',
    'hold',
    'pause',
    'hang on',
    'hold on',
    'one moment',
    'one second',
    'actually',
    'but',
    'however',
]

# Timing Configuration
# Time to wait for full transcription before making interrupt decision (in seconds)
TRANSCRIPTION_WAIT_TIME = 0.3

# Whether to log detailed interruption decisions
VERBOSE_LOGGING = True