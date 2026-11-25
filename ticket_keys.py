"""Extract issue-tracker keys such as AI-51, HS-12 or OPS2-40 from free text."""

import re

_TICKET_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b")

# Technical tokens (UTF-8, SHA-256, GPT-4) that share the KEY-123 shape
_NON_TICKET_PREFIXES = frozenset(
    {
        "AES",
        "CVE",
        "CWE",
        "ECMA",
        "GPT",
        "HTTP",
        "ISO",
        "MD",
        "PEP",
        "RFC",
        "RSA",
        "SHA",
        "SSL",
        "TLS",
        "UTF",
    }
)


def extract_ticket_key(text: object) -> str:
    """Return the first PROJECT-123 style ticket key in ``text``.

    Any project prefix of 2-10 uppercase letters or digits (starting with a
    letter) is accepted, so AI-51, HS-12 and OPS2-40 all match. Technical
    tokens such as UTF-8 or SHA-256 are skipped.

    Args:
        text: Free text, usually a Task delegation description

    Returns:
        The ticket key, or "unknown" when the text contains none
    """
    if not isinstance(text, str):
        return "unknown"
    for match in _TICKET_KEY_RE.finditer(text):
        key = match.group(1)
        if key.split("-", 1)[0] not in _NON_TICKET_PREFIXES:
            return key
    return "unknown"
