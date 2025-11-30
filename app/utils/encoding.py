import secrets

# Base36 alphabet (lowercase only for case-insensitive URLs)
ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
BASE = len(ALPHABET)
SHORT_CODE_LENGTH = 7


def generate_short_code() -> str:
    return ''.join(secrets.choice(ALPHABET) for _ in range(SHORT_CODE_LENGTH))


def normalize_short_code(code: str) -> str:
    return code.lower().strip()
