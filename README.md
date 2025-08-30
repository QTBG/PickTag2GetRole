# PickTag2GetRole

Un bot Discord ultra-optimisé pour surveiller les tags de serveur et attribuer automatiquement des rôles aux utilisateurs. Conçu pour fonctionner sur des VPS très légers avec un seul cœur CPU.

## 🚀 Fonctionnalités

- **Surveillance automatique des tags** : Détecte quand un utilisateur ajoute ou retire un tag de serveur
- **Attribution de rôles automatique** : Ajoute/retire des rôles en fonction de la présence du tag
- **Commandes slash intuitives** : Configuration facile via Discord
- **Optimisé pour les ressources** : Conçu pour tourner sur des VPS avec 1 CPU et peu de RAM
- **Événements en temps réel** : Utilise les événements Discord pour une réactivité maximale
- **Sauvegarde périodique** : Vérification toutes les 5 minutes au cas où des événements seraient manqués

## 📋 Prérequis

- Python 3.11+ ou Docker
- Un bot Discord avec son token (voir section "Obtenir le token du bot")
- Permissions du bot : 
  - Gérer les rôles
  - Voir les membres du serveur
  - Lire les informations du serveur

## 🛠️ Installation

### Option 1 : Avec Docker (Recommandé)

1. **Cloner le projet**
   ```bash
   git clone https://github.com/QTBG/PickTag2GetRole.git
   cd PickTag2GetRole
   ```

2. **Configurer le bot**
   ```bash
   cp .env.example .env
   ```
   Éditer `.env` et ajouter votre token Discord :
   ```
   DISCORD_TOKEN=votre_token_ici
   ```

3. **Lancer avec Docker Compose**
   ```bash
   docker-compose up -d
   ```

### Option 2 : Sans Docker

1. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configurer le bot**
   ```bash
   cp .env.example .env
   # Éditer .env avec votre token
   ```

3. **Lancer le bot**
   ```bash
   python bot.py
   ```

## 🎮 Utilisation

### Commandes disponibles

- **`/config <tag> <@role1 @role2...>`** : Configure le tag à surveiller et les rôles à attribuer
  - Exemple : `/config [TAG] @Membre @VIP`
  
- **`/status`** : Affiche la configuration actuelle du bot
  
- **`/toggle`** : Active ou désactive la surveillance des tags
  
- **`/scan`** : Force un scan immédiat de tous les membres (utile après la configuration initiale)

### Configuration initiale

1. Inviter le bot sur votre serveur avec les permissions nécessaires
2. Utiliser `/config` pour définir :
   - Le tag à surveiller (exactement comme il apparaît)
   - Les rôles à attribuer (mentionner avec @)
3. Utiliser `/scan` pour appliquer les rôles aux membres ayant déjà le tag
4. Le bot surveillera ensuite automatiquement les changements

## 🔧 Configuration avancée

### Variables d'environnement

- `DISCORD_TOKEN` : Token du bot Discord (obligatoire)

### Base de données

Le bot utilise une base de données SQLite (`data/bot_data.db`) pour stocker les configurations de manière sécurisée. Le fichier de base de données est stocké dans un dossier `data/` qui est créé automatiquement. Chaque serveur a ses propres données isolées :
- Les tags surveillés par serveur
- Les rôles à attribuer
- L'état d'activation du bot

**Sécurité & Confidentialité** :
- Chaque serveur n'a accès qu'à ses propres données
- Les données sont automatiquement supprimées quand le bot est retiré d'un serveur
- Migration automatique depuis l'ancien format JSON si nécessaire

### Optimisations pour VPS léger

Le bot est optimisé pour :
- Utiliser minimum de RAM (limite Docker : 256MB)
- Utiliser peu de CPU (limite Docker : 0.5 CPU)
- Désactiver les intents Discord non nécessaires
- Utiliser des événements plutôt que du polling constant
- Traiter les membres par batch avec des pauses

## 🔒 Sécurité et Confidentialité

Le bot est conçu avec la sécurité et la confidentialité en priorité :

### Protection des données
- **Base de données SQLite** : Chaque serveur a ses données isolées
- **Pas de partage entre serveurs** : Les configurations d'un serveur ne sont jamais accessibles par d'autres
- **Suppression automatique** : Les données sont supprimées quand le bot quitte un serveur
- **Données minimales** : Seuls les IDs nécessaires sont stockés (pas de messages, pas de données personnelles)

### Architecture sécurisée
- **Pas de fichier partagé** : Contrairement à un fichier JSON unique, la base de données isole les données
- **Permissions Discord** : Le bot demande uniquement les permissions nécessaires
- **Logs minimaux** : Aucune donnée sensible n'est loggée

## 🐳 Docker

### Build manuel
```bash
docker build -t picktag2getrole .
```

### Lancer sans docker-compose
```bash
docker run -d \
  --name picktag2getrole \
  --restart unless-stopped \
  -e DISCORD_TOKEN=votre_token \
  -v $(pwd)/data:/app/data \
  picktag2getrole
```

### Voir les logs
```bash
docker logs picktag2getrole
```

## 🔑 Obtenir le token du bot

1. **Créer une application Discord**
   - Aller sur https://discord.com/developers/applications
   - Cliquer sur "New Application" et donner un nom

2. **Créer le bot**
   - Dans le menu de gauche, cliquer sur "Bot"
   - Cliquer sur "Add Bot"

3. **Récupérer le token**
   - Cliquer sur "Reset Token" 
   - Copier le token qui apparaît (⚠️ ne sera montré qu'une fois!)
   - C'est ce token qu'il faut mettre dans le fichier `.env`

4. **Activer les intents**
   - Sur la même page, activer "SERVER MEMBERS INTENT"
   - Sauvegarder les changements

## 🤝 Permissions Discord requises

Le bot a besoin UNIQUEMENT de ces permissions :
- **Manage Roles** (268435456) : Pour ajouter/retirer des rôles
- **View Channels** (1024) : Pour accéder aux serveurs

Pour inviter le bot :
1. Dans le Developer Portal, aller dans "OAuth2" > "URL Generator"
2. Cocher `bot` et `applications.commands`
3. Sélectionner UNIQUEMENT : Manage Roles + View Channels
4. Utiliser l'URL générée pour inviter le bot

Lien d'invitation avec permissions minimales :
```
https://discord.com/oauth2/authorize?client_id=VOTRE_CLIENT_ID&permissions=268436480&scope=bot%20applications.commands
```

⚠️ Le bot n'a PAS besoin de :
- Read Message History
- Send Messages
- Read Messages
- Ou toute autre permission

## 📝 Notes importantes

1. **Tags de serveur** : Les tags peuvent être dans le nom d'affichage ou les décorations d'avatar
2. **Performance** : Le bot vérifie les événements en temps réel et fait une vérification complète toutes les 5 minutes
3. **Limites** : Sur un VPS très léger, évitez de surveiller trop de serveurs très grands simultanément

## 🐛 Dépannage

### Le bot ne détecte pas les tags
- Vérifier que le tag est exactement comme configuré (respecter la casse)
- S'assurer que le bot a les permissions nécessaires
- Utiliser `/scan` pour forcer une vérification

### Erreurs de permissions
- Le bot doit avoir un rôle plus élevé que les rôles qu'il essaie d'attribuer
- Vérifier que le bot a la permission "Manage Roles"

### Utilisation CPU/RAM élevée
- Augmenter l'intervalle de vérification dans `tag_monitor.py`
- Réduire le nombre de serveurs surveillés
- Vérifier les logs pour des erreurs en boucle

## 📄 Licence

Ce projet est sous licence MIT.