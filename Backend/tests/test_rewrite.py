import chat


def _hist(*pairs):
    out = []
    for role, content in pairs:
        out.append({"role": role, "content": content})
    return out


def test_followup_with_question_mark_is_rewritten():
    history = _hist(("user", "What is Amenify?"), ("assistant", "A resident services platform."))
    out = chat._rewrite_query("who founded it?", history)
    assert out == "who founded it? What is Amenify?"


def test_followup_with_trailing_period_is_rewritten():
    history = _hist(("user", "Tell me about the Resident Protection Plan"),
                    ("assistant", "It covers accidental damage."))
    out = chat._rewrite_query("what does it cover.", history)
    assert out.endswith("Tell me about the Resident Protection Plan")


def test_no_followup_word_returns_message_unchanged():
    history = _hist(("user", "What is Amenify?"), ("assistant", "A platform."))
    assert chat._rewrite_query("What are the cleaning prices", history) == "What are the cleaning prices"


def test_followup_with_no_history_returns_message_unchanged():
    assert chat._rewrite_query("who founded it?", []) == "who founded it?"


def test_contraction_followup_is_detected():
    history = _hist(("user", "Who is the CEO?"), ("assistant", "Everett Lynn."))
    out = chat._rewrite_query("what's their background?", history)
    assert out == "what's their background? Who is the CEO?"
