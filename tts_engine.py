import os
try:
    import pyttsx3
    PYTTSX3 = True
except Exception:
    PYTTSX3 = False

class TTSEngine:
    def __init__(self):
        if PYTTSX3:
            self.engine = pyttsx3.init()
        else:
            self.engine = None

    def speak(self, text):
        if self.engine:
            self.engine.say(text)
            self.engine.runAndWait()
        else:
            # fallback: print text so user can read
            print("TTS (fallback):", text)
