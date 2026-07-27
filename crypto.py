"""Chiffrement au repos des valeurs stockées en base.

Chiffrement applicatif : les identifiants qui servent de clés (guild_id, date)
restent en clair pour rester indexables, toutes les valeurs sont chiffrées avec
Fernet (AES-128-CBC + HMAC-SHA256, clé dans ENCRYPTION_KEY).

Conséquences :
- une copie du fichier de base, ou d'une sauvegarde, est inexploitable sans la clé,
  qui n'est jamais écrite sur le disque de données ;
- sans ENCRYPTION_KEY le bot fonctionne en clair, pour ne pas casser les
  installations auto-hébergées existantes ;
- la migration est transparente : les valeurs en clair déjà présentes sont chiffrées
  au démarrage, et les valeurs chiffrées sont reconnues à leur préfixe.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger('PickTag2GetRole.Crypto')

# Préfixe des jetons Fernet (version 0x80 encodée en base64url)
FERNET_PREFIX = 'gAAAAA'


class EncryptionKeyError(RuntimeError):
    """Clé absente ou incorrecte face à des données déjà chiffrées."""


class FieldCipher:
    """Chiffre/déchiffre les valeurs texte stockées en base."""

    def __init__(self, key: Optional[str] = None):
        raw_key = key if key is not None else os.getenv('ENCRYPTION_KEY', '')
        raw_key = (raw_key or '').strip()

        self._fernet = None
        if raw_key:
            try:
                from cryptography.fernet import Fernet
            except ImportError as e:  # pragma: no cover - dépendance déclarée
                raise EncryptionKeyError(
                    "ENCRYPTION_KEY is set but the 'cryptography' package is missing. "
                    "Install requirements.txt or unset ENCRYPTION_KEY."
                ) from e
            try:
                self._fernet = Fernet(raw_key)
            except (ValueError, TypeError) as e:
                raise EncryptionKeyError(
                    "ENCRYPTION_KEY is not a valid Fernet key. Generate one with: "
                    "python -c \"from cryptography.fernet import Fernet; "
                    "print(Fernet.generate_key().decode())\""
                ) from e

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    @staticmethod
    def looks_encrypted(value) -> bool:
        return isinstance(value, str) and value.startswith(FERNET_PREFIX)

    def encrypt(self, value):
        """Chiffrer une valeur texte (None et chaînes vides passent tel quel)."""
        if self._fernet is None or value is None or value == '':
            return value
        if self.looks_encrypted(value):
            return value  # déjà chiffré, ne pas empiler les couches
        return self._fernet.encrypt(str(value).encode('utf-8')).decode('ascii')

    def decrypt(self, value):
        """Déchiffrer une valeur ; les valeurs en clair (pré-migration) sont rendues telles quelles."""
        if value is None or value == '':
            return value
        if not self.looks_encrypted(value):
            # Donnée écrite avant l'activation du chiffrement
            return value
        if self._fernet is None:
            raise EncryptionKeyError(
                "The database contains encrypted values but ENCRYPTION_KEY is not set. "
                "Restore the key used to write this database, or restore a plaintext backup."
            )
        from cryptography.fernet import InvalidToken
        try:
            return self._fernet.decrypt(value.encode('ascii')).decode('utf-8')
        except InvalidToken as e:
            raise EncryptionKeyError(
                "ENCRYPTION_KEY does not match the key used to encrypt this database. "
                "Restore the original key, or restore a backup written with the current key."
            ) from e

    def encrypt_int(self, value: Optional[int]):
        if self._fernet is None or value is None:
            return value
        return self.encrypt(str(int(value)))

    def decrypt_int(self, value, default: int = 0) -> int:
        """Déchiffrer un compteur ; toute valeur illisible dégrade à `default`.

        EncryptionKeyError inclus : un compteur de statistique corrompu doit
        s'afficher à 0, pas casser /stats pendant 30 jours — /config ne réécrit
        jamais tag_stats, aucune commande ne pourrait donc réparer la ligne.
        """
        if value is None:
            return default
        try:
            return int(self.decrypt(value))
        except (TypeError, ValueError, EncryptionKeyError):
            return default
