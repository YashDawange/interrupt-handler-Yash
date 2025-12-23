import os

SOFT_TOKENS = os.getenv("SOFT_TOKENS", "yeah,ok,hmm,uh-huh,right,mm-hmm,aha")
HARD_TOKENS = os.getenv("HARD_TOKENS", "stop,wait,no,hold,pause,hey")
MAX_SOFT_LENGTH = int(os.getenv("MAX_SOFT_LENGTH", "3"))
