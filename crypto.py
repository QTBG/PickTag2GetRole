"""Chiffrement des valeurs API et index opaques pour le stockage SQLite.

La clé Fernet est fournie séparément du volume de données. Les valeurs API
sont chiffrées ; l'index de serveur est un HMAC dérivé de cette clé.
Les dates, métadonnées internes et la structure SQLite restent visibles.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

FERNET_PREFIX = 'gAAAAA'


class EncryptionKeyError(RuntimeError):
    """Clé absente, incorrecte ou données chiffrées illisibles."""


class FieldCipher:
    """Chiffrement obligatoire ; aucune clé n'est générée implicitement."""

    def __init__(self, key: Optional[str] = None):
        raw_key = (key if key is not None else os.getenv('ENCRYPTION_KEY', '')).strip()
        if not raw_key:
            raise EncryptionKeyError('ENCRYPTION_KEY is required. Restore or configure a Fernet key.')
        try:
            self._fernet = Fernet(raw_key)
            key_bytes = base64.urlsafe_b64decode(raw_key)
        except (ValueError, TypeError) as exc:
            raise EncryptionKeyError('ENCRYPTION_KEY is not a valid Fernet key.') from exc
        self._index_key = hmac.new(
            key_bytes, b'PickTag2GetRole:guild-index:v1', hashlib.sha256
        ).digest()

    @property
    def enabled(self) -> bool:
        return True

    @staticmethod
    def looks_encrypted(value) -> bool:
        return isinstance(value, str) and value.startswith(FERNET_PREFIX)

    def guild_index(self, guild_id: int) -> str:
        return hmac.new(
            self._index_key, str(int(guild_id)).encode('ascii'), hashlib.sha256
        ).hexdigest()

    def encrypt(self, value):
        if value is None:
            return None
        # Un tag ressemblant à un jeton Fernet doit aussi être chiffré.
        return self._fernet.encrypt(str(value).encode('utf-8')).decode('ascii')

    def decrypt(self, value):
        """Accepte le clair uniquement pour la migration du schéma historique."""
        if value is None or not self.looks_encrypted(value):
            return value
        try:
            return self._fernet.decrypt(value.encode('ascii')).decode('utf-8')
        except (InvalidToken, UnicodeError, ValueError) as exc:
            raise EncryptionKeyError(
                'Stored data cannot be decrypted. Restore the original ENCRYPTION_KEY.'
            ) from exc

    def encrypt_int(self, value: Optional[int]):
        return None if value is None else self.encrypt(str(int(value)))

    def decrypt_int(self, value, default: int = 0) -> int:
        """Ne pas masquer une erreur de clé en affichant un faux compteur."""
        return default if value is None else int(self.decrypt(value))
