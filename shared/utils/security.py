"""Security utilities — PII redaction, input sanitization, API key management.

Provides:
  • redact_pii()         — Strip PII from log messages
  • sanitize_input()     — Remove HTML/XSS vectors from user input
  • generate_api_key()   — Create cryptographically secure API keys
  • hash_api_key()       — SHA-256 hash for storage
  • mask_api_key()       — Show only last 8 chars for display
"""

from __future__ import annotations

import hashlib
import re
import secrets
import string


# ── PII Redaction ──

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CC_RE = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
_IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")


def redact_pii(text: str) -> str:
    """Redact personally identifiable information from text.

    Handles: email addresses, phone numbers, SSNs, credit cards, IP addresses.
    """

    # Email: user@domain.com → u***@d***.com
    def _redact_email(m: re.Match) -> str:
        email = m.group()
        local, domain = email.split("@", 1)
        return f"{local[0]}***@{domain[0]}***.{domain.rsplit('.', 1)[-1]}"

    text = _EMAIL_RE.sub(_redact_email, text)

    # Phone: +1-555-0101 → +1-***-****
    def _redact_phone(m: re.Match) -> str:
        phone = m.group()
        # Keep country code if present, redact the rest
        if phone.startswith("+"):
            parts = re.split(r"[-.\s]", phone, maxsplit=1)
            return f"{parts[0]}-***-****"
        return "***-***-****"

    text = _PHONE_RE.sub(_redact_phone, text)

    # SSN: 123-45-6789 → ***-**-****
    text = _SSN_RE.sub("***-**-****", text)

    # Credit card: 4111111111111111 → ****-****-****-1111
    def _redact_cc(m: re.Match) -> str:
        cc = re.sub(r"[-\s]", "", m.group())
        return f"****-****-****-{cc[-4:]}"

    text = _CC_RE.sub(_redact_cc, text)

    return text


# ── Input Sanitization ──

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_EVENT_HANDLER_RE = re.compile(r"\bon\w+\s*=", re.IGNORECASE)
_JAVASCRIPT_URI_RE = re.compile(r"javascript\s*:", re.IGNORECASE)


def sanitize_input(text: str) -> str:
    """Remove HTML tags, script blocks, and XSS vectors from user input."""
    text = _SCRIPT_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)
    text = _EVENT_HANDLER_RE.sub("", text)
    text = _JAVASCRIPT_URI_RE.sub("", text)
    return text.strip()


# ── API Key Management ──

_API_KEY_PREFIX = "vkai_"
_API_KEY_LENGTH = 40  # chars after prefix


def generate_api_key() -> str:
    """Generate a cryptographically secure API key.

    Format: vkai_<40 random chars>
    """
    chars = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(_API_KEY_LENGTH))
    return f"{_API_KEY_PREFIX}{random_part}"


def hash_api_key(key: str) -> str:
    """SHA-256 hash of an API key for secure storage."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def mask_api_key(key: str) -> str:
    """Mask an API key for display — show prefix + last 8 chars."""
    if len(key) <= 12:
        return "****"
    return f"{key[:5]}...{key[-8:]}"


# ── Validation Helpers ──


def is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID v4."""
    import uuid as _uuid

    try:
        _uuid.UUID(value, version=4)
        return True
    except ValueError:
        return False
