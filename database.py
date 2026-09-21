"""Stockage chiffré, migrations et suppression des sauvegardes locales."""
import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import aiosqlite

from crypto import EncryptionKeyError, FieldCipher

logger = logging.getLogger('PickTag2GetRole.Database')

STATS_RETENTION_DAYS = 365  # Nombre exact de dates UTC, aujourd'hui inclus.
BACKUP_RETENTION_DAYS = 7
_KEY_CHECK = 'PickTag2GetRole storage v2'
_BACKUP_NAME = re.compile(r'^bot_data-(\d{8})\.db$')


class StorageMigrationError(RuntimeError):
    """Migration ou vérification incomplète : ne pas démarrer le bot."""


class DatabaseManager:
    def __init__(self, db_path: str = 'data/bot_data.db', cipher: Optional[FieldCipher] = None):
        self.db_path = db_path
        self.cipher = cipher if cipher is not None else FieldCipher()
        self.init_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()

    @property
    def _backup_dir(self) -> Path:
        return Path(self.db_path).parent / 'backups'

    def _backup_files(self, include_tmp=False) -> List[Path]:
        if not self._backup_dir.is_dir():
            return []
        return sorted(
            path for path in self._backup_dir.iterdir()
            if path.is_file() and (
                _BACKUP_NAME.fullmatch(path.name)
                or (include_tmp and path.name.endswith('.db.tmp') and _BACKUP_NAME.fullmatch(path.name[:-4]))
            )
        )

    @staticmethod
    async def _columns(db, table):
        async with db.execute(f'PRAGMA table_info({table})') as cursor:
            return {row[1] for row in await cursor.fetchall()}

    async def _validate_connection(self, db):
        """Valider toutes les données avant toute écriture, y compris les stats."""
        async with db.execute('PRAGMA quick_check') as cursor:
            if [row[0] for row in await cursor.fetchall()] != ['ok']:
                raise StorageMigrationError('Database integrity verification failed.')
        if await self._columns(db, 'storage_metadata'):
            async with db.execute("SELECT value FROM storage_metadata WHERE name = 'key_check'") as cur:
                row = await cur.fetchone()
            if not row or not self.cipher.looks_encrypted(row[0]) or self.cipher.decrypt(row[0]) != _KEY_CHECK:
                raise EncryptionKeyError('Storage key verification failed.')
        for table, fields in (
            ('guild_configs', ('tag_to_watch', 'role_ids')),
            ('tag_stats', ('tagged_count', 'member_count')),
            ('deletion_requests', ()),
        ):
            columns = await self._columns(db, table)
            if not columns:
                continue
            modern = 'guild_id_value' in columns
            if not {'guild_id', *fields}.issubset(columns):
                raise StorageMigrationError('Unsupported storage schema.')
            selected = ['guild_id'] + (['guild_id_value'] if modern else []) + list(fields)
            async with db.execute(f"SELECT {', '.join(selected)} FROM {table}") as cur:
                rows = await cur.fetchall()
            for row in rows:
                decoded = []
                for value in row[1:]:
                    if modern and value is not None and not self.cipher.looks_encrypted(value):
                        raise StorageMigrationError('Unencrypted value in current storage schema.')
                    decoded.append(self.cipher.decrypt(value))
                if modern:
                    if self.cipher.guild_index(int(decoded.pop(0))) != row[0]:
                        raise StorageMigrationError('Stored identifier index verification failed.')
                else:
                    int(row[0])
                if table == 'guild_configs':
                    roles = json.loads(decoded[1]) if decoded[1] else []
                    if not isinstance(roles, list) or any(not isinstance(role, int) for role in roles):
                        raise StorageMigrationError('Invalid stored role configuration.')
                elif table == 'tag_stats':
                    int(decoded[0])
                    int(decoded[1])

    async def _preflight(self, paths):
        disposable = []
        for path in paths:
            try:
                async with aiosqlite.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
                    await self._validate_connection(db)
            except (aiosqlite.DatabaseError, StorageMigrationError):
                # Une copie temporaire interrompue n'est pas restaurable. Une
                # sauvegarde expirée doit être retirée même si elle est abîmée.
                # On attend la validation de TOUS les autres fichiers avant
                # toute suppression ; EncryptionKeyError n'est jamais ignorée.
                if path.name.endswith('.db.tmp') or (
                    path.parent == self._backup_dir and _BACKUP_NAME.fullmatch(path.name)
                    and self._backup_expired(path)
                ):
                    disposable.append(path)
                else:
                    raise
        return disposable

    @staticmethod
    async def _create_tables(db):
        await db.execute('''
            CREATE TABLE IF NOT EXISTS guild_configs (
                guild_id TEXT PRIMARY KEY,
                guild_id_value TEXT NOT NULL,
                tag_to_watch TEXT,
                role_ids TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tag_stats (
                guild_id TEXT NOT NULL,
                guild_id_value TEXT NOT NULL,
                date TEXT NOT NULL,
                tagged_count TEXT NOT NULL,
                member_count TEXT NOT NULL,
                PRIMARY KEY (guild_id, date)
            )
        ''')
        await db.execute('CREATE TABLE IF NOT EXISTS storage_metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL)')
        await db.execute('CREATE TABLE IF NOT EXISTS deletion_requests (guild_id TEXT PRIMARY KEY, guild_id_value TEXT NOT NULL)')

    async def _migrate_file(self, path):
        async with aiosqlite.connect(str(path)) as db:
            await db.execute('PRAGMA busy_timeout=5000')
            await db.execute('PRAGMA secure_delete=ON')
            # Fusionne le WAL avant de réécrire les pages historiques.
            async with db.execute('PRAGMA journal_mode=DELETE') as cur:
                if (await cur.fetchone())[0].lower() != 'delete':
                    raise StorageMigrationError('Cannot safely checkpoint the storage file.')
            await db.execute('BEGIN IMMEDIATE')
            legacy = {}
            try:
                for table in ('guild_configs', 'tag_stats'):
                    columns = await self._columns(db, table)
                    if columns and 'guild_id_value' not in columns:
                        db.row_factory = aiosqlite.Row
                        async with db.execute(f'SELECT * FROM {table}') as cur:
                            legacy[table] = [dict(row) for row in await cur.fetchall()]
                        db.row_factory = None
                        await db.execute(f'DROP TABLE {table}')
                await self._create_tables(db)
                for row in legacy.get('guild_configs', []):
                    guild_id = int(row['guild_id'])
                    await db.execute('''
                        INSERT INTO guild_configs
                        (guild_id, guild_id_value, tag_to_watch, role_ids, enabled, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), COALESCE(?, CURRENT_TIMESTAMP))
                    ''', (
                        self.cipher.guild_index(guild_id), self.cipher.encrypt_int(guild_id),
                        self.cipher.encrypt(self.cipher.decrypt(row['tag_to_watch'])),
                        self.cipher.encrypt(self.cipher.decrypt(row['role_ids']) or '[]'),
                        row.get('enabled', 1), row.get('created_at'), row.get('updated_at'),
                    ))
                for row in legacy.get('tag_stats', []):
                    guild_id = int(row['guild_id'])
                    await db.execute('INSERT INTO tag_stats VALUES (?, ?, ?, ?, ?)', (
                        self.cipher.guild_index(guild_id), self.cipher.encrypt_int(guild_id), row['date'],
                        self.cipher.encrypt_int(int(self.cipher.decrypt(row['tagged_count']))),
                        self.cipher.encrypt_int(int(self.cipher.decrypt(row['member_count']))),
                    ))
                await db.execute('INSERT OR REPLACE INTO storage_metadata VALUES (?, ?)',
                                 ('key_check', self.cipher.encrypt(_KEY_CHECK)))
                await db.commit()
            except BaseException:
                await db.rollback()
                raise
            # Obligatoire : un disque plein ne doit pas autoriser le démarrage
            # avec d'anciennes pages en clair encore récupérables.
            await db.execute('VACUUM')
            await self._validate_connection(db)
        for suffix in ('-wal', '-shm', '-journal'):
            if Path(str(path) + suffix).exists():
                raise StorageMigrationError('Storage journal cleanup is incomplete.')

    async def initialize(self, backup_keep: int = 7):
        async with self.init_lock, self._write_lock:
            main = Path(self.db_path)
            backups = self._backup_files(include_tmp=True)
            disposable = await self._preflight(([main] if main.exists() else []) + backups)
            for path in disposable:
                self._remove_snapshot(path)
            backups = [path for path in backups if path not in disposable]
            main.parent.mkdir(parents=True, exist_ok=True)
            await self._migrate_file(main)
            for path in backups:
                if path.name.endswith('.db.tmp'):
                    self._remove_snapshot(path)
                    continue
                times = path.stat()
                await self._migrate_file(path)
                os.utime(path, ns=(times.st_atime_ns, times.st_mtime_ns))
            await self._complete_pending_deletions()
            self._rotate_backups(backup_keep)
            await self._purge_stats_in_all_files()

    @asynccontextmanager
    async def get_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('PRAGMA busy_timeout=5000')
            await db.execute('PRAGMA secure_delete=ON')
            yield db

    async def get_guild_config(self, guild_id: int) -> Optional[Dict]:
        async with self.get_db() as db:
            async with db.execute('''
                SELECT tag_to_watch, role_ids, enabled FROM guild_configs
                WHERE guild_id = ? AND guild_id NOT IN (SELECT guild_id FROM deletion_requests)
            ''', (self.cipher.guild_index(guild_id),)) as cursor:
                row = await cursor.fetchone()
        return None if row is None else {
            'tag_to_watch': self.cipher.decrypt(row[0]),
            'role_ids': json.loads(self.cipher.decrypt(row[1])), 'enabled': bool(row[2]),
        }

    async def set_guild_config(self, guild_id: int, config: Dict):
        async with self._write_lock, self.get_db() as db:
            async with db.execute('SELECT 1 FROM deletion_requests WHERE guild_id = ?',
                                  (self.cipher.guild_index(guild_id),)) as cur:
                if await cur.fetchone():
                    raise StorageMigrationError('A pending deletion must complete before reconfiguration.')
            await db.execute('''
                INSERT INTO guild_configs (guild_id, guild_id_value, tag_to_watch, role_ids, enabled)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET tag_to_watch=excluded.tag_to_watch,
                    role_ids=excluded.role_ids, enabled=excluded.enabled, updated_at=CURRENT_TIMESTAMP
            ''', (
                self.cipher.guild_index(guild_id), self.cipher.encrypt_int(guild_id),
                self.cipher.encrypt(config.get('tag_to_watch')),
                self.cipher.encrypt(json.dumps(config.get('role_ids', []))),
                int(config.get('enabled', True)),
            ))
            await db.commit()

    async def get_all_guild_ids(self) -> List[int]:
        async with self.get_db() as db:
            async with db.execute('SELECT guild_id_value FROM guild_configs UNION SELECT guild_id_value FROM tag_stats UNION SELECT guild_id_value FROM deletion_requests') as cur:
                return sorted({int(self.cipher.decrypt(row[0])) async for row in cur})

    async def get_all_enabled_configs(self) -> Dict[int, Dict]:
        async with self.get_db() as db:
            async with db.execute('''
                SELECT guild_id_value, tag_to_watch, role_ids FROM guild_configs
                WHERE enabled = 1 AND guild_id NOT IN (SELECT guild_id FROM deletion_requests)
            ''') as cur:
                return {
                    int(self.cipher.decrypt(row[0])): {
                        'tag_to_watch': self.cipher.decrypt(row[1]),
                        'role_ids': json.loads(self.cipher.decrypt(row[2])), 'enabled': True,
                    }
                    async for row in cur
                }

    async def _complete_pending_deletions(self):
        async with self.get_db() as db:
            async with db.execute('SELECT guild_id FROM deletion_requests') as cur:
                pending = [row[0] for row in await cur.fetchall()]
        if not pending:
            return
        # La trace persistante bloque tout rechargement et toute nouvelle stat
        # tant qu'un snapshot local n'a pas pu être purgé. La maintenance retente.
        for path in self._backup_files() + [Path(self.db_path)]:
            async with aiosqlite.connect(str(path)) as db:
                await db.execute('PRAGMA busy_timeout=5000')
                await db.execute('PRAGMA secure_delete=ON')
                for index in pending:
                    await db.execute('DELETE FROM guild_configs WHERE guild_id = ?', (index,))
                    await db.execute('DELETE FROM tag_stats WHERE guild_id = ?', (index,))
                    if path != Path(self.db_path):
                        await db.execute('DELETE FROM deletion_requests WHERE guild_id = ?', (index,))
                await db.commit()
                await db.execute('VACUUM')
        for path in self._backup_files(include_tmp=True):
            if path.name.endswith('.db.tmp'):
                self._remove_snapshot(path)
        # Dernière écriture seulement après nettoyage physique et temporaires.
        # Un crash avant ce commit laisse la demande disponible pour reprise.
        async with self.get_db() as db:
            await db.executemany('DELETE FROM deletion_requests WHERE guild_id = ?',
                                 [(index,) for index in pending])
            await db.commit()

    async def delete_guild_config(self, guild_id: int):
        """Suppression base et snapshots, avec reprise persistante en cas d'échec."""
        async with self._write_lock:
            async with self.get_db() as db:
                await db.execute('INSERT OR REPLACE INTO deletion_requests VALUES (?, ?)',
                                 (self.cipher.guild_index(guild_id), self.cipher.encrypt_int(guild_id)))
                await db.commit()
            await self._complete_pending_deletions()

    @staticmethod
    async def _purge_stats(db):
        await db.execute("DELETE FROM tag_stats WHERE date < date('now', ?) OR date > date('now')",
                         (f'-{STATS_RETENTION_DAYS - 1} days',))
        await db.commit()

    async def _purge_stats_in_all_files(self):
        for path in [Path(self.db_path)] + self._backup_files():
            async with aiosqlite.connect(str(path)) as db:
                await db.execute('PRAGMA secure_delete=ON')
                await self._purge_stats(db)

    async def purge_expired_stats(self):
        async with self._write_lock:
            await self._purge_stats_in_all_files()

    async def record_tag_stat(self, guild_id: int, tagged_count: int, member_count: int):
        async with self._write_lock, self.get_db() as db:
            # Un scan périmé ne doit pas recréer des stats après /reset ou /toggle.
            await db.execute('''
                INSERT OR REPLACE INTO tag_stats (guild_id, guild_id_value, date, tagged_count, member_count)
                SELECT guild_id, guild_id_value, date('now'), ?, ? FROM guild_configs
                WHERE guild_id = ? AND enabled = 1 AND guild_id NOT IN (SELECT guild_id FROM deletion_requests)
            ''', (self.cipher.encrypt_int(tagged_count), self.cipher.encrypt_int(member_count),
                  self.cipher.guild_index(guild_id)))
            await self._purge_stats(db)

    async def get_tag_stats(self, guild_id: int, days: int = 30) -> List[Dict]:
        days = min(STATS_RETENTION_DAYS, max(1, int(days)))
        async with self.get_db() as db:
            async with db.execute('''
                SELECT date, tagged_count, member_count FROM tag_stats
                WHERE guild_id = ? AND date >= date('now', ?) AND date <= date('now')
                    AND guild_id NOT IN (SELECT guild_id FROM deletion_requests) ORDER BY date ASC
            ''', (self.cipher.guild_index(guild_id), f'-{days - 1} days')) as cur:
                return [{'date': row[0], 'tagged': self.cipher.decrypt_int(row[1]),
                         'members': self.cipher.decrypt_int(row[2])} async for row in cur]

    async def integrity_check(self) -> str:
        async with self.get_db() as db:
            async with db.execute('PRAGMA quick_check') as cur:
                results = [row[0] for row in await cur.fetchall()]
                return 'ok' if results == ['ok'] else 'failed'

    @staticmethod
    def _remove_snapshot(path):
        path.unlink(missing_ok=True)
        for suffix in ('-wal', '-shm', '-journal'):
            Path(str(path) + suffix).unlink(missing_ok=True)

    def _rotate_backups(self, keep: int):
        if keep < 1:
            raise ValueError('Backup retention count must be positive.')
        retained = []
        for path in self._backup_files(include_tmp=True):
            if path.name.endswith('.db.tmp'):
                self._remove_snapshot(path)
                continue
            created = self._backup_created(path)
            if self._backup_expired(path):
                self._remove_snapshot(path)
            else:
                retained.append((created, path))
        for _, path in sorted(retained)[:-keep]:
            self._remove_snapshot(path)

    @staticmethod
    def _backup_created(path):
        dated = datetime.strptime(_BACKUP_NAME.fullmatch(path.name)[1], '%Y%m%d').replace(tzinfo=timezone.utc)
        return min(dated, datetime.fromtimestamp(path.stat().st_mtime, timezone.utc))

    def _backup_expired(self, path):
        return datetime.now(timezone.utc) - self._backup_created(path) >= timedelta(days=BACKUP_RETENTION_DAYS)

    async def maintenance(self, keep: int = 7):
        """À appeler même si snapshots/intégrité échouent ou sont désactivés."""
        async with self._write_lock:
            self._rotate_backups(keep)
            await self._complete_pending_deletions()
            await self._purge_stats_in_all_files()

    async def backup(self, keep: int = 7) -> str:
        async with self._write_lock:
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            self._rotate_backups(keep)
            await self._complete_pending_deletions()
            date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
            dest = self._backup_dir / f'bot_data-{date_str}.db'
            tmp = Path(str(dest) + '.tmp')
            try:
                async with self.get_db() as src, aiosqlite.connect(str(tmp)) as dst:
                    await src.backup(dst)
                os.replace(tmp, dest)
            finally:
                self._remove_snapshot(tmp)
                self._rotate_backups(keep)
            return str(dest)
