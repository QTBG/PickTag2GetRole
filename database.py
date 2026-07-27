import json
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
import aiosqlite
from contextlib import asynccontextmanager

from crypto import EncryptionKeyError, FieldCipher

logger = logging.getLogger('PickTag2GetRole.Database')

# Durée de conservation des statistiques agrégées (compteurs journaliers, sans ID utilisateur)
STATS_RETENTION_DAYS = 365

class DatabaseManager:
    def __init__(self, db_path: str = 'data/bot_data.db', cipher: Optional[FieldCipher] = None):
        # Créer le répertoire data s'il n'existe pas
        data_dir = os.path.dirname(db_path)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)

        self.db_path = db_path
        self.init_lock = asyncio.Lock()
        # Chiffrement au repos des valeurs stockées (identifiants de clé exclus)
        self.cipher = cipher if cipher is not None else FieldCipher()

    async def initialize(self):
        """Initialize the database with required tables"""
        async with self.init_lock:
            async with aiosqlite.connect(self.db_path) as db:
                # WAL : écritures moins coûteuses et lectures non bloquantes
                # (propriété persistante du fichier, définie une seule fois)
                await db.execute('PRAGMA journal_mode=WAL')
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS guild_configs (
                        guild_id INTEGER PRIMARY KEY,
                        tag_to_watch TEXT,
                        role_ids TEXT,
                        enabled INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                # Statistiques agrégées : un compteur par serveur et par jour, aucun ID utilisateur
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS tag_stats (
                        guild_id INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        tagged_count INTEGER NOT NULL,
                        member_count INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (guild_id, date)
                    )
                ''')
                await db.commit()

        if self.cipher.enabled:
            # Ordre critique : vérifier la clé AVANT toute écriture. Avec une
            # mauvaise clé, migrer quoi que ce soit mélangerait deux clés dans
            # la base et la rendrait illisible sous chacune d'elles.
            await self._ensure_key_matches()
            await self._encrypt_existing_rows()
            await self._encrypt_backup_files()
        # Hygiène non critique : ne jamais empêcher le démarrage pour ça
        try:
            await self._sweep_backup_tmp()
            await self.purge_expired_stats()
        except Exception as e:
            logger.error("Non-fatal maintenance error at startup: %s", e)

    async def _sweep_backup_tmp(self):
        """Supprimer les fichiers temporaires de sauvegarde orphelins.

        backup() écrit un .tmp puis le renomme ; un conteneur tué en pleine
        copie (redéploiement Dokploy, OOM) peut le laisser derrière lui. Un
        .tmp échappe au filtre *.db du chiffrement des sauvegardes ET de la
        rotation : il garderait les données en clair indéfiniment. backup()
        étant le seul écrivain et séquentiel, tout .tmp rencontré ici est
        orphelin.
        """
        backup_dir = os.path.join(os.path.dirname(self.db_path) or '.', 'backups')
        if not os.path.isdir(backup_dir):
            return
        for name in os.listdir(backup_dir):
            if name.endswith('.db.tmp'):
                try:
                    os.remove(os.path.join(backup_dir, name))
                    logger.info("Removed orphaned backup temp file: %s", name)
                except OSError as e:
                    logger.warning("Could not remove orphaned temp file %s: %s", name, e)

    async def purge_expired_stats(self):
        """Purge globale des statistiques au-delà de la rétention promise.

        record_tag_stat purge déjà au fil de l'eau, mais uniquement pour les
        serveurs activement scannés : un serveur désactivé (/toggle) ou en
        pause garderait ses compteurs au-delà des 365 jours annoncés par la
        politique de confidentialité.
        """
        async with self.get_db() as db:
            cur = await db.execute(
                "DELETE FROM tag_stats WHERE date < date('now', ?)",
                (f'-{STATS_RETENTION_DAYS} days',)
            )
            await db.commit()
            if cur.rowcount:
                logger.info("Purged %s stat row(s) older than %s days",
                            cur.rowcount, STATS_RETENTION_DAYS)

    async def get_all_guild_ids(self) -> List[int]:
        """Tous les guild_id présents en base (configurations et statistiques)."""
        async with self.get_db() as db:
            async with db.execute(
                'SELECT guild_id FROM guild_configs UNION SELECT guild_id FROM tag_stats'
            ) as cursor:
                return [row[0] async for row in cursor]

    async def _ensure_key_matches(self):
        """Refuser de continuer si la clé ne déchiffre aucune valeur déjà chiffrée.

        Une ligne isolée illisible au milieu de lignes saines n'est pas un
        problème de clé (elle sera signalée au chargement) ; c'est l'échec de
        TOUTES les lignes chiffrées qui signe une mauvaise clé. Une base sans
        aucune ligne chiffrée (première activation) ne prouve rien et passe.
        """
        readable = 0
        unreadable = 0
        async with self.get_db() as db:
            async with db.execute('SELECT tag_to_watch, role_ids FROM guild_configs') as cur:
                async for tag, role_ids in cur:
                    for value in (tag, role_ids):
                        if not self.cipher.looks_encrypted(value):
                            continue
                        try:
                            self.cipher.decrypt(value)
                            readable += 1
                        except EncryptionKeyError:
                            unreadable += 1
        if unreadable and not readable:
            raise EncryptionKeyError(
                "ENCRYPTION_KEY does not decrypt any of the encrypted values already "
                "stored in this database. Restore the key that was used to write it — "
                "the bot refuses to start rather than run with unreadable data."
            )

    async def _encrypt_rows_in(self, db) -> int:
        """Chiffrer les valeurs en clair d'une connexion donnée (sans commit).

        Idempotent : une valeur déjà chiffrée est reconnue à son préfixe et ignorée.
        """
        migrated = 0
        async with db.execute('SELECT guild_id, tag_to_watch, role_ids FROM guild_configs') as cur:
            rows = await cur.fetchall()
        for guild_id, tag, role_ids in rows:
            if self.cipher.looks_encrypted(tag) and self.cipher.looks_encrypted(role_ids):
                continue
            await db.execute(
                'UPDATE guild_configs SET tag_to_watch = ?, role_ids = ? WHERE guild_id = ?',
                (self.cipher.encrypt(tag), self.cipher.encrypt(role_ids), guild_id)
            )
            migrated += 1

        async with db.execute('SELECT guild_id, date, tagged_count, member_count FROM tag_stats') as cur:
            stat_rows = await cur.fetchall()
        for guild_id, date_str, tagged, members in stat_rows:
            if self.cipher.looks_encrypted(tagged) and self.cipher.looks_encrypted(members):
                continue
            await db.execute(
                'UPDATE tag_stats SET tagged_count = ?, member_count = ? WHERE guild_id = ? AND date = ?',
                (self.cipher.encrypt_int(int(tagged)), self.cipher.encrypt_int(int(members)),
                 guild_id, date_str)
            )
            migrated += 1
        return migrated

    async def _encrypt_existing_rows(self):
        """Chiffrer les valeurs écrites avant l'activation du chiffrement."""
        async with self.get_db() as db:
            migrated = await self._encrypt_rows_in(db)
            if migrated:
                await db.commit()
                logger.info("Encryption at rest: migrated %s plaintext row(s)", migrated)
            # VACUUM systématique : la migration en place (celle-ci ou une
            # précédente) laisse les anciennes valeurs en clair dans les pages
            # libres du fichier, récupérables sans la clé par simple carving.
            # VACUUM réécrit le fichier sans ces résidus ; quelques ms sur une
            # base de cette taille. Non fatal : sur disque plein (VACUUM copie
            # la base), mieux vaut démarrer sans purger les résidus que
            # crash-looper — retentera au prochain démarrage.
            try:
                await db.execute('VACUUM')
            except Exception as e:
                logger.warning("VACUUM failed (non-fatal, will retry next start): %s", e)

    async def _encrypt_backup_files(self):
        """Appliquer la même migration aux sauvegardes existantes.

        Les snapshots pris avant l'activation de la clé restent en clair sur le
        même volume jusqu'à leur rotation (7 jours par défaut) — précisément ce
        que le chiffrement au repos promet d'empêcher. N'est exécuté qu'après
        _ensure_key_matches : chiffrer une sauvegarde sous une mauvaise clé
        détruirait la dernière copie lisible des données.
        """
        backup_dir = os.path.join(os.path.dirname(self.db_path) or '.', 'backups')
        if not os.path.isdir(backup_dir):
            return
        for name in sorted(os.listdir(backup_dir)):
            if not (name.startswith('bot_data-') and name.endswith('.db')):
                continue
            path = os.path.join(backup_dir, name)
            try:
                async with aiosqlite.connect(path) as db:
                    migrated = await self._encrypt_rows_in(db)
                    if migrated:
                        await db.commit()
                        logger.info("Encryption at rest: migrated %s plaintext row(s) in backup %s",
                                    migrated, name)
                    # Même raison que pour la base principale : purger les
                    # résidus en clair des pages libres du fichier
                    await db.execute('VACUUM')
            except Exception as e:
                logger.error("Could not encrypt backup %s: %s", name, e)
    
    @asynccontextmanager
    async def get_db(self):
        """Get a database connection"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('PRAGMA busy_timeout=5000')
            # Écraser physiquement les données supprimées ou remplacées :
            # /reset et la purge des stats promettent une vraie suppression
            await db.execute('PRAGMA secure_delete=ON')
            yield db
    
    async def get_guild_config(self, guild_id: int) -> Optional[Dict]:
        """Get configuration for a specific guild"""
        async with self.get_db() as db:
            async with db.execute(
                'SELECT tag_to_watch, role_ids, enabled FROM guild_configs WHERE guild_id = ?',
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    tag = self.cipher.decrypt(row[0])
                    role_ids = self.cipher.decrypt(row[1])
                    return {
                        'tag_to_watch': tag,
                        'role_ids': json.loads(role_ids) if role_ids else [],
                        'enabled': bool(row[2])
                    }
                return None
    
    async def set_guild_config(self, guild_id: int, config: Dict):
        """Set configuration for a specific guild"""
        async with self.get_db() as db:
            role_ids_json = json.dumps(config.get('role_ids', []))
            
            await db.execute('''
                INSERT OR REPLACE INTO guild_configs 
                (guild_id, tag_to_watch, role_ids, enabled, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                guild_id,
                self.cipher.encrypt(config.get('tag_to_watch')),
                self.cipher.encrypt(role_ids_json),
                int(config.get('enabled', True))
            ))
            await db.commit()
    
    async def delete_guild_config(self, guild_id: int):
        """Delete configuration and statistics for a specific guild"""
        async with self.get_db() as db:
            await db.execute('DELETE FROM guild_configs WHERE guild_id = ?', (guild_id,))
            await db.execute('DELETE FROM tag_stats WHERE guild_id = ?', (guild_id,))
            await db.commit()

    async def record_tag_stat(self, guild_id: int, tagged_count: int, member_count: int):
        """Record today's aggregated counters for a guild (one row per guild per day)"""
        async with self.get_db() as db:
            await db.execute('''
                INSERT OR REPLACE INTO tag_stats (guild_id, date, tagged_count, member_count)
                VALUES (?, date('now'), ?, ?)
            ''', (guild_id,
                  self.cipher.encrypt_int(tagged_count),
                  self.cipher.encrypt_int(member_count)))
            # Purge au fil de l'eau pour borner l'espace disque
            await db.execute(
                "DELETE FROM tag_stats WHERE guild_id = ? AND date < date('now', ?)",
                (guild_id, f'-{STATS_RETENTION_DAYS} days')
            )
            await db.commit()

    async def get_tag_stats(self, guild_id: int, days: int = 30) -> List[Dict]:
        """Get daily aggregated counters for a guild, oldest first"""
        async with self.get_db() as db:
            async with db.execute(
                "SELECT date, tagged_count, member_count FROM tag_stats "
                "WHERE guild_id = ? AND date >= date('now', ?) ORDER BY date ASC",
                (guild_id, f'-{days} days')
            ) as cursor:
                return [
                    {
                        'date': row[0],
                        'tagged': self.cipher.decrypt_int(row[1]),
                        'members': self.cipher.decrypt_int(row[2]),
                    }
                    async for row in cursor
                ]

    async def integrity_check(self) -> str:
        """Run PRAGMA quick_check on the database ('ok' means healthy)"""
        async with self.get_db() as db:
            async with db.execute('PRAGMA quick_check') as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 'unknown'

    async def backup(self, keep: int = 7) -> str:
        """Write a consistent snapshot of the database, one file per UTC day.

        Utilise l'API de sauvegarde en ligne de SQLite : le snapshot est cohérent
        même si le bot écrit en même temps (un simple `cp` ne l'est pas, surtout
        en mode WAL). Écriture atomique via un fichier temporaire, puis rotation :
        seuls les `keep` fichiers les plus récents sont conservés.
        """
        backup_dir = os.path.join(os.path.dirname(self.db_path) or '.', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        # Nettoyer un éventuel .tmp orphelin d'une exécution tuée en route
        # (couvre aussi les conteneurs qui tournent plusieurs jours sans redémarrer)
        await self._sweep_backup_tmp()

        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
        dest = os.path.join(backup_dir, f'bot_data-{date_str}.db')
        tmp = dest + '.tmp'

        try:
            async with aiosqlite.connect(self.db_path) as src:
                async with aiosqlite.connect(tmp) as dst:
                    await src.backup(dst)
            os.replace(tmp, dest)
        finally:
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass

        if keep > 0:
            existing = sorted(
                name for name in os.listdir(backup_dir)
                if name.startswith('bot_data-') and name.endswith('.db')
            )
            for old_name in existing[:-keep]:
                try:
                    os.remove(os.path.join(backup_dir, old_name))
                except OSError:
                    pass

        return dest
    
    async def get_all_enabled_configs(self) -> Dict[int, Dict]:
        """Get all enabled configurations (for monitoring).

        Une ligne illisible (jeton corrompu, ou écrit sous une autre clé pendant
        un incident) est ignorée et signalée, au lieu de faire échouer le
        chargement de tous les autres serveurs. Si AUCUNE ligne n'est
        déchiffrable, c'est la clé qui est en cause : on lève plutôt que de
        laisser le bot tourner avec un cache vide.
        """
        configs: Dict[int, Dict] = {}
        key_failures = []
        parse_failures = []
        async with self.get_db() as db:
            async with db.execute(
                'SELECT guild_id, tag_to_watch, role_ids FROM guild_configs WHERE enabled = 1'
            ) as cursor:
                async for row in cursor:
                    try:
                        role_ids = self.cipher.decrypt(row[2])
                        configs[row[0]] = {
                            'tag_to_watch': self.cipher.decrypt(row[1]),
                            'role_ids': json.loads(role_ids) if role_ids else [],
                            'enabled': True
                        }
                    except EncryptionKeyError:
                        key_failures.append(row[0])
                    except (ValueError, TypeError):
                        parse_failures.append(row[0])

        if key_failures and not configs:
            raise EncryptionKeyError(
                "None of the stored configurations can be decrypted with the current "
                "ENCRYPTION_KEY. Restore the key that was used to write this database."
            )
        if key_failures:
            logger.error(
                "Skipping %s guild config(s) that cannot be decrypted with the current key "
                "(guild_ids: %s) — these guilds are unmonitored until reconfigured with /config",
                len(key_failures), key_failures
            )
        if parse_failures:
            logger.error(
                "Skipping %s guild config(s) with unparseable role_ids (guild_ids: %s)",
                len(parse_failures), parse_failures
            )
        return configs