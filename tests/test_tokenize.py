from agent.basic_agent import tokenize


def test_simple_words():
    assert tokenize("yeah ok") == ["yeah", "ok"]


def test_punctuation_removed():
    assert tokenize("yeah, wait.") == ["yeah", "wait"]


def test_mixed_case():
    assert tokenize("YeAh BuT WaIt") == ["yeah", "but", "wait"]


def test_hyphenated_words():
    assert tokenize("uh-huh") == ["uh-huh"]
