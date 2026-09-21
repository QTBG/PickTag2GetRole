"""Journaux operationnels sans payloads Discord ni traces d'exception."""
from __future__ import annotations

import copy
import logging
from logging.handlers import RotatingFileHandler


class ApplicationLogFilter(logging.Filter):
    """Les bibliotheques peuvent journaliser des profils meme au niveau DEBUG."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name == 'PickTag2GetRole' or record.name.startswith('PickTag2GetRole.')


class PrivacyFormatter(logging.Formatter):
    """Ne jamais serialiser une exception susceptible de contenir une reponse API."""

    def format(self, record: logging.LogRecord) -> str:
        safe = copy.copy(record)
        safe.exc_info = None
        safe.exc_text = None
        safe.stack_info = None
        return super().format(safe)


def configure_logging(level: str = 'INFO', filename: str = '') -> None:
    """Installer le meme filtrage sur stdout et le fichier optionnel.

    Les messages applicatifs doivent rester des constantes operationnelles.
    Les donnees et compteurs de diagnostic d'un
    serveur sont accessibles par les commandes ephemeres dans Discord.
    """
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if filename:
        handlers.append(RotatingFileHandler(
            filename, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8',
        ))
    formatter = PrivacyFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    for handler in handlers:
        handler.addFilter(ApplicationLogFilter())
        handler.setFormatter(formatter)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=handlers,
        force=True,
    )
