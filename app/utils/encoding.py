import secrets

# Base36 alphabet (lowercase only for case-insensitive URLs)
ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
BASE = len(ALPHABET)
SHORT_CODE_LENGTH = 7


def generate_short_code() -> str:
    """Generate cryptographically secure random 7-character lowercase code."""
    return ''.join(secrets.choice(ALPHABET) for _ in range(SHORT_CODE_LENGTH))


def normalize_short_code(code: str) -> str:
    """Normalize short code to lowercase for case-insensitive lookups."""
    return code.lower().strip()


def encode_base62(num: int) -> str:
    """Encode integer to Base62 string (kept for compatibility, uses Base36 now)."""
    if num == 0:
        return ALPHABET[0]
    out = []
    while num:
        num, rem = divmod(num, BASE)
        out.append(ALPHABET[rem])
    return ''.join(reversed(out))


def decode_base62(s: str) -> int:
    """Decode Base62 string to integer (kept for compatibility, uses Base36 now)."""
    s = normalize_short_code(s)
    n = 0
    for ch in s:
        n = n * BASE + ALPHABET.index(ch)
    return n