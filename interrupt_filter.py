class InterruptionFilter:
    def __init__(self, ignore_list=None, interrupt_list=None):
        self.ignore_list = set(ignore_list or [
            "yeah","yea","ok","okay","hmm","uh-huh","right","mhm","mm"
        ])
        self.interrupt_list = set(interrupt_list or [
            "stop","wait","no","hold on","pause","stop that"
        ])

    def contains_interrupt(self, text):
        t = text.lower()
        for w in self.interrupt_list:
            if w in t:
                return True
        return False

    def is_only_soft(self, text):
       
        t = text.lower().strip()
        if t in self.ignore_list:
            return True
        
        words = [w.strip(".,!?") for w in t.split()]
        if len(words) == 0:
            return False
        for w in words:
            if w == "" or w in self.ignore_list:
                continue
            
            return False
        return True

    def process_transcript(self, text: str, agent_state: str):
        """
        agent_state: "speaking" or "silent"
        Returns one of: "ignore", "interrupt", "respond"
        """
        if not text or text.strip()=="":
            return "ignore" if agent_state=="speaking" else "respond"

   
        if self.contains_interrupt(text):
            return "interrupt"

        
        if self.is_only_soft(text):
            return "ignore" if agent_state=="speaking" else "respond"

    
        if agent_state == "speaking":
            return "interrupt"
        else:
            return "respond"
