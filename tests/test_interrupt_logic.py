from livekit.agents.voice.semantic_interruptions import CommandDetector, SoftWordFilter


SOFT = ["yeah", "ok", "uh huh", "mm hmm"]
STOPS = ["stop", "wait", "hold on"]
CORRECTIONS = ["actually", "no that's wrong"]


def build_detector() -> CommandDetector:
    return CommandDetector(
        stop_commands=STOPS,
        correction_cues=CORRECTIONS,
        soft_filter=SoftWordFilter(SOFT),
    )


def test_soft_phrase_is_detected():
    detector = build_detector()
    label, cleaned = detector.classify("Yeah uh huh ok")
    assert label == "soft"
    assert cleaned == ""


def test_stop_command_overrides_soft_prefix():
    detector = build_detector()
    label, cleaned = detector.classify("yeah wait a second")
    assert label == "stop"
    # cleaned text should strip filler and keep command content
    assert "wait" in cleaned
    assert "yeah" not in cleaned


def test_correction_phrase_detected():
    detector = build_detector()
    label, cleaned = detector.classify("uh actually it's Paris")
    assert label == "correction"
    assert cleaned.startswith("actually")


def test_content_is_not_misclassified():
    detector = build_detector()
    label, cleaned = detector.classify("please tell me more about solar power")
    assert label == "content"
    assert "solar power" in cleaned

