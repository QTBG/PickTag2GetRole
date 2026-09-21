"""Régressions stockage sur fichiers temporaires, sans données de production."""
import asyncio
import hashlib
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import aiosqlite
from cryptography.fernet import Fernet

from crypto import EncryptionKeyError, FieldCipher
from database import DatabaseManager, STATS_RETENTION_DAYS


GUILD = 1411452026856145057
OTHER = 1411452026856145099
ROLE = 123456789123456789
TAG = 'PRIVATE_TAG_MARKER'


class StoragePrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'bot_data.db'
        self.key = Fernet.generate_key().decode()
        self.cipher = FieldCipher(self.key)
        self.db = DatabaseManager(str(self.path), cipher=self.cipher)

    def backup_path(self, age=0):
        directory = self.root / 'backups'
        directory.mkdir(exist_ok=True)
        day = datetime.now(timezone.utc) - timedelta(days=age)
        return directory / f"bot_data-{day.strftime('%Y%m%d')}.db"

    def legacy(self, path, cipher=None, stats_only=False):
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript('''
                CREATE TABLE guild_configs (guild_id INTEGER PRIMARY KEY, tag_to_watch TEXT,
                    role_ids TEXT, enabled INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT);
                CREATE TABLE tag_stats (guild_id INTEGER, date TEXT, tagged_count INTEGER,
                    member_count INTEGER, PRIMARY KEY(guild_id, date));
            ''')
            encrypt = cipher.encrypt if cipher else lambda value: value
            if not stats_only:
                db.execute('INSERT INTO guild_configs VALUES (?, ?, ?, 1, ?, ?)',
                           (GUILD, encrypt(TAG), encrypt(f'[{ROLE}]'), '2026-01-01', '2026-02-01'))
            # Historiquement une ligne pouvait être partiellement chiffrée.
            db.execute("INSERT INTO tag_stats VALUES (?, date('now'), ?, ?)",
                       (GUILD, encrypt('3'), 42))

    async def configured(self):
        await self.db.initialize()
        await self.db.set_guild_config(GUILD, {'tag_to_watch': TAG, 'role_ids': [ROLE]})
        await self.db.record_tag_stat(GUILD, 3, 42)

    async def test_key_required_and_does_not_create_directories(self):
        with self.assertRaises(EncryptionKeyError):
            FieldCipher('')
        with self.assertRaises(EncryptionKeyError):
            FieldCipher('invalid')
        with patch.dict(os.environ, {'ENCRYPTION_KEY': ''}):
            with self.assertRaises(EncryptionKeyError):
                DatabaseManager(str(self.root / 'absent' / 'db.sqlite'))
        self.assertFalse((self.root / 'absent').exists())

    async def test_legacy_migration_encrypts_ids_values_and_backups(self):
        self.legacy(self.path)
        backup = self.backup_path()
        self.legacy(backup, self.cipher)
        before_mtime = backup.stat().st_mtime_ns
        await self.db.initialize()
        self.assertEqual(before_mtime, backup.stat().st_mtime_ns)
        self.assertEqual((await self.db.get_guild_config(GUILD))['role_ids'], [ROLE])
        self.assertEqual((await self.db.get_tag_stats(GUILD))[0]['tagged'], 3)
        self.assertEqual(await self.db.get_all_guild_ids(), [GUILD])
        for path in (self.path, backup):
            data = path.read_bytes()
            for marker in (TAG.encode(), str(ROLE).encode(), str(GUILD).encode()):
                self.assertNotIn(marker, data)
            with closing(sqlite3.connect(path)) as db, db:
                row = db.execute('SELECT guild_id, guild_id_value, role_ids FROM guild_configs').fetchone()
                self.assertEqual(row[0], self.cipher.guild_index(GUILD))
                self.assertEqual(self.cipher.decrypt(row[1]), str(GUILD))
                self.assertTrue(self.cipher.looks_encrypted(row[2]))
            for suffix in ('-wal', '-shm', '-journal'):
                self.assertFalse(Path(str(path) + suffix).exists())
        # Un deuxième démarrage conserve les valeurs sans double chiffrement.
        await self.db.initialize()
        self.assertEqual((await self.db.get_guild_config(GUILD))['tag_to_watch'], TAG)

    async def test_wrong_key_checks_stats_only_backup_before_any_mutation(self):
        sqlite3.connect(self.path).close()
        backup = self.backup_path()
        self.legacy(backup, self.cipher, stats_only=True)
        originals = {path: path.read_bytes() for path in (self.path, backup)}
        wrong = DatabaseManager(str(self.path), FieldCipher(Fernet.generate_key().decode()))
        with self.assertRaises(EncryptionKeyError):
            await wrong.initialize()
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content)

    async def test_mixed_encryption_keys_fail_before_modifying_either_file(self):
        self.legacy(self.path, self.cipher)
        backup = self.backup_path()
        self.legacy(backup, FieldCipher(Fernet.generate_key().decode()))
        originals = {path: path.read_bytes() for path in (self.path, backup)}
        with self.assertRaises(EncryptionKeyError):
            await self.db.initialize()
        self.assertEqual(originals, {path: path.read_bytes() for path in originals})

    async def test_empty_modern_database_still_rejects_wrong_key(self):
        await self.db.initialize()
        before = hashlib.sha256(self.path.read_bytes()).digest()
        wrong = DatabaseManager(str(self.path), FieldCipher(Fernet.generate_key().decode()))
        with self.assertRaises(EncryptionKeyError):
            await wrong.initialize()
        self.assertEqual(before, hashlib.sha256(self.path.read_bytes()).digest())

    async def test_vacuum_failure_blocks_startup_and_retry_finishes_migration(self):
        self.legacy(self.path)
        original = aiosqlite.Connection.execute

        def execute(connection, sql, *args, **kwargs):
            if sql == 'VACUUM':
                async def fail():
                    raise sqlite3.OperationalError('simulated full disk')
                return fail()
            return original(connection, sql, *args, **kwargs)

        with patch.object(aiosqlite.Connection, 'execute', execute):
            with self.assertRaises(sqlite3.OperationalError):
                await self.db.initialize()
        await self.db.initialize()
        self.assertEqual((await self.db.get_guild_config(GUILD))['tag_to_watch'], TAG)
        self.assertNotIn(TAG.encode(), self.path.read_bytes())

    async def test_deleted_server_cannot_return_from_snapshots_or_stale_stats(self):
        await self.configured()
        await self.db.set_guild_config(OTHER, {'tag_to_watch': 'OTHER', 'role_ids': [8]})
        await self.db.record_tag_stat(OTHER, 2, 5)
        backup = Path(await self.db.backup())
        older = self.backup_path(1)
        shutil.copyfile(backup, older)
        await self.db.delete_guild_config(GUILD)
        await self.db.record_tag_stat(GUILD, 99, 99)
        self.assertIsNone(await self.db.get_guild_config(GUILD))
        self.assertEqual(await self.db.get_tag_stats(GUILD), [])
        self.assertEqual(await self.db.get_all_guild_ids(), [OTHER])
        for path in (backup, older):
            with closing(sqlite3.connect(path)) as db, db:
                self.assertEqual(db.execute('SELECT guild_id FROM guild_configs').fetchall(),
                                 [(self.cipher.guild_index(OTHER),)])
                self.assertEqual(db.execute('SELECT guild_id FROM tag_stats').fetchall(),
                                 [(self.cipher.guild_index(OTHER),)])

    async def test_failed_snapshot_deletion_is_hidden_and_retried(self):
        await self.configured()
        backup = Path(await self.db.backup())
        original = backup.read_bytes()
        backup.write_bytes(b'corrupt snapshot')
        with self.assertRaises(sqlite3.DatabaseError):
            await self.db.delete_guild_config(GUILD)
        self.assertIsNone(await self.db.get_guild_config(GUILD))
        self.assertEqual(await self.db.get_all_enabled_configs(), {})
        self.assertEqual(await self.db.get_tag_stats(GUILD), [])
        await self.db.record_tag_stat(GUILD, 99, 99)
        backup.write_bytes(original)
        await self.db.maintenance()
        self.assertEqual(await self.db.get_all_guild_ids(), [])
        with closing(sqlite3.connect(backup)) as db, db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM guild_configs').fetchone()[0], 0)

    async def test_concurrent_snapshot_reset_and_stale_scan_do_not_resurrect_data(self):
        await self.configured()
        await asyncio.gather(self.db.backup(), self.db.delete_guild_config(GUILD),
                             self.db.record_tag_stat(GUILD, 99, 99))
        self.assertEqual(await self.db.get_all_guild_ids(), [])
        for path in self.db._backup_files():
            with closing(sqlite3.connect(path)) as db, db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM tag_stats').fetchone()[0], 0)

    async def test_retention_is_exact_and_applies_to_inactive_guilds_and_backups(self):
        await self.configured()
        async with self.db.get_db() as db:
            for age in (29, 30, STATS_RETENTION_DAYS - 1, STATS_RETENTION_DAYS):
                await db.execute('INSERT INTO tag_stats VALUES (?, ?, date(\'now\', ?), ?, ?)',
                                 (self.cipher.guild_index(GUILD), self.cipher.encrypt_int(GUILD),
                                  f'-{age} days', self.cipher.encrypt_int(1), self.cipher.encrypt_int(2)))
            await db.execute('UPDATE guild_configs SET enabled = 0')
            await db.commit()
        backup = Path(await self.db.backup())
        self.assertEqual(len(await self.db.get_tag_stats(GUILD, days=30)), 2)
        await self.db.purge_expired_stats()
        for path in (self.path, backup):
            with closing(sqlite3.connect(path)) as db, db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM tag_stats').fetchone()[0], 4)

    async def test_old_backups_expire_without_creating_a_new_snapshot(self):
        await self.configured()
        recent = Path(await self.db.backup())
        expired = self.backup_path(7)
        shutil.copyfile(recent, expired)
        await self.db.maintenance(keep=20)
        self.assertFalse(expired.exists())
        self.assertTrue(recent.exists())

    async def test_backup_count_is_bounded_and_mtime_cannot_extend_age(self):
        await self.configured()
        recent = Path(await self.db.backup())
        for age in (1, 2, 3, 30):
            shutil.copyfile(recent, self.backup_path(age))
        await self.db.maintenance(keep=2)
        self.assertEqual(set(self.db._backup_files()), {recent, self.backup_path(1)})

    async def test_age_rotation_still_runs_if_main_database_is_corrupted(self):
        await self.configured()
        recent = Path(await self.db.backup())
        old = self.backup_path(8)
        shutil.copyfile(recent, old)
        self.path.write_bytes(b'corrupt database')
        with self.assertRaises(sqlite3.DatabaseError):
            await self.db.maintenance()
        self.assertFalse(old.exists())

    async def test_orphan_temporary_snapshot_is_removed(self):
        self.legacy(self.path)
        tmp = Path(str(self.backup_path()) + '.tmp')
        self.legacy(tmp)
        await self.db.initialize()
        self.assertFalse(tmp.exists())

    async def test_tag_that_looks_like_ciphertext_round_trips(self):
        await self.db.initialize()
        await self.db.set_guild_config(GUILD, {'tag_to_watch': 'gAAAAAtag', 'role_ids': [ROLE]})
        self.assertEqual((await self.db.get_guild_config(GUILD))['tag_to_watch'], 'gAAAAAtag')
        await self.db.initialize()
        self.assertEqual((await self.db.get_guild_config(GUILD))['tag_to_watch'], 'gAAAAAtag')

    async def test_deletion_marker_survives_final_vacuum_failure(self):
        await self.configured()
        original = aiosqlite.Connection.execute

        def execute(connection, sql, *args, **kwargs):
            if sql == 'VACUUM':
                async def fail():
                    raise sqlite3.OperationalError('simulated full disk')
                return fail()
            return original(connection, sql, *args, **kwargs)

        with patch.object(aiosqlite.Connection, 'execute', execute):
            with self.assertRaises(sqlite3.OperationalError):
                await self.db.delete_guild_config(GUILD)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM deletion_requests').fetchone()[0], 1)
        await self.db.maintenance()
        self.assertEqual(await self.db.get_all_guild_ids(), [])

    async def test_deletion_marker_survives_temporary_snapshot_cleanup_failure(self):
        await self.configured()
        temporary = Path(str(self.backup_path()) + '.tmp')
        temporary.write_bytes(b'partial snapshot')
        original = self.db._remove_snapshot

        def remove(path):
            if path == temporary:
                raise PermissionError('simulated lock')
            return original(path)

        with patch.object(self.db, '_remove_snapshot', remove):
            with self.assertRaises(PermissionError):
                await self.db.delete_guild_config(GUILD)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM deletion_requests').fetchone()[0], 1)
        await self.db.maintenance()
        self.assertEqual(await self.db.get_all_guild_ids(), [])
        self.assertFalse(temporary.exists())

    async def test_truncated_temporary_and_corrupt_expired_snapshots_do_not_block_startup(self):
        await self.configured()
        temporary = Path(str(self.backup_path()) + '.tmp')
        temporary.write_bytes(b'partial snapshot')
        expired = self.backup_path(8)
        expired.write_bytes(b'corrupt expired snapshot')
        await self.db.initialize()
        self.assertFalse(temporary.exists())
        self.assertFalse(expired.exists())

    async def test_wrong_key_does_not_delete_truncated_or_expired_files(self):
        await self.configured()
        temporary = Path(str(self.backup_path()) + '.tmp')
        temporary.write_bytes(b'partial snapshot')
        expired = self.backup_path(8)
        expired.write_bytes(b'corrupt expired snapshot')
        wrong = DatabaseManager(str(self.path), FieldCipher(Fernet.generate_key().decode()))
        with self.assertRaises(EncryptionKeyError):
            await wrong.initialize()
        self.assertTrue(temporary.exists())
        self.assertTrue(expired.exists())


if __name__ == '__main__':
    unittest.main()

