# PickTag2GetRole

Un bot Discord qui attribue et retire des rôles aux membres affichant le tag public de leur serveur. Il utilise **Server Members comme seul intent privilégié**, sans Presence ni Message Content.

*[English version below](#picktag2getrole-english)*

## Fonctionnement

Un membre reçoit les rôles configurés lorsque son identité de serveur est affichée publiquement, que son serveur d'origine est le serveur surveillé et que le texte du tag correspond, sans distinction de casse. Un tag identique provenant d'un autre serveur ne donne pas accès aux rôles. Les correspondances partielles avec `#` ne sont pas prises en charge.

Les événements de mise à jour des membres permettent de réagir aux changements de tag. Un scan au démarrage, un scan quotidien et `/scan` réconcilient les rôles après des changements manqués. Le bot ne lit pas les messages, les jeux ou le statut en ligne des membres.

## Installation

Prérequis : Docker, ou [uv](https://docs.astral.sh/uv/) pour une installation directe avec Python 3.14. Le bot doit disposer de **Manage Roles** et son rôle doit être placé au-dessus des rôles à attribuer.

```bash
git clone https://github.com/QTBG/PickTag2GetRole.git
cd PickTag2GetRole
cp .env.example .env
```

### Avec Docker

Construire l'image, puis générer une clé de chiffrement pour une **nouvelle installation** :

```bash
docker build -t picktag2getrole .
docker run --rm --entrypoint python picktag2getrole -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Renseigner les deux variables obligatoires dans `.env` :

```dotenv
DISCORD_TOKEN=votre_token
ENCRYPTION_KEY=votre_cle_fernet
```

Conserver la clé dans un gestionnaire de secrets, avec une copie de récupération protégée. Pour mettre à jour une installation déjà chiffrée, **garder sa clé existante**.

```bash
docker compose up -d
```

### Sans Docker

```bash
uv sync --locked
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Renseigner `DISCORD_TOKEN` et `ENCRYPTION_KEY` dans `.env`, puis lancer :

```bash
uv run python bot.py
```

## Configuration Discord

1. Créer l'application dans le [Developer Portal](https://discord.com/developers/applications), puis récupérer son token dans **Bot**.
2. Dans **Privileged Gateway Intents**, activer uniquement **SERVER MEMBERS INTENT**. **PRESENCE INTENT** et **MESSAGE CONTENT INTENT** ne sont pas utilisés.
3. Dans **OAuth2 > URL Generator**, sélectionner les scopes `bot` et `applications.commands`, puis la permission **Manage Roles** uniquement.
4. Inviter le bot et placer son rôle au-dessus des rôles qu'il devra gérer.

Exemple de lien d'invitation :

```text
https://discord.com/oauth2/authorize?client_id=VOTRE_CLIENT_ID&permissions=268435456&scope=bot%20applications.commands
```

**Guilds** est également activé dans le code ; il ne s'agit pas d'un intent privilégié. **View Channels**, **Administrator** et les permissions de lecture ou d'envoi de messages ne sont pas nécessaires. Une nouvelle version ne retire pas automatiquement les anciennes permissions déjà accordées au rôle du bot.

Pour les applications concernées par l'examen Discord, demander **Server Members** pour les listes de membres, les nouveaux arrivants et les mises à jour du tag public. La présence en ligne n'est pas nécessaire à cette fonctionnalité.

## Commandes

Les commandes de gestion ci-dessous nécessitent **Manage Roles**, avec une vérification lors de leur exécution. Les réponses sont localisées selon la langue du client Discord : anglais, français, espagnol, allemand, italien ou portugais du Brésil.

| Commande | Fonction |
| --- | --- |
| `/config <tag> <roles>` | Configure le tag exact de ce serveur et les rôles à attribuer. Exemple : `/config tag:VIP roles:@Membre @VIP`. |
| `/status` | Affiche la configuration, le nombre de membres ayant le tag et les éventuels problèmes de permissions ou de configuration. |
| `/toggle` | Active ou désactive la surveillance. |
| `/scan` | Réconcilie les rôles de tous les membres, avec un délai minimal de 60 secondes entre deux demandes. |
| `/check <membre>` | Vérifie l'éligibilité d'un membre selon son tag et son serveur d'origine. |
| `/stats` | Affiche les compteurs journaliers agrégés, avec des comparaisons à 7 et 30 jours. |
| `/reset` | Arrête la surveillance et supprime la configuration et les statistiques du serveur, y compris dans les sauvegardes locales gérées. |

`/help` donne la liste des commandes et les liens vers les politiques. `/botstats`, réservé au propriétaire du bot, affiche son état global : mémoire, latence, intégrité de la base, chiffrement et dernière sauvegarde.

Pour démarrer, exécuter `/config`, vérifier `/status`, puis lancer `/scan`. Le champ `tag` reçoit le texte du tag de serveur, jamais une mention de rôle. Un tag de plus de quatre caractères ou une mention de rôle est refusé. Les rôles configurés doivent être sous celui du bot et sous le rôle le plus élevé de la personne qui configure, sauf si celle-ci possède le serveur.

La désactivation et `/reset` attendent la fin d'une éventuelle modification de rôle déjà engagée, puis empêchent un scan annulé de modifier d'autres rôles ou de recréer des statistiques. **Les rôles déjà attribués restent en place.** Un `/reset` sans configuration permet aussi de supprimer d'éventuelles données résiduelles. Une erreur de suppression doit être corrigée puis la commande relancée.

## Données et confidentialité

La base SQLite `data/bot_data.db` contient la configuration de chaque serveur et des compteurs journaliers agrégés. Elle ne contient ni liste d'utilisateurs ni historique individuel des tags. La bibliothèque Discord reçoit et conserve en mémoire des informations sur les membres nécessaires aux événements et aux opérations de rôles.

`/toggle` arrête le traitement pour le serveur ; il n'empêche pas Discord de livrer des événements ni la bibliothèque de conserver son cache. Il n'existe pas de commande de retrait individuel de ce traitement. Masquer son tag change l'éligibilité aux rôles, sans empêcher les mises à jour de membre. Retirer le bot met fin à son accès au serveur.

La configuration est conservée jusqu'à `/reset` ou au départ du bot. Les statistiques couvrent au plus **365 dates journalières**, aujourd'hui inclus. La purge intervient au démarrage et lors de la maintenance horaire, également dans les sauvegardes locales gérées. Au démarrage, le bot supprime aussi les données des serveurs qu'il a quittés pendant son arrêt. Un marqueur chiffré conserve une demande de suppression inachevée pour permettre les nouvelles tentatives ; il disparaît après réussite.

### Chiffrement obligatoire

`ENCRYPTION_KEY` est obligatoire. Les identifiants de serveur, tags configurés, identifiants de rôles et compteurs sont chiffrés avec Fernet (AES-128-CBC et HMAC-SHA256). L'index de recherche par serveur est un HMAC avec clé, pas l'identifiant Discord en clair.

La structure SQLite, les dates, les horodatages de configuration, l'état d'activation, le nombre de lignes et les index pseudonymes restent visibles. Ce chiffrement des champs ne rend donc pas le fichier entier opaque. La clé doit rester protégée séparément du volume de données.

Les bases existantes et leurs sauvegardes locales gérées sont migrées au démarrage. Une clé absente, malformée ou incompatible, ou une migration incomplète, bloque le démarrage. **Remplacer la variable par une nouvelle clé ne constitue pas une rotation des données existantes.** Sans la clé d'origine, les données chiffrées sont irrécupérables.

### Journaux

Les logs applicatifs contiennent des événements opérationnels et des catégories d'erreur, sans identifiants Discord, noms, tags, rôles ni réponses brutes de l'API. Les logs bruts des dépendances et les détails d'exception sont exclus, même avec `LOG_LEVEL=DEBUG`. Utiliser `/status`, `/check` et `/botstats` pour les diagnostics autorisés dans Discord.

Les anciens fichiers de log et les journaux conservés par l'hébergeur ne sont pas réécrits par une mise à jour. L'opérateur doit supprimer ou faire expirer les journaux historiques contenant des identifiants et définir la rétention des logs de son infrastructure.

Consulter la [Privacy Policy](PRIVACY_POLICY.md) et les [Terms of Service](TERMS_OF_SERVICE.md). Le [suivi GitHub](https://github.com/QTBG/PickTag2GetRole/issues) permet les demandes et questions, mais il est public : ne pas y publier de secrets ou de données privées sur les membres.

## Sauvegardes et restauration

Des sauvegardes SQLite cohérentes sont créées au démarrage puis toutes les 24 heures dans `data/backups/bot_data-YYYYMMDD.db`, après vérification d'intégrité. La rétention limite leur nombre à `BACKUP_KEEP` (7 par défaut) et supprime les fichiers datés d'au moins sept jours avant la date UTC actuelle. Une date de modification plus ancienne peut avancer cette expiration. La maintenance horaire reste active quand `BACKUP_ENABLED=false`, y compris si un nouveau snapshot échoue. Un processus arrêté ne peut pas effectuer de purge ; elle reprend au démarrage.

`/reset` et le départ du bot suppriment les données du serveur dans la base **et dans toutes les sauvegardes locales gérées**, sans supprimer les données des autres serveurs. Les copies manuelles, snapshots de l'hôte et sauvegardes externes sont à gérer séparément par l'opérateur, y compris lors d'une demande de suppression.

Avant une restauration : arrêter le bot, choisir une sauvegarde respectant les suppressions et la rétention, et retrouver sa clé de chiffrement. Exemple pour le volume Docker nommé :

```bash
docker compose down
VOL=$(docker volume ls -q | grep picktag_data | head -1)
MP=$(docker volume inspect -f '{{.Mountpoint}}' "$VOL")
# Vérifier que MP désigne le volume attendu avant de continuer.
sudo cp "$MP/backups/bot_data-AAAAMMJJ.db" "$MP/bot_data.db"
sudo rm -f "$MP/bot_data.db-wal" "$MP/bot_data.db-shm"
sudo chown -R 1000:1000 "$MP"
docker compose up -d
```

Les sauvegardes locales ne protègent pas d'une panne du disque hôte. Pour des sauvegardes externes, appliquer aussi une rétention, un contrôle d'accès et la suppression des données demandée dans le bot.

## Variables d'environnement

| Variable | Rôle |
| --- | --- |
| `DISCORD_TOKEN` | Token Discord obligatoire. |
| `ENCRYPTION_KEY` | Clé Fernet obligatoire, à préserver entre déploiements. |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` ou `ERROR`, défaut `INFO`. |
| `LOG_FILE` | Défaut `bot.log`, rotation à 5 Mo avec trois fichiers de rotation. Une valeur vide active stdout uniquement, comme dans Docker Compose. |
| `CHUNK_ENABLED_GUILDS` | Défaut `true` : charge les membres des serveurs surveillés en cache. `false` économise de la RAM, les membres non mis en cache dépendent davantage des scans. |
| `BACKUP_ENABLED` | Défaut `true` : création quotidienne de snapshots. La rétention et les suppressions restent actives avec `false`. |
| `BACKUP_KEEP` | Nombre maximal de fichiers de sauvegarde, défaut `7`, en complément de la limite d'âge. |
| `MEMORY_LIMIT` / `CPU_LIMIT` | Limites Docker Compose, défauts `512M` et `0.5`. |
| `HEARTBEAT_FILE` | Fichier du contrôle de santé, défaut `/tmp/picktag_heartbeat`. |

## Déploiement avec Dokploy

1. Créer un service **Compose**, provider **GitHub/Git**, dépôt `QTBG/PickTag2GetRole`, branche `main`, Compose Path `./docker-compose.yml`, type **Docker Compose**.
2. Dans **Environment**, définir `DISCORD_TOKEN` et `ENCRYPTION_KEY`. Conserver la clé existante pour une instance déjà chiffrée.
3. Déployer avec **Deploy**. Le volume nommé `picktag_data` persiste entre les déploiements.
4. Vérifier les logs opérationnels puis `/botstats` dans Discord pour l'état de la base, du chiffrement et de la sauvegarde.

Éviter un bind mount relatif `./data:/app/data` avec Dokploy : le répertoire de code peut être recréé au déploiement. Le conteneur utilise l'UID 1000. Pour un ancien dossier hôte créé par un conteneur root, adapter une fois ses permissions avec `sudo chown -R 1000:1000 ./data` après vérification du chemin.

Le contrôle de santé surveille un fichier mis à jour chaque minute tant que la connexion Discord répond. Après cinq minutes sans mise à jour, le conteneur devient `unhealthy`.

```bash
docker compose logs --tail=100
```

## Mise à jour depuis une ancienne version

- Conserver la clé Fernet utilisée en production. Une installation auparavant en clair doit définir une clé avant de démarrer cette version.
- Le schéma de la base et des sauvegardes locales est migré au démarrage. Un retour à l'ancien code seul n'est pas compatible : prévoir une procédure de restauration et conserver la clé, en respectant les demandes de suppression et la rétention des éventuelles copies externes.
- Vérifier que les tags configurés désignent bien le serveur où la commande a été exécutée. Les anciennes correspondances avec un autre serveur ou avec `#` ne sont plus valables ; une réconciliation peut retirer les rôles devenus inéligibles.
- Déployer et vérifier l'attribution et le retrait sur un compte de test. Ensuite, désactiver **Presence Intent** dans le Developer Portal et ne demander que **Server Members** dans le formulaire d'examen.
- Examiner les anciennes permissions d'invitation, les logs historiques et les snapshots externes. La mise à jour ne les révoque ou n'efface pas automatiquement.

## Dépannage

- **Aucun changement de rôle** : vérifier Server Members, la visibilité du tag, son serveur d'origine, la configuration dans `/status` et lancer `/scan`.
- **Permissions insuffisantes** : vérifier **Manage Roles**, la position du rôle du bot et celle des rôles configurés. `/status` donne le nombre de membres qui n'ont pas pu être mis à jour.
- **Configuration invalide** : relancer `/config` avec le tag exact et les mentions de rôles dans le champ `roles`. Le bot suspend les opérations pour une configuration invalide.
- **Démarrage bloqué par la clé** : restaurer la clé d'origine. Ne pas générer une nouvelle clé pour remplacer une clé perdue d'une base déjà chiffrée.
- **Suppression ou migration impossible** : vérifier les permissions du volume et les sauvegardes concernées. Ne pas considérer une commande échouée comme une suppression réussie.
- **Mémoire élevée** : augmenter `MEMORY_LIMIT` ou désactiver le chargement complet avec `CHUNK_ENABLED_GUILDS=false`, au prix d'un recours plus fréquent aux scans.

## Vérification du code

Après `uv sync --locked`, lancer les tests avec :

```bash
uv run python -m unittest discover -s tests -v
```

La CI vérifie Python 3.14, l'installation à partir de `uv.lock`, la construction Docker et les tests dans l'image de production. Les tests utilisent des données fictives ; une vérification Discord sur un compte de test reste nécessaire avant la mise en production.

## Licence

Code sous licence MIT. La publication du code ne constitue pas une certification de conformité ou une approbation par Discord.

---

# PickTag2GetRole (English)

A Discord bot that assigns and removes roles when members display their server's public tag. **Server Members is the only privileged intent**, without Presence or Message Content.

## Behavior

A member qualifies when their server identity is publicly enabled, the source server is the server being monitored, and the tag text matches the configuration, ignoring case. An identical tag from a different server does not qualify. Partial `#` matching is not supported.

Member-update events handle tag changes. Startup, daily and manual `/scan` reconciliation catches missed changes. The bot does not read messages, games or members' online status.

## Installation

Requirements: Docker, or [uv](https://docs.astral.sh/uv/) for a direct installation with Python 3.14. The bot needs **Manage Roles**, with its role above every role it must assign.

```bash
git clone https://github.com/QTBG/PickTag2GetRole.git
cd PickTag2GetRole
cp .env.example .env
```

### With Docker

Build the image and generate an encryption key for a **new installation**:

```bash
docker build -t picktag2getrole .
docker run --rm --entrypoint python picktag2getrole -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set both required variables in `.env`:

```dotenv
DISCORD_TOKEN=your_token
ENCRYPTION_KEY=your_fernet_key
```

Keep the key in a secret store with a protected recovery copy. When updating an encrypted installation, **preserve its existing key**.

```bash
docker compose up -d
```

### Without Docker

```bash
uv sync --locked
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set `DISCORD_TOKEN` and `ENCRYPTION_KEY` in `.env`, then run:

```bash
uv run python bot.py
```

## Discord Setup

1. Create the application in the [Developer Portal](https://discord.com/developers/applications) and obtain its token under **Bot**.
2. Under **Privileged Gateway Intents**, enable **SERVER MEMBERS INTENT** only. **PRESENCE INTENT** and **MESSAGE CONTENT INTENT** are not used.
3. Under **OAuth2 > URL Generator**, select the `bot` and `applications.commands` scopes and the **Manage Roles** permission only.
4. Invite the bot and move its role above those it must manage.

Example invitation:

```text
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=268435456&scope=bot%20applications.commands
```

**Guilds** is also enabled in code; it is not privileged. **View Channels**, **Administrator**, and message-reading or message-sending permissions are not needed. Updating the application does not automatically revoke permissions already granted to an existing bot role.

For applications subject to Discord's review, request **Server Members** for member lists, new arrivals and updates to the public primary guild. Online presence is not required for this functionality.

## Commands

These management commands require **Manage Roles**, checked when each command runs. Responses follow the user's Discord language: English, French, Spanish, German, Italian or Brazilian Portuguese.

| Command | Purpose |
| --- | --- |
| `/config <tag> <roles>` | Configure this server's exact tag and assigned roles. Example: `/config tag:VIP roles:@Member @VIP`. |
| `/status` | Show configuration, tagged-member count and permission or configuration problems. |
| `/toggle` | Enable or disable monitoring. |
| `/scan` | Reconcile all members' roles, with a 60-second request cooldown. |
| `/check <member>` | Check eligibility using the member's tag and source server. |
| `/stats` | Show daily aggregate counts and comparisons over 7 and 30 days. |
| `/reset` | Stop monitoring and delete this server's configuration and statistics, including from managed local backups. |

`/help` lists commands and links to the policies. `/botstats`, restricted to the bot owner, shows memory, latency, database integrity, encryption and last backup status.

Start with `/config`, check `/status`, then run `/scan`. The `tag` field takes the server tag text, never a role mention. Tags longer than four characters and role mentions are rejected. Configured roles must be below the bot's highest role and the caller's highest role, except for the server owner.

Disabling monitoring and `/reset` wait for any role operation already in progress, then prevent a cancelled scan from changing further roles or recreating statistics. **Already assigned roles remain in Discord.** `/reset` also removes residual data when no configuration exists. Resolve deletion errors and retry the command if it fails.

## Data and Privacy

The SQLite database at `data/bot_data.db` contains per-server configuration and daily aggregate counters. It contains no member list or individual tag history. The Discord library receives and caches member information in memory for member events and role operations.

`/toggle` stops processing for the server; it does not prevent Discord from delivering updates or the library from caching members. There is no per-member opt-out command. Hiding a tag changes eligibility without stopping member updates. Removing the bot ends its access to the server.

Configuration is retained until `/reset` or departure cleanup. Statistics cover at most **365 daily dates**, including today. Startup and hourly maintenance purge expired records, including from managed local backups. Startup also removes data for servers the bot left while offline. An encrypted marker records unfinished deletion requests for retry and is removed after successful cleanup.

### Required Encryption

`ENCRYPTION_KEY` is required. Server IDs, configured tags, role IDs and counts are encrypted with Fernet (AES-128-CBC and HMAC-SHA256). Server lookup indexes are keyed HMACs instead of plaintext Discord IDs.

SQLite structure, dates, configuration timestamps, enabled state, row counts and pseudonymous lookup indexes remain visible. Field encryption does not make the entire file opaque. Protect the key separately from the data volume.

Existing databases and managed local backups are migrated at startup. A missing, malformed or incompatible key, or an incomplete migration, prevents startup. **Replacing the variable with a new key does not rotate existing encrypted data.** Without the original key, encrypted data cannot be recovered.

### Logs

Application logs contain operational events and error categories without Discord IDs, names, tags, roles or raw API responses. Raw dependency logs and exception details are excluded even with `LOG_LEVEL=DEBUG`. Use `/status`, `/check` and `/botstats` for authorized diagnostics in Discord.

Updating the bot does not rewrite historical log files or hosting logs. The operator must delete or expire historical logs containing identifiers and define retention for infrastructure logs.

See the [Privacy Policy](PRIVACY_POLICY.md) and [Terms of Service](TERMS_OF_SERVICE.md). Requests and questions can be submitted through [GitHub issues](https://github.com/QTBG/PickTag2GetRole/issues), a public channel: do not post secrets or private member data.

## Backups and Recovery

Consistent SQLite backups are created at startup and every 24 hours in `data/backups/bot_data-YYYYMMDD.db`, after an integrity check. Retention limits the count to `BACKUP_KEEP` (default: 7) and removes files dated seven or more days before the current UTC date. An older modification timestamp can cause earlier expiry. Hourly maintenance continues with `BACKUP_ENABLED=false`, including when a new snapshot fails. A stopped process cannot purge data; maintenance resumes at startup.

`/reset` and departure cleanup delete the server's data from the live database **and every managed local backup**, preserving other servers' data. Manual copies, host snapshots and external backups must be managed separately by the operator, including for deletion requests.

Before restoring, stop the bot, choose a backup that respects deletions and retention, and locate its encryption key. Example for the named Docker volume:

```bash
docker compose down
VOL=$(docker volume ls -q | grep picktag_data | head -1)
MP=$(docker volume inspect -f '{{.Mountpoint}}' "$VOL")
# Confirm that MP points to the intended volume before proceeding.
sudo cp "$MP/backups/bot_data-YYYYMMDD.db" "$MP/bot_data.db"
sudo rm -f "$MP/bot_data.db-wal" "$MP/bot_data.db-shm"
sudo chown -R 1000:1000 "$MP"
docker compose up -d
```

Local snapshots do not protect against host disk failure. External backups also need access controls, retention and enforcement of deletion requests made through the bot.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `DISCORD_TOKEN` | Required Discord token. |
| `ENCRYPTION_KEY` | Required Fernet key, preserved across deployments. |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` or `ERROR`, default `INFO`. |
| `LOG_FILE` | Default `bot.log`, rotation at 5 MB with three rotated files. An empty value enables stdout only, as in Docker Compose. |
| `CHUNK_ENABLED_GUILDS` | Default `true`: cache members of monitored servers. `false` saves memory; uncached members rely more on scans. |
| `BACKUP_ENABLED` | Default `true`: create daily snapshots. Retention and deletion remain active with `false`. |
| `BACKUP_KEEP` | Maximum backup files, default `7`, in addition to the age limit. |
| `MEMORY_LIMIT` / `CPU_LIMIT` | Docker Compose limits, default `512M` and `0.5`. |
| `HEARTBEAT_FILE` | Healthcheck file, default `/tmp/picktag_heartbeat`. |

## Deploying with Dokploy

1. Create a **Compose** service using **GitHub/Git**, repository `QTBG/PickTag2GetRole`, branch `main`, Compose Path `./docker-compose.yml`, type **Docker Compose**.
2. Set `DISCORD_TOKEN` and `ENCRYPTION_KEY` under **Environment**. Preserve the existing key for an encrypted instance.
3. Select **Deploy**. The named `picktag_data` volume persists across deployments.
4. Check operational logs and `/botstats` in Discord for database, encryption and backup status.

Avoid relative bind mounts such as `./data:/app/data` in Dokploy: deployment can recreate the source directory. The container runs as UID 1000. For an old host folder created by a root container, adjust its permissions once with `sudo chown -R 1000:1000 ./data` after checking the path.

The healthcheck watches a file updated every minute while the Discord connection responds. Five minutes without an update makes the container `unhealthy`.

```bash
docker compose logs --tail=100
```

## Upgrading from an Older Release

- Preserve the Fernet key used in production. Previously plaintext installations must set a key before starting this release.
- The database and managed local backups are migrated at startup. Downgrading only the code is not compatible: plan a recovery procedure and preserve the key, while respecting deletion requests and retention for any external recovery copies.
- Verify that configured tags identify the server where the command was run. Previous matches from another source server or partial `#` configurations no longer qualify; reconciliation may remove roles from ineligible members.
- Deploy and verify role addition and removal with a test account. Then disable **Presence Intent** in the Developer Portal and request **Server Members** only in the review form.
- Review historical invitation permissions, logs and external snapshots. Updating the code does not automatically revoke or erase them.

## Troubleshooting

- **Roles do not change**: check Server Members, public tag visibility, source server and `/status`, then run `/scan`.
- **Permission errors**: check **Manage Roles**, the bot's highest role and configured roles. `/status` reports members that could not be updated.
- **Invalid configuration**: run `/config` with the exact tag and role mentions in `roles`. Invalid configurations pause monitoring.
- **Key prevents startup**: restore the original key. Generating a replacement cannot recover an already encrypted database.
- **Deletion or migration fails**: check volume permissions and affected backups. A failed command is not a successful deletion.
- **High memory use**: raise `MEMORY_LIMIT` or set `CHUNK_ENABLED_GUILDS=false`, accepting greater reliance on scans.

## Code Verification

After `uv sync --locked`, run:

```bash
uv run python -m unittest discover -s tests -v
```

CI covers Python 3.14, installation from `uv.lock`, the Docker build and tests inside the production image. Tests use synthetic data; test role changes with a Discord test account before production deployment.

## License

Code under the MIT license. Open-source availability is not a certification of compliance or approval by Discord.
