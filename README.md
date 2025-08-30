# PickTag2GetRole

Un bot Discord ultra-optimisé pour surveiller les tags de serveur et attribuer automatiquement des rôles aux utilisateurs. Conçu pour fonctionner sur des VPS très légers avec un seul cœur CPU.

*[English version below](#picktag2getrole-english)*

## 🚀 Fonctionnalités

- **Surveillance automatique des tags** : Détecte quand un utilisateur ajoute ou retire un tag de serveur
- **Attribution de rôles automatique** : Ajoute/retire des rôles en fonction de la présence du tag
- **Commandes slash intuitives** : Configuration facile via Discord
- **Optimisé pour les ressources** : Conçu pour tourner sur des VPS avec 1 CPU et peu de RAM
- **Événements en temps réel** : Utilise les événements Discord pour une réactivité maximale
- **Vérification de sécurité** : Vérification au démarrage et une fois par jour pour garantir la cohérence

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
- `LOG_LEVEL` : Niveau de logging (optionnel, défaut: INFO). Valeurs possibles : DEBUG, INFO, WARNING, ERROR

### Base de données

Le bot utilise une base de données SQLite (`data/bot_data.db`) pour stocker les configurations de manière sécurisée. Le fichier de base de données est stocké dans un dossier `data/` qui est créé automatiquement. Chaque serveur a ses propres données isolées :
- Les tags surveillés par serveur
- Les rôles à attribuer
- L'état d'activation du bot

**Sécurité & Confidentialité** :
- Chaque serveur n'a accès qu'à ses propres données
- Les données sont automatiquement supprimées quand le bot est retiré d'un serveur


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

4. **Activer les intents** (⚠️ TRÈS IMPORTANT)
   - Sur la même page, activer ces deux intents :
     - **SERVER MEMBERS INTENT** : Pour accéder aux membres
     - **PRESENCE INTENT** : Pour accéder aux tags de serveur (primary guild)
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
2. **Performance** : Le bot réagit instantanément aux changements via les événements Discord, avec une vérification quotidienne de sécurité
3. **Limites** : Sur un VPS très léger, évitez de surveiller trop de serveurs très grands simultanément

## 🐛 Dépannage

### Le bot ne détecte pas les tags
- **Vérifier les intents Discord** : PRESENCE INTENT doit être activé dans le Developer Portal
- Vérifier que le tag est exactement comme configuré (respecter la casse)
- S'assurer que le bot a les permissions nécessaires
- Utiliser `/scan debug:True` pour activer les logs détaillés (consultez bot.log)
- Vérifier que les utilisateurs ont leur "Primary Guild" (tag de serveur) en public
- Pour un debug permanent, définir `LOG_LEVEL=DEBUG` dans le fichier .env

### Erreurs de permissions
- Le bot doit avoir un rôle plus élevé que les rôles qu'il essaie d'attribuer
- Vérifier que le bot a la permission "Manage Roles"

### Utilisation CPU/RAM élevée
- Augmenter l'intervalle de vérification dans `tag_monitor.py`
- Réduire le nombre de serveurs surveillés
- Vérifier les logs pour des erreurs en boucle

## 📄 Licence

Ce projet est sous licence MIT.

## 📜 Informations Légales

- [Terms of Service](TERMS_OF_SERVICE.md)
- [Privacy Policy](PRIVACY_POLICY.md)

---

# PickTag2GetRole (English)

An ultra-optimized Discord bot for monitoring server tags and automatically assigning roles to users. Designed to run on very lightweight VPS with a single CPU core.

## 🚀 Features

- **Automatic tag monitoring**: Detects when a user adds or removes a server tag
- **Automatic role assignment**: Adds/removes roles based on tag presence
- **Intuitive slash commands**: Easy configuration via Discord
- **Resource optimized**: Designed to run on VPS with 1 CPU and low RAM
- **Real-time events**: Uses Discord events for maximum responsiveness
- **Safety verification**: Verification at startup and once daily to ensure consistency

## 📋 Prerequisites

- Python 3.11+ or Docker
- A Discord bot with its token (see "Getting the bot token" section)
- Bot permissions:
  - Manage Roles
  - View Server Members
  - Read Server Information

## 🛠️ Installation

### Option 1: With Docker (Recommended)

1. **Clone the project**
   ```bash
   git clone https://github.com/QTBG/PickTag2GetRole.git
   cd PickTag2GetRole
   ```

2. **Configure the bot**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your Discord token:
   ```
   DISCORD_TOKEN=your_token_here
   ```

3. **Launch with Docker Compose**
   ```bash
   docker-compose up -d
   ```

### Option 2: Without Docker

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure the bot**
   ```bash
   cp .env.example .env
   # Edit .env with your token
   ```

3. **Run the bot**
   ```bash
   python bot.py
   ```

## 🎮 Usage

### Available Commands

- **`/config <tag> <@role1 @role2...>`**: Configure the tag to monitor and roles to assign
  - Example: `/config [TAG] @Member @VIP`
  
- **`/status`**: Display current bot configuration
  
- **`/toggle`**: Enable or disable tag monitoring
  
- **`/scan`**: Force an immediate scan of all members (useful after initial configuration)

### Initial Setup

1. Invite the bot to your server with necessary permissions
2. Use `/config` to define:
   - The tag to monitor (exactly as it appears)
   - The roles to assign (mention with @)
3. Use `/scan` to apply roles to members who already have the tag
4. The bot will then automatically monitor changes

## 🔧 Advanced Configuration

### Environment Variables

- `DISCORD_TOKEN`: Discord bot token (required)
- `LOG_LEVEL`: Logging level (optional, default: INFO). Possible values: DEBUG, INFO, WARNING, ERROR

### Database

The bot uses an SQLite database (`data/bot_data.db`) to securely store configurations. The database file is stored in a `data/` folder that is created automatically. Each server has its own isolated data:
- Tags monitored per server
- Roles to assign
- Bot activation status

**Security & Privacy**:
- Each server only has access to its own data
- Data is automatically deleted when the bot is removed from a server

### Optimizations for Lightweight VPS

The bot is optimized to:
- Use minimum RAM (Docker limit: 256MB)
- Use low CPU (Docker limit: 0.5 CPU)
- Disable unnecessary Discord intents
- Use events rather than constant polling
- Process members in batches with pauses

## 🔒 Security and Privacy

The bot is designed with security and privacy as priorities:

### Data Protection
- **SQLite database**: Each server has isolated data
- **No cross-server sharing**: One server's configurations are never accessible by others
- **Automatic deletion**: Data is deleted when the bot leaves a server
- **Minimal data**: Only necessary IDs are stored (no messages, no personal data)

### Secure Architecture
- **No shared file**: Unlike a single JSON file, the database isolates data
- **Discord permissions**: The bot only requests necessary permissions
- **Minimal logs**: No sensitive data is logged

## 🐳 Docker

### Manual Build
```bash
docker build -t picktag2getrole .
```

### Run without docker-compose
```bash
docker run -d \
  --name picktag2getrole \
  --restart unless-stopped \
  -e DISCORD_TOKEN=your_token \
  -v $(pwd)/data:/app/data \
  picktag2getrole
```

### View logs
```bash
docker logs picktag2getrole
```

## 🔑 Getting the Bot Token

1. **Create a Discord application**
   - Go to https://discord.com/developers/applications
   - Click "New Application" and give it a name

2. **Create the bot**
   - In the left menu, click "Bot"
   - Click "Add Bot"

3. **Get the token**
   - Click "Reset Token"
   - Copy the token that appears (⚠️ will only be shown once!)
   - This is the token to put in the `.env` file

4. **Enable intents** (⚠️ VERY IMPORTANT)
   - On the same page, enable these two intents:
     - **SERVER MEMBERS INTENT**: To access members
     - **PRESENCE INTENT**: To access server tags (primary guild)
   - Save changes

## 🤝 Required Discord Permissions

The bot ONLY needs these permissions:
- **Manage Roles** (268435456): To add/remove roles
- **View Channels** (1024): To access servers

To invite the bot:
1. In the Developer Portal, go to "OAuth2" > "URL Generator"
2. Check `bot` and `applications.commands`
3. Select ONLY: Manage Roles + View Channels
4. Use the generated URL to invite the bot

Invitation link with minimal permissions:
```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=268436480&scope=bot%20applications.commands
```

⚠️ The bot does NOT need:
- Read Message History
- Send Messages
- Read Messages
- Or any other permission

## 📝 Important Notes

1. **Server tags**: Tags can be in the display name or avatar decorations
2. **Performance**: The bot responds instantly to changes via Discord events, with a daily safety verification
3. **Limits**: On a very light VPS, avoid monitoring too many very large servers simultaneously

## 🐛 Troubleshooting

### Bot doesn't detect tags
- **Check Discord intents**: PRESENCE INTENT must be enabled in the Developer Portal
- Verify that the tag is exactly as configured (case sensitive)
- Ensure the bot has necessary permissions
- Use `/scan debug:True` to enable detailed logs (check bot.log)
- Verify that users have their "Primary Guild" (server tag) public
- For permanent debug, set `LOG_LEVEL=DEBUG` in the .env file

### Permission errors
- The bot must have a role higher than the roles it's trying to assign
- Check that the bot has the "Manage Roles" permission

### High CPU/RAM usage
- Increase the verification interval in `tag_monitor.py`
- Reduce the number of monitored servers
- Check logs for looping errors

## 📄 License

This project is under MIT license.

## 📜 Legal Information

- [Terms of Service](TERMS_OF_SERVICE.md)
- [Privacy Policy](PRIVACY_POLICY.md)