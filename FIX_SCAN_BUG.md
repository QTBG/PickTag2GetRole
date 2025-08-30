# Correction du bug de la commande /scan

## Problème identifié

La commande `/scan` supprimait les rôles des membres qui avaient pourtant le tag configuré dans leur statut personnalisé.

## Causes du problème

1. **Méthode `fetch_members()`** : Cette méthode Discord ne récupère pas toutes les informations des membres, notamment :
   - Les activités (statuts personnalisés)
   - Les présences
   
2. **Intent `presences` manquant** : Le bot n'avait pas l'intent `presences` activé, ce qui est nécessaire pour accéder aux activités et statuts personnalisés des membres.

## Solutions appliquées

### 1. Modification de la méthode de récupération des membres

Dans `/workspace/cogs/commands.py` (ligne 225) :
- **Avant** : `async for member in interaction.guild.fetch_members(limit=None):`
- **Après** : `for member in interaction.guild.members:`

L'utilisation de `guild.members` permet d'accéder aux données en cache qui incluent les activités et présences.

### 2. Activation de l'intent `presences`

Dans `/workspace/bot.py` (ligne 18) :
- Ajout de : `intents.presences = True`

Ceci est nécessaire pour que Discord envoie les informations de présence et d'activité au bot.

### 3. Ajout de logs de débogage

Des logs ont été ajoutés pour faciliter le débogage futur :
- Dans la commande `/scan` pour tracer les membres avec le tag
- Dans la méthode `_member_has_tag` (commenté par défaut)

## Impact

Ces modifications permettent à la commande `/scan` de :
- Détecter correctement les tags dans les statuts personnalisés
- Ne plus supprimer les rôles des membres qui ont le tag
- Fonctionner de manière cohérente avec le monitoring en temps réel

## Note importante

⚠️ **L'intent `presences` doit être activé dans les paramètres du bot sur Discord Developer Portal** pour que ces modifications fonctionnent correctement.