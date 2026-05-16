import unicodedata

_STRIP_CHARS = ".,;:()[]!?\"'«»"
_INVALID_CHARS = {",", ".", ":", ";", "!", "?", "\"", "'", ""}


def tokenize(text: str) -> list[str]:
    """Normalize and split text into raw tokens.

    Normalization: NFKC + ё→е + lowercase.
    Splits on whitespace; strips edge punctuation from each token.
    Preserves internal hyphens and slashes (composite terms handled downstream).
    """
    normalized = unicodedata.normalize("NFKC", text).replace("ё", "е").lower()
    result: list[str] = []
    for token in normalized.split():
        token = token.strip(_STRIP_CHARS)
        if token:
            result.append(token)
    return result
