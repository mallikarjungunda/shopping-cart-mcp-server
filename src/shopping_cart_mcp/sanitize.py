"""Treat everything that comes back from the store as untrusted text.

Product names and descriptions are written by third parties. They could contain
markup, hidden Unicode, or text that tries to instruct the model. We strip what
we can and bound the length; the server instructions also tell the model that
tool output is data, never instructions.
"""
import re
import unicodedata

_TAG = re.compile(r"<[^>]*>")
_HIDDEN = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")


def clean_text(value: object, max_len: int = 200) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text)
    text = _TAG.sub(" ", text)
    text = _HIDDEN.sub("", text)
    text = "".join(ch for ch in text if ch == " " or unicodedata.category(ch)[0] != "C")
    text = " ".join(text.split())
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"
