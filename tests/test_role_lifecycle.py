"""Régressions du suivi des rôles, sans connexion Discord ni données réelles."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

import discord
from discord import app_commands
from discord.state import ConnectionState

from cogs.commands import ConfigCommands
from cogs.tag_monitor import TagMonitor


class FakeRole:
    def __init__(self, role_id=42, position=1):
        self.id = role_id
        self.position = position
        self.managed = False

    def is_default(self):
        return False

    def __lt__(self, other):
        return self.position < other.position


class FakeMember:
    def __init__(self, guild, member_id=100, tag='TEST', source=None):
        self.guild = guild
        self.id = member_id
        self.primary_guild = SimpleNamespace(
            id=guild.id if source is None else source,
            tag=tag, identity_enabled=True,
        )
        self.roles = []
        self.changes = []
        self.request_started = None
        self.request_release = None

    async def add_roles(self, *roles, reason):
        if self.request_started:
            self.request_started.set()
            await self.request_release.wait()
        self.roles.extend(role for role in roles if role not in self.roles)
        self.changes.append('add')

    async def remove_roles(self, *roles, reason):
        self.roles = [role for role in self.roles if role not in roles]
        self.changes.append('remove')


class FakeGuild:
    def __init__(self, guild_id=1):
        self.id = guild_id
        self.members = []
        self.role = FakeRole()
        self.chunked = True
        self.me = SimpleNamespace(
            guild_permissions=SimpleNamespace(manage_roles=True),
            top_role=FakeRole(43, position=10),
        )
        self.chunk_started = asyncio.Event()
        self.chunk_release = asyncio.Event()

    def get_member(self, member_id):
        return next((m for m in self.members if m.id == member_id), None)

    def get_role(self, role_id):
        return self.role if role_id == self.role.id else None

    async def chunk(self, *, cache):
        self.chunk_started.set()
        await self.chunk_release.wait()
        self.chunked = True


class FakeDB:
    def __init__(self, config):
        self.config = dict(config)
        self.stats = {}
        self.delete_calls = 0
        self.fail_delete = False

    async def record_tag_stat(self, guild_id, tagged, checked):
        self.stats[guild_id] = (tagged, checked)

    async def delete_guild_config(self, guild_id):
        self.delete_calls += 1
        self.config = None
        if self.fail_delete:
            raise OSError('synthetic failure')
        self.stats.pop(guild_id, None)


class FakeBot:
    def __init__(self, guild):
        config = {'tag_to_watch': 'TEST', 'role_ids': [guild.role.id], 'enabled': True}
        self.guilds = [guild]
        self.config_cache = {guild.id: dict(config)}
        self.cache_lock = asyncio.Lock()
        self.db = FakeDB(config)
        self.monitor = TagMonitor(self)

    def get_guild(self, guild_id):
        return next((g for g in self.guilds if g.id == guild_id), None)

    def get_guild_config_cached(self, guild_id):
        return self.config_cache.get(guild_id)

    async def get_guild_config(self, guild_id):
        return dict(self.db.config) if self.db.config else None

    async def set_guild_config(self, guild_id, config):
        self.db.config = dict(config)
        if config['enabled']:
            self.config_cache[guild_id] = dict(config)
        else:
            self.config_cache.pop(guild_id, None)

    def get_cog(self, name):
        return self.monitor if name == 'TagMonitor' else None


def interaction_for(guild):
    return SimpleNamespace(
        guild=guild, guild_id=guild.id, locale=discord.Locale.american_english,
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        permissions=discord.Permissions.none(),
        created_at=datetime.now(timezone.utc),
    )


class RoleLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.guild = FakeGuild()
        self.member = FakeMember(self.guild)
        self.guild.members.append(self.member)
        self.bot = FakeBot(self.guild)
        self.monitor = self.bot.monitor
        self.commands = ConfigCommands(self.bot)

    async def scan(self):
        return await self.monitor.scan_guild(self.guild, 'TEST', [self.guild.role.id])

    async def test_strict_source_identity_and_exact_tag(self):
        self.assertTrue(self.monitor._member_has_tag(self.member, 'test'))
        self.member.primary_guild.id = 2
        self.assertFalse(self.monitor._member_has_tag(self.member, 'TEST'))
        self.member.primary_guild.id = self.guild.id
        self.member.primary_guild.identity_enabled = False
        self.assertFalse(self.monitor._member_has_tag(self.member, 'TEST'))
        self.member.primary_guild.identity_enabled = True
        self.member.primary_guild.tag = 'A#B'
        self.assertFalse(self.monitor._member_has_tag(self.member, '#B'))

    async def test_user_updates_add_and_remove_without_presence_listener(self):
        self.assertFalse(hasattr(self.monitor, 'on_presence_update'))
        before = SimpleNamespace(primary_guild=None)
        after = SimpleNamespace(id=self.member.id, primary_guild=self.member.primary_guild)
        await self.monitor.on_user_update(before, after)
        self.assertEqual(self.member.changes, ['add'])
        before = after
        self.member.primary_guild = None
        after = SimpleNamespace(id=self.member.id, primary_guild=None)
        await self.monitor.on_user_update(before, after)
        self.assertEqual(self.member.changes, ['add', 'remove'])

    async def test_reset_waits_for_inflight_role_and_stops_remaining_members(self):
        second = FakeMember(self.guild, 101)
        self.guild.members.append(second)
        self.member.request_started = asyncio.Event()
        self.member.request_release = asyncio.Event()
        scan = asyncio.create_task(self.scan())
        await self.member.request_started.wait()
        reset = asyncio.create_task(self.monitor.delete_guild_data(self.guild.id))
        await asyncio.sleep(0)
        self.assertFalse(reset.done())
        self.member.request_release.set()
        await reset
        self.assertTrue((await scan)['cancelled'])
        self.assertEqual(self.member.changes, ['add'])
        self.assertEqual(second.changes, [])
        self.assertEqual(self.bot.db.stats, {})
        self.assertNotIn(self.guild.id, self.monitor.member_cache)
        self.assertNotIn(self.guild.id, self.bot.config_cache)

    async def test_reset_during_chunk_does_not_recreate_stats_or_roles(self):
        self.guild.chunked = False
        scan = asyncio.create_task(self.scan())
        await self.guild.chunk_started.wait()
        await self.monitor.delete_guild_data(self.guild.id)
        self.guild.chunk_release.set()
        self.assertTrue((await scan)['cancelled'])
        self.assertEqual(self.member.changes, [])
        self.assertEqual(self.bot.db.stats, {})

    async def test_reset_command_removes_orphan_stats_even_without_config(self):
        self.bot.db.config = None
        self.bot.config_cache.clear()
        self.bot.db.stats[self.guild.id] = (2, 3)
        interaction = interaction_for(self.guild)
        await self.commands.reset.callback(self.commands, interaction)
        await self.commands.reset.callback(self.commands, interaction)
        self.assertEqual(self.bot.db.stats, {})
        self.assertEqual(self.bot.db.delete_calls, 2)
        self.assertEqual(interaction.followup.send.await_count, 2)

    async def test_reset_failure_stops_monitoring_and_does_not_report_success(self):
        self.bot.db.fail_delete = True
        interaction = interaction_for(self.guild)
        with self.assertRaises(OSError):
            await self.commands.reset.callback(self.commands, interaction)
        self.assertNotIn(self.guild.id, self.bot.config_cache)
        interaction.followup.send.assert_not_awaited()
        await self.monitor.on_member_join(self.member)
        self.assertEqual(self.member.changes, [])

    async def test_toggle_command_cancels_scan_and_prevents_event_writes(self):
        self.guild.chunked = False
        scan = asyncio.create_task(self.scan())
        await self.guild.chunk_started.wait()
        await self.commands.toggle.callback(self.commands, interaction_for(self.guild))
        self.guild.chunk_release.set()
        self.assertTrue((await scan)['cancelled'])
        await self.monitor.on_member_join(self.member)
        self.assertEqual(self.member.changes, [])
        self.assertEqual(self.bot.db.stats, {})
        self.assertFalse(self.bot.db.config['enabled'])

    async def test_toggle_refresh_failure_leaves_monitoring_suspended(self):
        async def write_then_fail_refresh(guild_id, config):
            self.bot.db.config = dict(config)
            raise OSError('synthetic refresh failure')

        self.bot.set_guild_config = write_then_fail_refresh
        interaction = interaction_for(self.guild)
        with self.assertRaises(OSError):
            await self.commands.toggle.callback(self.commands, interaction)
        self.assertFalse(self.bot.db.config['enabled'])
        self.assertNotIn(self.guild.id, self.bot.config_cache)
        interaction.followup.send.assert_not_awaited()
        await self.monitor.on_member_join(self.member)
        self.assertEqual(self.member.changes, [])

    async def test_reset_while_chunking_prevents_first_rest_fallback_request(self):
        self.guild.chunked = False

        async def incomplete_chunk(*, cache):
            self.guild.chunk_started.set()
            await self.guild.chunk_release.wait()

        fetches = []

        async def pages(*, limit):
            fetches.append('first')
            yield self.member

        self.guild.chunk = incomplete_chunk
        self.guild.fetch_members = pages
        scan = asyncio.create_task(self.scan())
        await self.guild.chunk_started.wait()
        await self.monitor.delete_guild_data(self.guild.id)
        self.guild.chunk_release.set()
        self.assertTrue((await scan)['cancelled'])
        self.assertEqual(fetches, [])

    async def test_reset_during_rest_scan_prevents_next_page_request(self):
        self.guild.chunked = False
        self.monitor.chunking_enabled = False
        self.member.request_started = asyncio.Event()
        self.member.request_release = asyncio.Event()
        second = FakeMember(self.guild, 101)
        self.guild.members.append(second)
        fetches = []

        async def pages(*, limit):
            fetches.append('first')
            yield self.member
            fetches.append('second')
            yield second

        self.guild.fetch_members = pages
        scan = asyncio.create_task(self.scan())
        await self.member.request_started.wait()
        reset = asyncio.create_task(self.monitor.delete_guild_data(self.guild.id))
        await asyncio.sleep(0)
        self.member.request_release.set()
        await reset
        self.assertTrue((await scan)['cancelled'])
        self.assertEqual(fetches, ['first'])
        self.assertEqual(second.changes, [])
        self.assertEqual(self.bot.db.stats, {})

    async def test_reconfiguration_invalidates_old_scan_even_when_values_identical(self):
        self.guild.chunked = False
        scan = asyncio.create_task(self.scan())
        await self.guild.chunk_started.wait()
        async with self.monitor.configuration_change(self.guild.id):
            await self.bot.set_guild_config(self.guild.id, dict(self.bot.db.config))
        self.guild.chunk_release.set()
        self.assertTrue((await scan)['cancelled'])
        self.assertEqual(self.member.changes, [])
        self.assertEqual(self.bot.db.stats, {})

    async def test_queued_event_rechecks_config_after_reset(self):
        lock = self.monitor._get_state_lock(self.guild.id)
        await lock.acquire()
        reset = asyncio.create_task(self.monitor.delete_guild_data(self.guild.id))
        await asyncio.sleep(0)
        event = asyncio.create_task(self.monitor.on_member_join(self.member))
        await asyncio.sleep(0)
        lock.release()
        await asyncio.gather(reset, event)
        self.assertEqual(self.member.changes, [])

    async def test_departed_guild_does_not_receive_roles_from_pending_scan(self):
        self.guild.chunked = False
        scan = asyncio.create_task(self.scan())
        await self.guild.chunk_started.wait()
        self.bot.guilds.clear()
        await self.monitor.delete_guild_data(self.guild.id)
        self.guild.chunk_release.set()
        self.assertTrue((await scan)['cancelled'])
        self.assertEqual(self.member.changes, [])
        self.assertEqual(self.bot.db.stats, {})

    async def test_scan_counts_members_and_removes_colliding_server_tag_role(self):
        impostor = FakeMember(self.guild, 101, source=2)
        impostor.roles = [self.guild.role]
        self.guild.members.append(impostor)
        stats = await self.scan()
        self.assertEqual(stats, {'checked': 2, 'tagged': 1, 'updated': 2})
        self.assertEqual(impostor.changes, ['remove'])
        self.assertEqual(self.bot.db.stats[self.guild.id], (1, 2))

    async def test_events_update_shared_scan_count_after_member_was_visited(self):
        second = FakeMember(self.guild, 101)
        second.request_started = asyncio.Event()
        second.request_release = asyncio.Event()
        self.guild.members.append(second)
        scan = asyncio.create_task(self.scan())
        await second.request_started.wait()
        before = SimpleNamespace(primary_guild=self.member.primary_guild)
        self.member.primary_guild = None
        event = asyncio.create_task(self.monitor.on_user_update(
            before, SimpleNamespace(id=self.member.id, primary_guild=None)))
        await asyncio.sleep(0)
        second.request_release.set()
        await event
        stats = await scan
        self.assertEqual(stats['tagged'], 1)
        self.assertEqual(self.monitor.member_cache[self.guild.id], {second.id})
        self.assertEqual(self.member.changes, ['add', 'remove'])

    async def test_real_gateway_member_payload_updates_shared_user_without_presence(self):
        dispatched = []
        http = SimpleNamespace(add_role=AsyncMock(), remove_role=AsyncMock())
        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = True
        state = ConnectionState(
            dispatch=lambda *event: dispatched.append(event), handlers={}, hooks={},
            http=http, intents=intents,
        )
        bot_user = {'id': '900', 'username': 'test-bot', 'discriminator': '0',
                    'avatar': None, 'bot': True}
        state.user = discord.ClientUser(state=state, data=bot_user)
        user = {'id': '100', 'username': 'test-user', 'discriminator': '0',
                'avatar': None, 'primary_guild': None}

        def make_guild(guild_id, role_id, has_role=False):
            return discord.Guild(state=state, data={
                'id': str(guild_id), 'name': 'synthetic', 'member_count': 2,
                'roles': [
                    {'id': str(guild_id), 'name': '@everyone', 'position': 0,
                     'permissions': '0'},
                    {'id': str(role_id), 'name': 'reward', 'position': 1,
                     'permissions': '0'},
                    {'id': str(role_id + 1), 'name': 'bot', 'position': 5,
                     'permissions': str(discord.Permissions(manage_roles=True).value)},
                ],
                'members': [
                    {'user': bot_user, 'roles': [str(role_id + 1)], 'flags': 0},
                    {'user': user, 'roles': [str(role_id)] if has_role else [], 'flags': 0},
                ],
            })

        own = make_guild(1, 42)
        foreign = make_guild(2, 142, has_role=True)
        for guild in (own, foreign):
            state._add_guild(guild)
        cache = {
            own.id: {'enabled': True, 'tag_to_watch': 'TEST', 'role_ids': [42]},
            foreign.id: {'enabled': True, 'tag_to_watch': 'TEST', 'role_ids': [142]},
        }
        bot = SimpleNamespace(
            guilds=[own, foreign], get_guild=state._get_guild,
            get_guild_config_cached=cache.get,
        )
        monitor = TagMonitor(bot)
        self.assertFalse(state._intents.presences)
        self.assertIs(own.get_member(100)._user, foreign.get_member(100)._user)

        async def parse(primary_guild, roles):
            dispatched.clear()
            state.parse_guild_member_update({
                'guild_id': '1', 'user': dict(user, primary_guild=primary_guild),
                'roles': roles, 'flags': 0,
            })
            self.assertIn('user_update', [event[0] for event in dispatched])
            for name, *args in dispatched:
                await getattr(monitor, 'on_' + name)(*args)

        await parse({'identity_guild_id': '1', 'identity_enabled': True,
                     'tag': 'TEST', 'badge': None}, [])
        http.add_role.assert_awaited_once_with(1, 100, 42, reason='Server tag detected')
        http.remove_role.assert_awaited_once_with(2, 100, 142, reason='Server tag removed')
        # Les réponses REST ne mettent pas le cache à jour : simuler l'écho
        # Gateway des rôles avant le deuxième changement de profil.
        foreign.get_member(100)._roles = discord.utils.SnowflakeList([])
        http.remove_role.reset_mock()
        await parse(None, ['42'])
        http.remove_role.assert_awaited_once_with(1, 100, 42, reason='Server tag removed')
        self.assertEqual(http.add_role.await_count, 1)

    async def test_stats_includes_baseline_thirty_days_before_today(self):
        today = datetime.now(timezone.utc).date()
        self.bot.db.get_tag_stats = AsyncMock(return_value=[
            {'date': (today - timedelta(days=30)).isoformat(), 'tagged': 10, 'members': 20},
            {'date': today.isoformat(), 'tagged': 12, 'members': 20},
        ])
        interaction = interaction_for(self.guild)
        await self.commands.stats.callback(self.commands, interaction)
        self.bot.db.get_tag_stats.assert_awaited_once_with(self.guild.id, days=31)
        embed = interaction.response.send_message.await_args.kwargs['embed']
        self.assertEqual(embed.fields[2].value, '+2 (10 → 12)')

    async def test_manage_roles_is_checked_at_runtime(self):
        for name in ('config', 'reset', 'status', 'toggle', 'scan', 'check_member', 'stats'):
            with self.subTest(command=name):
                command = getattr(self.commands, name)
                interaction = interaction_for(self.guild)
                with self.assertRaises(app_commands.MissingPermissions):
                    await command._check_can_run(interaction)
                interaction.permissions = discord.Permissions(manage_roles=True)
                self.assertTrue(await command._check_can_run(interaction))


if __name__ == '__main__':
    unittest.main()

