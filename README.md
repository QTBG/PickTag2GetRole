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
- **Garde-fous anti-erreur** : Une configuration qui ne peut correspondre à aucun membre est refusée à la saisie et neutralisée à l'exécution — jamais de retrait de rôles en masse

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
  - Exemple : `/config tag:VIP roles:@Membre @VIP`
  - ⚠️ Le champ `tag` attend le **tag de serveur** : les 2 à 4 caractères affichés à côté des pseudos. Ce n'est **pas** une mention de rôle — coller un `@Rôle` ici est l'erreur la plus fréquente, et elle est refusée
  - Un tag de plus de 4 caractères est refusé : les tags de serveur Discord font 4 caractères maximum, il ne pourrait donc correspondre à personne
  - Un tag contenant `#` active la correspondance partielle (usage volontaire)
  - Sécurité : impossible de configurer un rôle supérieur ou égal à votre rôle le plus élevé (ou à celui du bot)
  
- **`/status`** : Affiche la configuration actuelle du bot et le nombre de membres ayant le tag. Signale aussi les deux pannes silencieuses : tag invalide (surveillance en pause) et permissions insuffisantes (nombre de membres qui n'ont pas pu être mis à jour)
  
- **`/toggle`** : Active ou désactive la surveillance des tags
  
- **`/scan`** : Force un scan immédiat de tous les membres (utile après la configuration initiale, cooldown de 60s)

- **`/check <@membre>`** : Vérifie le statut du tag d'un membre spécifique

- **`/stats`** : Évolution du nombre de membres avec le tag (7 jours, 30 jours, mini-graphe). Compteurs agrégés uniquement, aucun ID utilisateur stocké

- **`/reset`** : Supprime la configuration et toutes les données stockées pour ce serveur

- **`/botstats`** : Statistiques globales du bot (réservé au propriétaire du bot) : serveurs, membres, uptime, RAM, latence, taille de la base

- **`/help`** : Liste toutes les commandes disponibles, avec les liens cliquables vers la politique de confidentialité et les conditions d'utilisation

### Configuration initiale

1. Inviter le bot sur votre serveur avec les permissions nécessaires
2. **Placer le rôle du bot au-dessus des rôles qu'il doit attribuer** (Paramètres du serveur → Rôles) : sans cela il ne pourra modifier personne
3. Utiliser `/config` pour définir :
   - Le tag à surveiller : le tag de serveur court (2 à 4 caractères), exactement comme il apparaît à côté des pseudos — **pas** une mention de rôle
   - Les rôles à attribuer (mentionner avec @)
4. Vérifier avec `/status` qu'aucun avertissement n'est signalé
5. Utiliser `/scan` pour appliquer les rôles aux membres ayant déjà le tag
6. Le bot surveillera ensuite automatiquement les changements

## 🔧 Configuration avancée

### Variables d'environnement

- `DISCORD_TOKEN` : Token du bot Discord (obligatoire)
- `LOG_LEVEL` : Niveau de logging (optionnel, défaut: INFO). Valeurs possibles : DEBUG, INFO, WARNING, ERROR
- `LOG_FILE` : Chemin du fichier de log (optionnel, défaut: `bot.log`, rotation automatique 5 Mo × 3). Mettre une valeur vide pour ne logger que sur stdout (recommandé sous Docker)
- `CHUNK_ENABLED_GUILDS` : `true` (défaut) charge en cache la liste complète des membres des serveurs où la surveillance est **activée**, pour une détection temps réel complète même sur les gros serveurs (>250 membres). Coût : ~1 Ko de RAM par membre mis en cache — avec beaucoup de très gros serveurs, augmentez la limite mémoire Docker (ex: 384M/512M) ou mettez `false` (la détection reposera alors sur le scan quotidien et `/scan` pour les gros serveurs)
- `ENCRYPTION_KEY` : Clé Fernet activant le **chiffrement au repos** des valeurs stockées (recommandé, voir la section dédiée). Vide = stockage en clair
- `BACKUP_ENABLED` : `true` (défaut) active la sauvegarde quotidienne de la base dans `data/backups/`
- `BACKUP_KEEP` : Nombre de sauvegardes journalières conservées (défaut : 7)
- `MEMORY_LIMIT` / `CPU_LIMIT` : Limites du conteneur, utilisées uniquement par `docker-compose.yml` (défauts : `512M` et `0.5`)
- `HEARTBEAT_FILE` : Fichier touché toutes les minutes et lu par le HEALTHCHECK du conteneur (défaut : `/tmp/picktag_heartbeat`, rarement modifié)

### Base de données

Le bot utilise une base de données SQLite (`data/bot_data.db`) pour stocker les configurations de manière sécurisée. Le fichier de base de données est stocké dans un dossier `data/` qui est créé automatiquement. Chaque serveur a ses propres données isolées :
- Les tags surveillés par serveur
- Les rôles à attribuer
- L'état d'activation du bot

**Sécurité & Confidentialité** :
- Chaque serveur n'a accès qu'à ses propres données
- Les données sont automatiquement supprimées quand le bot est retiré d'un serveur

### Chiffrement au repos

Avec `ENCRYPTION_KEY` définie, toutes les **valeurs** stockées sont chiffrées avec Fernet (AES-128-CBC + HMAC-SHA256) : tag surveillé, IDs de rôles et compteurs journaliers. Les identifiants qui servent de clés (ID de serveur, date) restent en clair pour rester indexables.

Une copie du fichier de base, ou d'une sauvegarde, est donc inexploitable sans la clé.

**Générer une clé** :
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Renseignez-la ensuite dans `ENCRYPTION_KEY` (variable d'environnement, jamais dans le volume de données).

**Migration** : au premier démarrage avec une clé, les données existantes en clair sont chiffrées automatiquement. L'opération est idempotente et ne perd aucune configuration.

⚠️ **Conservez la clé hors du serveur.** Sans elle, une base déjà chiffrée (et ses sauvegardes) est irrécupérable. Le bot refuse de démarrer si la clé est absente, incorrecte ou malformée, plutôt que de tourner avec des données illisibles et d'écraser des configurations valides.

Sans `ENCRYPTION_KEY`, le bot fonctionne en clair : les installations auto-hébergées existantes ne sont pas cassées. `/botstats` indique l'état du chiffrement.

### Sauvegardes automatiques

Le bot sauvegarde automatiquement sa base SQLite pour se protéger d'une corruption :

- **Quand** : au démarrage puis toutes les 24 h
- **Où** : `data/backups/bot_data-YYYYMMDD.db` (un fichier par jour, les `BACKUP_KEEP` plus récents conservés, 7 par défaut)
- **Comment** : API de sauvegarde en ligne de SQLite — snapshot cohérent même pendant les écritures (un simple `cp` d'une base WAL active ne l'est pas), écriture atomique
- **Contrôle d'intégrité** : `PRAGMA quick_check` avant chaque sauvegarde. En cas d'échec, le bot n'écrase **ni ne purge** les sauvegardes saines existantes et logge une erreur bien visible (visible aussi dans `/botstats`)

**Restauration** (le volume Docker `picktag_data` contient `bot_data.db` et `backups/`) :
```bash
docker compose down                                            # ou arrêter l'app dans Dokploy
VOL=$(docker volume ls -q | grep picktag_data | head -1)
MP=$(docker volume inspect -f '{{.Mountpoint}}' "$VOL")
sudo cp "$MP/backups/bot_data-AAAAMMJJ.db" "$MP/bot_data.db"
sudo rm -f "$MP/bot_data.db-wal" "$MP/bot_data.db-shm"
sudo chown -R 1000:1000 "$MP"
docker compose up -d                                           # ou redéployer dans Dokploy
```

⚠️ Ces sauvegardes restent sur le même disque que la base. Pour survivre à une panne disque du VPS, copiez-les régulièrement ailleurs (cron + `scp`/`rclone`) — elles ne pèsent que quelques Ko :
```bash
0 5 * * * rsync -a "$(docker volume inspect -f '{{.Mountpoint}}' picktag_data)/backups/" user@autre-machine:~/picktag-backups/
```

### Optimisations pour VPS léger

Le bot est optimisé pour :
- Utiliser peu de RAM (limite Docker par défaut : 512MB, ajustable via `MEMORY_LIMIT`)
- Utiliser peu de CPU (limite Docker : 0.5 CPU, ajustable via `CPU_LIMIT`)
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

### Healthcheck

Le conteneur embarque un `HEALTHCHECK` : le bot touche `HEARTBEAT_FILE` toutes les minutes tant que la gateway Discord répond. Si le process se fige ou perd la connexion, le fichier cesse d'être mis à jour et le conteneur passe en `unhealthy` (fenêtre de 5 min, `start-period` de 30 s pour laisser le temps à la connexion initiale).

```bash
docker inspect --format '{{.State.Health.Status}}' picktag2getrole
```

### ⚠️ Migration depuis une ancienne version (conteneur root)

Le conteneur tourne désormais avec un utilisateur non-root (UID 1000) pour plus de sécurité. Si vous montez un dossier de l'hôte créé par une ancienne version (root), corrigez ses permissions une seule fois :
```bash
sudo chown -R 1000:1000 ./data
```
Avec le volume nommé `picktag_data` (configuration par défaut), rien à faire : le volume hérite automatiquement du bon propriétaire à sa création.

## 🚀 Déploiement avec Dokploy

Le `docker-compose.yml` du dépôt fonctionne tel quel avec Dokploy.

1. **Créer l'application** : *Create Service* → **Compose** → Provider **GitHub/Git**, dépôt `QTBG/PickTag2GetRole`, branche `main`, Compose Path `./docker-compose.yml`, Compose Type **Docker Compose**
2. **Environnement** : onglet *Environment*, coller au minimum :
   ```
   DISCORD_TOKEN=votre_token
   ```
   (toutes les autres variables ont des valeurs par défaut — voir `.env.example`)
3. **Déployer** : bouton *Deploy*. Le volume nommé `picktag_data` est créé automatiquement et **persiste entre les déploiements**
4. **Vérifier** : les logs doivent afficher `Bot connected as ...`, et `/botstats` sur Discord donne l'état complet (RAM, intégrité de la base, dernière sauvegarde)

**Migrer une base existante vers Dokploy** : voir la procédure de transfert dans la section *Sauvegardes automatiques* ci-dessus (même principe : copier le fichier `.db` dans le mountpoint du volume, puis `chown -R 1000:1000`).

⚠️ **Ne pas utiliser de bind mount relatif** (`./data:/app/data`) avec Dokploy : le dossier du code est recréé à chaque déploiement, la base serait perdue. Le volume nommé du dépôt évite ce piège.

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

1. **Tags de serveur** : Le bot lit le tag "Primary Guild" (tag de serveur) affiché sur le profil, à côté du pseudo. L'utilisateur doit l'avoir activé publiquement
2. **Performance** : Le bot réagit instantanément aux changements via les événements Discord, avec une vérification quotidienne de sécurité
3. **Détection temps réel** : Par défaut (`CHUNK_ENABLED_GUILDS=true`), le bot met en cache les membres des serveurs surveillés pour une détection instantanée complète, même sur les gros serveurs. Avec `false`, les serveurs >250 membres sont surtout couverts par le scan quotidien et `/scan`
4. **Langues** : Les commandes et réponses sont localisées en anglais, français, espagnol, allemand, italien et portugais (Brésil), selon la langue du client Discord de chaque utilisateur
5. **Limites** : Sur un VPS très léger, évitez de surveiller trop de serveurs très grands simultanément

## 🐛 Dépannage

### Le bot ne détecte pas les tags
- **Vérifier les intents Discord** : PRESENCE INTENT et SERVER MEMBERS INTENT doivent être activés dans le Developer Portal
- Vérifier que le tag est exactement comme configuré
- S'assurer que le bot a les permissions nécessaires
- Vérifier que les utilisateurs ont leur "Primary Guild" (tag de serveur) affiché publiquement
- Pour des logs détaillés, définir `LOG_LEVEL=DEBUG` dans le fichier .env puis consulter bot.log (ou `docker logs`)
- Lancer `/scan` pour forcer une resynchronisation immédiate

### « monitoring paused for this guild » dans les logs

```
Guild 123...: configured tag is a role mention — it can never match a server tag;
monitoring paused for this guild to avoid mass role removal
```

(ou `configured tag is 26 characters (server tags are at most 4)` selon le cas — la valeur elle-même n'apparaît jamais dans les logs.)

Une valeur impossible à satisfaire a été enregistrée dans le champ `tag` : une mention de rôle collée, ou un tag de plus de 4 caractères (la limite des tags de serveur Discord). Une telle valeur ne peut correspondre à aucun membre : sans garde-fou, le bot en conclurait que plus personne ne porte le tag et retirerait les rôles à tout le serveur. Il met donc la surveillance en pause et **ne touche à aucun rôle** jusqu'à correction.

**Correctif** : relancer `/config` avec le tag de serveur court (ex. `tag:VIP`) et laisser les rôles dans le champ `roles`. `/status` affiche l'alerte tant que la configuration est cassée.

### Erreurs de permissions

```
Guild 123...: missing permissions to manage roles — my role is probably
below the configured roles, or I lack Manage Roles
```

- Le bot doit avoir un rôle plus élevé que les rôles qu'il essaie d'attribuer (Paramètres du serveur → Rôles, glisser le rôle du bot au-dessus)
- Vérifier que le bot a la permission "Manage Roles"
- `/status` indique combien de membres distincts n'ont pas pu être mis à jour depuis le dernier scan (scan et événements temps réel compris)
- Le message n'apparaît qu'une fois par serveur et par scan, pas une ligne par membre

### Utilisation CPU/RAM élevée
- Augmenter l'intervalle de vérification dans `tag_monitor.py`
- Réduire le nombre de serveurs surveillés
- Vérifier les logs pour des erreurs en boucle

## 📄 Licence

Ce projet est sous licence MIT.

## 📜 Informations Légales

- [Terms of Service](TERMS_OF_SERVICE.md)
- [Privacy Policy](PRIVACY_POLICY.md)

Ces deux documents sont aussi accessibles directement depuis Discord via `/help`, sans quitter le serveur.

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
- **Misconfiguration safeguards**: A configuration that can never match any member is rejected at input and neutralized at runtime — no mass role removal, ever

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
  - Example: `/config tag:VIP roles:@Member @VIP`
  - ⚠️ The `tag` field expects the **server tag**: the 2-4 characters shown next to member names. It is **not** a role mention — pasting an `@Role` here is the most common mistake, and it is rejected
  - A tag longer than 4 characters is rejected: Discord server tags are 4 characters at most, so it could never match anyone
  - A tag containing `#` enables partial matching (an intentional use)
  - Security: you cannot configure a role higher than or equal to your own highest role (or the bot's)
  
- **`/status`**: Display current bot configuration and how many members have the tag. Also surfaces the two silent failure modes: invalid tag (monitoring paused) and missing permissions (how many members could not be updated)
  
- **`/toggle`**: Enable or disable tag monitoring
  
- **`/scan`**: Force an immediate scan of all members (useful after initial configuration, 60s cooldown)

- **`/check <@member>`**: Check a specific member's tag status

- **`/stats`**: Evolution of members with the tag (7 days, 30 days, mini-chart). Aggregated counters only, no user IDs stored

- **`/reset`**: Delete the configuration and all stored data for this server

- **`/botstats`**: Global bot statistics (bot owner only): servers, members, uptime, RAM, latency, database size

- **`/help`**: Lists all available commands, with clickable links to the privacy policy and terms of service

### Initial Setup

1. Invite the bot to your server with necessary permissions
2. **Move the bot's role above the roles it must assign** (Server Settings → Roles): without this it cannot update anyone
3. Use `/config` to define:
   - The tag to monitor: the short server tag (2-4 characters), exactly as it appears next to member names — **not** a role mention
   - The roles to assign (mention with @)
4. Check with `/status` that no warning is reported
5. Use `/scan` to apply roles to members who already have the tag
6. The bot will then automatically monitor changes

## 🔧 Advanced Configuration

### Environment Variables

- `DISCORD_TOKEN`: Discord bot token (required)
- `LOG_LEVEL`: Logging level (optional, default: INFO). Possible values: DEBUG, INFO, WARNING, ERROR
- `LOG_FILE`: Log file path (optional, default: `bot.log`, automatic rotation 5 MB × 3). Set to an empty value to log to stdout only (recommended with Docker)
- `CHUNK_ENABLED_GUILDS`: `true` (default) caches the full member list of servers where monitoring is **enabled**, for complete real-time detection even on large servers (>250 members). Cost: ~1 KB of RAM per cached member — with many very large servers, raise the Docker memory limit (e.g. 384M/512M) or set `false` (large servers will then rely on the daily scan and `/scan`)
- `BACKUP_ENABLED`: `true` (default) enables the daily database backup into `data/backups/`
- `ENCRYPTION_KEY`: Fernet key enabling **encryption at rest** for stored values (recommended, see dedicated section). Empty means clear-text storage
- `BACKUP_KEEP`: Number of daily backup files to keep (default: 7)
- `MEMORY_LIMIT` / `CPU_LIMIT`: Container limits, used by `docker-compose.yml` only (defaults: `512M` and `0.5`)
- `HEARTBEAT_FILE`: File touched every minute and read by the container HEALTHCHECK (default: `/tmp/picktag_heartbeat`, rarely changed)

### Database

The bot uses an SQLite database (`data/bot_data.db`) to securely store configurations. The database file is stored in a `data/` folder that is created automatically. Each server has its own isolated data:
- Tags monitored per server
- Roles to assign
- Bot activation status

**Security & Privacy**:
- Each server only has access to its own data
- Data is automatically deleted when the bot is removed from a server

### Encryption at Rest

When `ENCRYPTION_KEY` is set, every stored **value** is encrypted with Fernet (AES-128-CBC + HMAC-SHA256): the monitored tag, role IDs and daily counters. Identifiers used as keys (guild ID, date) stay in clear text so they remain indexable.

A copy of the database file, or of a backup, is therefore unusable without the key.

**Generate a key**:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Then set it as `ENCRYPTION_KEY` (environment variable, never inside the data volume).

**Migration**: on the first start with a key, existing clear-text data is encrypted automatically. The operation is idempotent and loses no configuration.

⚠️ **Keep the key off the server.** Without it, an already encrypted database (and its backups) cannot be recovered. The bot refuses to start when the key is missing, wrong or malformed, rather than running with unreadable data and overwriting valid configurations.

Without `ENCRYPTION_KEY` the bot runs in clear text, so existing self-hosted installs keep working. `/botstats` reports the encryption status.

### Automatic Backups

The bot automatically backs up its SQLite database to protect against corruption:

- **When**: at startup, then every 24h
- **Where**: `data/backups/bot_data-YYYYMMDD.db` (one file per day, the `BACKUP_KEEP` most recent kept, 7 by default)
- **How**: SQLite's online backup API — a consistent snapshot even during writes (a plain `cp` of a live WAL database is not), atomic write
- **Integrity check**: `PRAGMA quick_check` before every backup. On failure, the bot neither overwrites **nor rotates out** existing healthy backups, and logs a loud error (also visible in `/botstats`)

**Restore** (the `picktag_data` Docker volume holds `bot_data.db` and `backups/`):
```bash
docker compose down                                            # or stop the app in Dokploy
VOL=$(docker volume ls -q | grep picktag_data | head -1)
MP=$(docker volume inspect -f '{{.Mountpoint}}' "$VOL")
sudo cp "$MP/backups/bot_data-YYYYMMDD.db" "$MP/bot_data.db"
sudo rm -f "$MP/bot_data.db-wal" "$MP/bot_data.db-shm"
sudo chown -R 1000:1000 "$MP"
docker compose up -d                                           # or redeploy in Dokploy
```

⚠️ These backups live on the same disk as the database. To survive a VPS disk failure, copy them elsewhere regularly (cron + `scp`/`rclone`) — they only weigh a few KB:
```bash
0 5 * * * rsync -a "$(docker volume inspect -f '{{.Mountpoint}}' picktag_data)/backups/" user@other-machine:~/picktag-backups/
```

### Optimizations for Lightweight VPS

The bot is optimized to:
- Use little RAM (default Docker limit: 512MB, tunable via `MEMORY_LIMIT`)
- Use low CPU (Docker limit: 0.5 CPU, tunable via `CPU_LIMIT`)
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

### Healthcheck

The container ships a `HEALTHCHECK`: the bot touches `HEARTBEAT_FILE` every minute for as long as the Discord gateway responds. If the process freezes or loses its connection, the file stops being updated and the container turns `unhealthy` (5 min window, 30 s `start-period` to allow for the initial connection).

```bash
docker inspect --format '{{.State.Health.Status}}' picktag2getrole
```

### ⚠️ Migrating from an older version (root container)

The container now runs as a non-root user (UID 1000) for better security. If you mount a host folder created by an older (root) version, fix its permissions once:
```bash
sudo chown -R 1000:1000 ./data
```
With the named volume `picktag_data` (default setup), nothing to do: the volume automatically inherits the correct owner when created.

## 🚀 Deploying with Dokploy

The repository's `docker-compose.yml` works as-is with Dokploy.

1. **Create the application**: *Create Service* → **Compose** → Provider **GitHub/Git**, repository `QTBG/PickTag2GetRole`, branch `main`, Compose Path `./docker-compose.yml`, Compose Type **Docker Compose**
2. **Environment**: in the *Environment* tab, paste at minimum:
   ```
   DISCORD_TOKEN=your_token
   ```
   (every other variable has a default — see `.env.example`)
3. **Deploy**: hit *Deploy*. The named volume `picktag_data` is created automatically and **persists across deployments**
4. **Verify**: logs should show `Bot connected as ...`, and `/botstats` on Discord reports full status (RAM, database integrity, last backup)

**Migrating an existing database to Dokploy**: see the transfer procedure in the *Automatic Backups* section above (same idea: copy the `.db` file into the volume mountpoint, then `chown -R 1000:1000`).

⚠️ **Do not use a relative bind mount** (`./data:/app/data`) with Dokploy: the code directory is recreated on every deployment, so the database would be lost. The repository's named volume avoids this pitfall.

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

1. **Server tags**: The bot reads the "Primary Guild" tag (server tag) displayed on the profile, next to the username. Users must have it publicly enabled
2. **Performance**: The bot responds instantly to changes via Discord events, with a daily safety verification
3. **Real-time detection**: By default (`CHUNK_ENABLED_GUILDS=true`), the bot caches members of monitored servers for complete instant detection, even on large servers. With `false`, servers >250 members are mostly covered by the daily scan and `/scan`
4. **Languages**: Commands and responses are localized in English, French, Spanish, German, Italian and Brazilian Portuguese, based on each user's Discord client language
5. **Limits**: On a very light VPS, avoid monitoring too many very large servers simultaneously

## 🐛 Troubleshooting

### Bot doesn't detect tags
- **Check Discord intents**: PRESENCE INTENT and SERVER MEMBERS INTENT must be enabled in the Developer Portal
- Verify that the tag is exactly as configured
- Ensure the bot has necessary permissions
- Verify that users have their "Primary Guild" (server tag) publicly displayed
- For detailed logs, set `LOG_LEVEL=DEBUG` in the .env file then check bot.log (or `docker logs`)
- Run `/scan` to force an immediate resynchronization

### "monitoring paused for this guild" in the logs

```
Guild 123...: configured tag is a role mention — it can never match a server tag;
monitoring paused for this guild to avoid mass role removal
```

(or `configured tag is 26 characters (server tags are at most 4)` depending on the case — the value itself never appears in the logs.)

An impossible-to-satisfy value was stored in the `tag` field: a pasted role mention, or a tag longer than 4 characters (Discord's server tag limit). Such a value can never match any member: without a safeguard, the bot would conclude nobody carries the tag anymore and strip the roles from the whole server. It therefore pauses monitoring and **touches no role at all** until the configuration is fixed.

**Fix**: run `/config` again with the short server tag (e.g. `tag:VIP`) and leave the roles in the `roles` field. `/status` keeps showing the alert for as long as the configuration is broken.

### Permission errors

```
Guild 123...: missing permissions to manage roles — my role is probably
below the configured roles, or I lack Manage Roles
```

- The bot must have a role higher than the roles it's trying to assign (Server Settings → Roles, drag the bot's role above them)
- Check that the bot has the "Manage Roles" permission
- `/status` reports how many distinct members could not be updated since the last scan (scan and real-time events included)
- The message appears once per server per scan, not one line per member

### High CPU/RAM usage
- Increase the verification interval in `tag_monitor.py`
- Reduce the number of monitored servers
- Check logs for looping errors

## 📄 License

This project is under MIT license.

## 📜 Legal Information

- [Terms of Service](TERMS_OF_SERVICE.md)
- [Privacy Policy](PRIVACY_POLICY.md)

Both documents are also reachable straight from Discord via `/help`, without leaving the server.