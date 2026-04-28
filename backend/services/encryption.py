"""
Application-level field encryption for sensitive user content.

Supabase PostgreSQL and Cloudflare R2 both provide AES-256 disk encryption,
which guards against physical hardware access. That is necessary but not
sufficient: a compromised DB credential, SQL injection, or Supabase insider
would still expose raw journal text. Application-level encryption (ALE)
separates the encryption key from the data store so that DB access alone is
never enough.

Algorithm  — Fernet (AES-128-CBC + HMAC-SHA256). Each encrypt() call
             generates a fresh random IV, so the same plaintext never
             produces the same ciphertext. Output is URL-safe base64,
             safe to store directly in a PostgreSQL Text column.

Key        — FIELD_ENCRYPTION_KEY env var. Generate once with:
               python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
             Treat it like a root secret: rotate via key migration, not by
             simply swapping the env var (existing ciphertexts would break).

Coverage   — JournalEntry.raw_text, Nudge.content, Nudge.trigger_reason.
             MoodScore floats are aggregate stats (no text), and audio files in
             R2 use R2's native AES-256 (the client uploads directly via
             presigned URL so we never touch the bytes).
"""

import os
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Written before every ciphertext so we can tell encrypted values from legacy
# plaintext rows without a separate migration step.
_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    key = os.environ.get("FIELD_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY is not set. "
            "Generate a key with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    """Return a prefixed Fernet ciphertext string for the given UTF-8 plaintext."""
    token = _fernet().encrypt(plaintext.encode("utf-8"))
    return _PREFIX + token.decode("ascii")


def decrypt(value: str) -> str:
    """Decrypt a value produced by encrypt().

    If the value lacks the encrypted prefix it is returned as-is — this covers
    existing plaintext rows written before ALE was introduced so a hard cut-over
    is not required.
    """
    if not value or not value.startswith(_PREFIX):
        return value  # legacy plaintext — return unchanged
    token = value[len(_PREFIX):].encode("ascii")
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken:
        logger.error("Fernet decryption failed — key mismatch or corrupted ciphertext")
        raise ValueError("Failed to decrypt stored field value")
