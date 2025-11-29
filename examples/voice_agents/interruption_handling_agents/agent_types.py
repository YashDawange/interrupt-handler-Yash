from __future__ import annotations
from enum import Enum


class UserInputType(Enum):
    BACKCHANNEL = "backchannel"     # small acknowledgements like "yeah", "ok"
    COMMAND = "command"             # user giving an instruction (stop, pause)
    QUERY = "query"                 # meaningful question or informational ask
    UNCLASSIFIED = "unclassified"   # cannot determine the input type
