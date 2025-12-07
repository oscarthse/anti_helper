"""
Unit Tests for Cryptographic Utilities

Tests encrypt_secret/decrypt_secret round-trip integrity.
"""

import os

# Add project paths
# Add project paths
from unittest.mock import patch

import pytest


class TestCryptoRoundTrip:
    """Tests for encryption/decryption round-trip integrity."""

    @pytest.fixture(autouse=True)
    def setup_test_key(self):
        """Set up a test encryption key for all tests."""
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key().decode()

        with patch.dict(os.environ, {"ANTIGRAVITY_ENCRYPTION_KEY": test_key}):
            yield

    def test_encrypt_decrypt_round_trip(self):
        """Test that encrypt followed by decrypt returns original value."""
        from gravity_core.utils.crypto import decrypt_secret, encrypt_secret

        original = "sk-abc123-secret-api-key"

        encrypted = encrypt_secret(original)
        decrypted = decrypt_secret(encrypted)

        assert decrypted == original
        assert encrypted != original  # Should be encrypted

    def test_encrypt_produces_different_ciphertext_each_time(self):
        """Test that encryption uses random IV (different output each time)."""
        from gravity_core.utils.crypto import encrypt_secret

        original = "same-secret"

        encrypted1 = encrypt_secret(original)
        encrypted2 = encrypt_secret(original)

        # Same plaintext should produce different ciphertext (due to random IV)
        assert encrypted1 != encrypted2

    def test_decrypt_fails_with_wrong_key(self):
        """Test that decryption fails with incorrect key."""
        from cryptography.fernet import Fernet
        from gravity_core.utils.crypto import DecryptionError, encrypt_secret

        original = "secret-value"
        encrypted = encrypt_secret(original)

        # Now try to decrypt with a different key
        new_key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"ANTIGRAVITY_ENCRYPTION_KEY": new_key}):
            from gravity_core.utils.crypto import decrypt_secret
            with pytest.raises(DecryptionError):
                decrypt_secret(encrypted)

    def test_encrypt_empty_string_raises_error(self):
        """Test that encrypting empty string raises error."""
        from gravity_core.utils.crypto import CryptoError, encrypt_secret

        with pytest.raises(CryptoError):
            encrypt_secret("")

    def test_decrypt_empty_string_raises_error(self):
        """Test that decrypting empty string raises error."""
        from gravity_core.utils.crypto import DecryptionError, decrypt_secret

        with pytest.raises(DecryptionError):
            decrypt_secret("")

    def test_is_encrypted_detection(self):
        """Test that is_encrypted correctly identifies encrypted values."""
        from gravity_core.utils.crypto import encrypt_secret, is_encrypted

        plaintext = "not-encrypted"
        encrypted = encrypt_secret(plaintext)

        assert is_encrypted(encrypted) is True
        assert is_encrypted(plaintext) is False
        assert is_encrypted("") is False


class TestKeyNotConfigured:
    """Tests for missing encryption key handling."""

    def test_encrypt_without_key_raises_error(self):
        """Test that encryption fails when key is not configured."""
        from gravity_core.utils.crypto import CryptoError, encrypt_secret

        # Remove the key entirely
        original_key = os.environ.pop("ANTIGRAVITY_ENCRYPTION_KEY", None)
        try:
            with pytest.raises(CryptoError):  # CryptoError is parent of KeyNotConfiguredError
                encrypt_secret("test")
        finally:
            # Restore if it was set
            if original_key:
                os.environ["ANTIGRAVITY_ENCRYPTION_KEY"] = original_key

    def test_decrypt_without_key_raises_error(self):
        """Test that decryption fails when key is not configured."""
        from gravity_core.utils.crypto import CryptoError, decrypt_secret

        original_key = os.environ.pop("ANTIGRAVITY_ENCRYPTION_KEY", None)
        try:
            with pytest.raises(CryptoError):  # CryptoError is parent
                decrypt_secret("gAAAAA...")
        finally:
            if original_key:
                os.environ["ANTIGRAVITY_ENCRYPTION_KEY"] = original_key


class TestGenerateKey:
    """Tests for key generation."""

    def test_generate_key_produces_valid_fernet_key(self):
        """Test that generate_key produces a valid Fernet key."""
        from cryptography.fernet import Fernet
        from gravity_core.utils.crypto import generate_key

        key = generate_key()

        # Should not raise - valid key
        fernet = Fernet(key.encode())

        # Test round-trip
        test_data = b"test data"
        encrypted = fernet.encrypt(test_data)
        decrypted = fernet.decrypt(encrypted)

        assert decrypted == test_data
