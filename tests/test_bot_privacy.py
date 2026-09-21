import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


class BotPrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Construire le vrai client sans .env, fichier de donnees ou connexion.
        path = Path(__file__).resolve().parents[1] / 'bot.py'
        spec = importlib.util.spec_from_file_location('bot_privacy_test', path)
        self.module = importlib.util.module_from_spec(spec)
        with patch('dotenv.load_dotenv'), patch('safe_logging.configure_logging'), \
                patch('database.DatabaseManager', return_value=SimpleNamespace()):
            spec.loader.exec_module(self.module)

    async def asyncTearDown(self):
        await self.module.bot.close()

    def test_client_requests_only_guilds_and_members(self):
        self.assertEqual(self.module.bot.intents.value, 3)
        self.assertFalse(self.module.bot.intents.presences)
        self.assertFalse(self.module.bot.intents.message_content)

    async def test_disabling_backups_does_not_disable_retention(self):
        db = SimpleNamespace(maintenance=AsyncMock(), integrity_check=AsyncMock(), backup=AsyncMock())
        bot = SimpleNamespace(db=db, backup_enabled=False, backup_keep=7)
        await self.module.PickTag2GetRole.daily_backup.coro(bot)
        db.maintenance.assert_awaited_once_with(keep=7)
        db.integrity_check.assert_not_awaited()
        db.backup.assert_not_awaited()

    async def test_failed_integrity_still_runs_retention_and_hides_diagnostics(self):
        db = SimpleNamespace(maintenance=AsyncMock(),
            integrity_check=AsyncMock(return_value='private database diagnostic'), backup=AsyncMock())
        bot = SimpleNamespace(db=db, backup_enabled=True, backup_keep=7)
        with self.assertLogs('PickTag2GetRole', level='ERROR') as captured:
            await self.module.PickTag2GetRole.daily_backup.coro(bot)
        db.maintenance.assert_awaited_once_with(keep=7)
        db.backup.assert_not_awaited()
        self.assertEqual(bot.db_integrity, 'failed')
        self.assertNotIn('private database diagnostic', ' '.join(captured.output))

    async def test_maintenance_failure_can_be_retried_without_logging_exception_text(self):
        db = SimpleNamespace(maintenance=AsyncMock(side_effect=[ValueError('private row'), None]))
        bot = SimpleNamespace(db=db, backup_keep=7)
        with self.assertLogs('PickTag2GetRole', level='ERROR') as captured:
            await self.module.PickTag2GetRole.storage_maintenance.coro(bot)
        await self.module.PickTag2GetRole.storage_maintenance.coro(bot)
        self.assertEqual(db.maintenance.await_count, 2)
        self.assertNotIn('private row', ' '.join(captured.output))

    async def test_event_failure_does_not_log_event_payload(self):
        with self.assertLogs('PickTag2GetRole', level='ERROR') as captured:
            await self.module.bot.on_error('on_user_update', 'private profile')
        self.assertNotIn('private profile', ' '.join(captured.output))


if __name__ == '__main__':
    unittest.main()
