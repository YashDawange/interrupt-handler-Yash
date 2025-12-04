import threading
import pyttsx3
import re
import time
import speech_recognition as sr

IGNORE_WORDS = ["yeah", "ok", "hmm", "right", "uh-huh", "mm", "mm-hmm", "uh", "aha"]
INTERRUPT_KEYWORDS = ["stop", "wait", "no", "hold", "hold on", "pause", "cancel", "stop that", "stop now"]

PARAGRAPH = (
    "Artificial Intelligence, or AI, is the simulation of human intelligence in machines. "
    "It enables machines to perform tasks that usually require human intelligence, "
    "such as problem-solving, understanding language, and recognizing patterns. "
    "The history of AI began in the 1950s and has rapidly evolved, influencing many industries and aspects of daily life."
)

def classify_input(text):
    text_lower = text.lower()
    for kw in INTERRUPT_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
            return "INTERRUPT"
    tokens = re.findall(r"\w+(?:[-']\w+)?", text_lower)
    if tokens and all(tok in IGNORE_WORDS for tok in tokens):
        return "IGNORE"
    return "RESPOND"

class VoiceAgent:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 165)
        self.engine.setProperty("voice", "com.apple.speech.synthesis.voice.samantha")
        self.speaking = False
        self.stop_flag = False
        self.lock = threading.Lock()
    
    def speak(self, text):
        with self.lock:
            self.speaking = True
            self.stop_flag = False
            self.engine.say(text)
            self.engine.runAndWait()
            self.speaking = False

    def listen_user(self):
        recognizer = sr.Recognizer()
        mic = sr.Microphone()
        while True:
            try:
                with mic as source:
                    print("🎤 Speak now...")
                    audio = recognizer.listen(source, timeout=1, phrase_time_limit=5)
                user_input = recognizer.recognize_google(audio)
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except sr.RequestError:
                print("STT request failed.")
                continue

            cls = classify_input(user_input)
            print(f"User said: {user_input} -> classified as {cls}")

            if user_input.lower() in ["quit", "exit"]:
                self.stop_flag = True
                break

            if self.speaking:
                if cls == "INTERRUPT":
                    print("Interrupt triggered! Stopping speech...")
                    self.engine.stop()
                    self.stop_flag = True
                else:
                    print("Ignored filler word while speaking.")
            else:
                if cls != "IGNORE":
                    self.speak(f"You said: {user_input}")

    def read_paragraph(self):
        self.speak(PARAGRAPH)
        print("Finished reading paragraph.")

def main():
    agent = VoiceAgent()
    agent.speak("Hello, I am your assistant. I will read a paragraph now. You can interrupt me with 'wait' or 'stop'.")

    # Start listening in background
    listener_thread = threading.Thread(target=agent.listen_user, daemon=True)
    listener_thread.start()

    # Read paragraph
    agent.read_paragraph()

    listener_thread.join()
    agent.speak("Goodbye!")

if __name__ == "__main__":
    main()
