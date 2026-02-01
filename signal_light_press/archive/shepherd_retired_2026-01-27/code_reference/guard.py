#guard.py
import re

class GuardViolation(Exception):
    pass


def enforce_three_words(text: str) -> None:
    if not re.fullmatch(r"[a-z]+ [a-z]+ [a-z]+", text.strip()):
        raise GuardViolation(f"Guard failed: {text!r}")
