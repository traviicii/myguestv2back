import re

# Shared service-name normalization for the backend.
# We format labels for display and also derive a lowercase key for uniqueness.

CONNECTOR_WORDS = {"and", "or", "of", "the", "a", "an", "for", "to"}


def normalize_service_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _format_token(token: str, index: int, total: int) -> str:
    trimmed = token.strip()
    if not trimmed:
        return ""

    if re.fullmatch(r"[&/+|-]+", trimmed):
        return trimmed

    lowered = trimmed.lower()
    if 0 < index < total - 1 and lowered in CONNECTOR_WORDS:
        return lowered

    return re.sub(r"(^[a-z])|([-/][a-z])", lambda part: part.group(0).upper(), lowered)


def format_service_name(value: str) -> str:
    normalized = normalize_service_whitespace(value)
    if not normalized:
        return ""

    parts = normalized.split(" ")
    return " ".join(_format_token(token, idx, len(parts)) for idx, token in enumerate(parts))


def normalize_service_key(value: str) -> str:
    return format_service_name(value).lower()
