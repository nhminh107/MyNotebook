def sanitize_text(value: str) -> str:
    """Remove characters that PostgreSQL cannot store in text values."""
    return value.replace("\x00", "")
