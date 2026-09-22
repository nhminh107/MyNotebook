from BackEnd.app.text_sanitizer import sanitize_text


def test_sanitize_text_removes_null_characters() -> None:
    assert sanitize_text("before\x00middle\x00after") == "beforemiddleafter"


def test_sanitize_text_preserves_regular_unicode() -> None:
    assert sanitize_text("Tiếng Việt — 日本語 🚀") == "Tiếng Việt — 日本語 🚀"
