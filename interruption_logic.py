
""" the Logic I Applied :
1.validate all words and each input word is valid when the agent is silent.
2.when the agent is speaking, only interrupt commands are valid.that are stored in the  interrupt words set  
3 when agent is speaking, condition we check if the user input is in the interrupt words set to decide whether to interrupt or not.
"""
class InterruptionLogic:

    BACKCHANNEL_WORDS = {
        "yeah", "yea", "ok", "okay",
        "uh", "uhh", "hmm", "mhmm","ok got it","great","good","good idea","sounds good","cool"
    }

    INTERRUPT_WORDS = {
        "stop", "wait", "hold on", "pause","fine stop","stop it","cut it out","enough","stoop"
    }

    @classmethod
    def normalization(cls, text: str) -> str: # this is my code to clean the input text using string functions and make th the text to lp
        return text.strip().lower()
    

    @classmethod
    def is_backchannel(cls, text: str) -> bool:
        return cls.normalization(text) in cls.BACKCHANNEL_WORDS

    @classmethod
    def is_interrupt(cls, text: str) -> bool:
        return cls.normalization(text) in cls.INTERRUPT_WORDS
    @classmethod
    def is_interruption_required(cls, transcript: str, agent_speaking: bool) -> bool:# this is the main code that finds if the  interruption required or not
        
        if not agent_speaking:
            return False
        
        
        return cls.is_interrupt(transcript)


        return cls.is_interrupt(transcript)