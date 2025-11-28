from livekit.agents.voice.interruption_handler import classify_user_transcript

phrases = [
    "yeah",
    "stop",
    "yeah wait",
    "ok hmm",
    "no please"
]

for phrase in phrases:
    result = classify_user_transcript(phrase)
    print(f"Phrase: '{phrase}' => {result}")
