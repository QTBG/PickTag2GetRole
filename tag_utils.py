"""Validation des tags de serveur configurés.

Un tag de serveur Discord est très court (4 caractères côté Discord). Certaines
valeurs saisies par erreur — typiquement une mention de rôle collée dans le champ
`tag` — ne peuvent correspondre à aucun membre. Sans garde-fou, le bot en conclut
que plus personne ne porte le tag et retire les rôles à tout le serveur.
"""
import re

# <@&123> (rôle), <@123> / <@!123> (membre), <#123> (salon), <:nom:123> (emoji custom)
MENTION_RE = re.compile(r'<(?:@[!&]?|#|a?:\w+:)\d+>')

# Longueur maximale d'un tag de serveur Discord
DISCORD_TAG_MAX_LENGTH = 4


def is_role_mention(tag: str) -> bool:
    """True si la valeur contient une mention Discord (rôle, membre, salon, emoji)."""
    return bool(tag) and bool(MENTION_RE.search(tag))


def is_unmatchable_tag(tag) -> bool:
    """True si la valeur ne peut correspondre à aucun tag de serveur réel.

    Utilisé à la configuration (pour refuser la saisie) et à l'exécution (pour
    neutraliser une configuration existante au lieu de retirer les rôles en masse).
    """
    if not tag:
        return True
    return is_role_mention(tag)


def is_suspiciously_long(tag: str) -> bool:
    """True si le tag dépasse la longueur d'un tag de serveur Discord.

    Les tags contenant '#' sont exclus : ils activent la correspondance partielle,
    qui est un usage volontaire.
    """
    return bool(tag) and '#' not in tag and len(tag) > DISCORD_TAG_MAX_LENGTH
