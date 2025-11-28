"""Encoding utilities for generating compact short codes from integers.

Provides base62 encode/decode and a small wrapper to produce codes of
limited length (max 10)."""

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)


def encode_base62(num: int) -> str:
    if num == 0:
        return ALPHABET[0]
    out = []
    while num:
        num, rem = divmod(num, BASE)
        out.append(ALPHABET[rem])
    return ''.join(reversed(out))


def decode_base62(s: str) -> int:
    n = 0
    for ch in s:
        n = n * BASE + ALPHABET.index(ch)
    return n


def generate_code_from_id(id_value: int, max_len: int = 10) -> str:
    code = encode_base62(id_value)
    if len(code) <= max_len:
        return code
    # If code exceeds max_len (extremely unlikely), take the last max_len chars
    # which preserve the low-order bits of the id — still deterministic.
    return code[-max_len:]
