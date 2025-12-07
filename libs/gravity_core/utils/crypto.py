"""
Cryptographic Utilities - Secure Secret Storage

Provides symmetric encryption for storing repository secrets
(API keys, credentials, etc.) safely in the database.

Uses Fernet (AES-128-CBC with HMAC) for authenticated encryption.
The master encryption key is loaded from environment variable.
"""

from __future__ import annotations

import base64
import os
from typing import Optional

import structlog
from cryptography.fernet import Fernet, InvalidToken

logger = structlog.get_logger(__name__)


class CryptoError(Exception):
    """Base exception for cryptographic operations."""
    pass


class KeyNotConfiguredError(CryptoError):
    """Raised when the encryption key is not configured."""
    pass


class DecryptionError(CryptoError):
    """Raised when decryption fails (invalid key or corrupted data)."""
    pass


# =============================================================================
# Key Management
# =============================================================================


def _get_master_key() -> bytes:
    """
    Load the master encryption key from environment.

    The key must be a valid Fernet key (32 bytes, base64-encoded).

    Raises:
        KeyNotConfiguredError: If ANTIGRAVITY_ENCRYPTION_KEY is not set
    """
    key = os.environ.get("ANTIGRAVITY_ENCRYPTION_KEY")

    if not key:
        raise KeyNotConfiguredError(
            "ANTIGRAVITY_ENCRYPTION_KEY environment variable is not set. "
            "Generate a key with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )

    return key.encode()


def _get_fernet() -> Fernet:
    """Get a Fernet cipher instance configured with the master key."""
    return Fernet(_get_master_key())


def generate_key() -> str:
    """
    Generate a new Fernet encryption key.

    Returns:
        A base64-encoded 32-byte key suitable for ANTIGRAVITY_ENCRYPTION_KEY
    """
    return Fernet.generate_key().decode()


# =============================================================================
# Encryption Functions
# =============================================================================


def encrypt_secret(plaintext: str) -> str:
    """
    Encrypt a secret value for storage.

    Args:
        plaintext: The secret value to encrypt (e.g., API key)

    Returns:
        Base64-encoded encrypted ciphertext

    Raises:
        KeyNotConfiguredError: If encryption key is not configured
        CryptoError: If encryption fails

    Example:
        >>> encrypted = encrypt_secret("sk-abc123...")
        >>> # Store `encrypted` safely in database
    """
    if not plaintext:
        raise CryptoError("Cannot encrypt empty secret")

    try:
        fernet = _get_fernet()
        encrypted = fernet.encrypt(plaintext.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error("encryption_failed", error_type=type(e).__name__)
        raise CryptoError(f"Encryption failed: {str(e)}") from e


def decrypt_secret(ciphertext: str) -> str:
    """
    Decrypt a secret value from storage.

    Args:
        ciphertext: The encrypted value from the database

    Returns:
        The original plaintext secret

    Raises:
        KeyNotConfiguredError: If encryption key is not configured
        DecryptionError: If decryption fails (wrong key or corrupted data)

    Example:
        >>> plaintext = decrypt_secret(encrypted_value_from_db)
        >>> # Use `plaintext` to make authenticated API calls
    """
    if not ciphertext:
        raise DecryptionError("Cannot decrypt empty ciphertext")

    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(ciphertext.encode())
        return decrypted.decode()
    except InvalidToken:
        logger.error("decryption_failed", reason="invalid_token")
        raise DecryptionError(
            "Decryption failed: Invalid token. "
            "This may mean the encryption key has changed or the data is corrupted."
        )
    except Exception as e:
        logger.error("decryption_failed", error_type=type(e).__name__)
        raise DecryptionError(f"Decryption failed: {str(e)}") from e


# =============================================================================
# Utility Functions
# =============================================================================


def is_encrypted(value: str) -> bool:
    """
    Check if a value appears to be Fernet-encrypted.

    Args:
        value: The string to check

    Returns:
        True if the value looks like Fernet ciphertext
    """
    if not value:
        return False

    # Fernet tokens start with "gAAAAA" (base64-encoded version byte)
    return value.startswith("gAAAAA") or value.startswith("gAAAAAB")


def rotate_secret(old_ciphertext: str, new_key: Optional[str] = None) -> str:
    """
    Re-encrypt a secret with a new key.

    Useful for key rotation - decrypt with current key,
    then encrypt with new key.

    Args:
        old_ciphertext: The secret encrypted with the current key
        new_key: The new Fernet key (uses current key if not provided)

    Returns:
        The secret encrypted with the new key
    """
    # Decrypt with current key
    plaintext = decrypt_secret(old_ciphertext)

    if new_key:
        # Encrypt with provided key
        fernet = Fernet(new_key.encode())
        return fernet.encrypt(plaintext.encode()).decode()
    else:
        # Re-encrypt with current key (generates new IV)
        return encrypt_secret(plaintext)
