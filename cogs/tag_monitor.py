from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
import os
from typing import Dict, List, Optional, Set

import discord
from discord.ext import commands, tasks

from tag_utils import is_unmatchable_tag

logger = logging.getLogger('PickTag2GetRole.TagMonitor')


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


# Le cache complet permet de traiter GUILD_MEMBER_UPDATE pour tous les membres.
# Le champ primary_guild est traité par discord.py via on_user_update.
CHUNK_ENABLED_GUILDS = _env_flag('CHUNK_ENABLED_GUILDS', True)


class TagMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chunking_enabled = CHUNK_ENABLED_GUILDS
        self.member_cache: Dict[int, Set[int]] = {}
        self.permission_issues: Dict[int, Set[int]] = {}
        self.invalid_tag_guilds: Set[int] = set()
        self._scan_locks: Dict[int, asyncio.Lock] = {}
        self._state_locks: Dict[int, asyncio.Lock] = {}
        self._revisions: Dict[int, int] = {}
        self._global_scan_lock = asyncio.Lock()

    async def cog_load(self):
        self.daily_check.start()

    async def cog_unload(self):
        self.daily_check.cancel()

    def _get_scan_lock(self, guild_id: int) -> asyncio.Lock:
        return self._scan_locks.setdefault(guild_id, asyncio.Lock())

    def _get_state_lock(self, guild_id: int) -> asyncio.Lock:
        # Ne pas supprimer un verrou au reset : des coroutines peuvent déjà
        # l'attendre. Le remplacer leur permettrait de travailler en parallèle.
        return self._state_locks.setdefault(guild_id, asyncio.Lock())

    @asynccontextmanager
    async def configuration_change(self, guild_id: int):
        """Sérialiser une mutation avec les rôles et invalider les anciens scans.

        Un scan ne garde ce verrou que pour un membre ou son écriture finale,
        donc une suppression n'attend pas le parcours complet du serveur.
        L'appelant écrit la base et rafraîchit config_cache dans ce contexte.
        """
        async with self._get_state_lock(guild_id):
            self._revisions[guild_id] = self._revisions.get(guild_id, 0) + 1
            self.member_cache.pop(guild_id, None)
            self.permission_issues.pop(guild_id, None)
            self.invalid_tag_guilds.discard(guild_id)
            # Une mutation persistante peut réussir avant que refresh_cache
            # échoue. Suspendre d'abord évite d'appliquer l'ancienne config.
            async with self.bot.cache_lock:
                self.bot.config_cache.pop(guild_id, None)
            yield

    async def delete_guild_data(self, guild_id: int):
        """Supprimer aussi les statistiques orphelines, sans lire la config."""
        async with self.configuration_change(guild_id):
            await self.bot.db.delete_guild_config(guild_id)

    def get_tagged_count(self, guild_id: int) -> Optional[int]:
        members = self.member_cache.get(guild_id)
        return len(members) if members is not None else None

    def _active_config(self, guild_id: int) -> Optional[tuple]:
        config = self.bot.get_guild_config_cached(guild_id)
        if not config or not config.get('enabled', False):
            return None
        tag = config.get('tag_to_watch')
        role_ids = config.get('role_ids', [])
        if not tag or not role_ids:
            return None
        if is_unmatchable_tag(tag):
            if guild_id not in self.invalid_tag_guilds:
                self.invalid_tag_guilds.add(guild_id)
                logger.warning('Monitoring paused: an invalid tag is configured')
            return None
        self.invalid_tag_guilds.discard(guild_id)
        return tag, list(role_ids)

    def _note_permission_issue(self, guild_id: int, member_id: int):
        members = self.permission_issues.setdefault(guild_id, set())
        if not members:
            logger.warning('Role synchronization blocked by permissions or role hierarchy')
        members.add(member_id)

    async def _sync_member(self, guild: discord.Guild, member_id: int):
        # Relire le membre et la configuration après attente : les événements
        # en file peuvent décrire un ancien tag ou une ancienne configuration.
        async with self._get_state_lock(guild.id):
            if self.bot.get_guild(guild.id) is not guild:
                return
            active = self._active_config(guild.id)
            member = guild.get_member(member_id)
            if active is None or member is None:
                return
            tag, role_ids = active
            await self._update_member_roles(member, self._member_has_tag(member, tag), role_ids)

    @staticmethod
    def _tag_identity(user):
        pg = getattr(user, 'primary_guild', None)
        if pg is None:
            return None, False, None
        return pg.id, pg.identity_enabled, pg.tag

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if self._tag_identity(before) != self._tag_identity(after):
            await self._sync_member(after.guild, after.id)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        # GUILD_MEMBER_UPDATE met à jour l'utilisateur partagé dans discord.py et
        # émet user_update lorsque primary_guild change, sans Presence Intent.
        if self._tag_identity(before) == self._tag_identity(after):
            return
        for guild in list(self.bot.guilds):
            if guild.get_member(after.id) is not None:
                await self._sync_member(guild, after.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self._sync_member(member.guild, member.id)

    @staticmethod
    def _member_has_tag(member: discord.Member, tag: str) -> bool:
        """Un tag public exact, issu du serveur où le rôle doit être attribué."""
        pg = getattr(member, 'primary_guild', None)
        return bool(
            pg is not None
            and pg.identity_enabled is True
            and pg.id == member.guild.id
            and pg.tag
            and pg.tag.casefold() == tag.casefold()
        )

    def _manageable_roles(self, guild: discord.Guild, role_ids: List[int]) -> Set[int]:
        """Tout ou rien : éviter de modifier une configuration partiellement."""
        me = guild.me
        if me is None or not me.guild_permissions.manage_roles:
            return set()
        writable = set()
        existing = set()
        for role_id in role_ids:
            role = guild.get_role(role_id)
            if role is None:
                continue
            existing.add(role_id)
            if not role.is_default() and not role.managed and role < me.top_role:
                writable.add(role_id)
        return writable if writable == existing else set()

    async def _update_member_roles(self, member: discord.Member, should_have_roles: bool,
                                   role_ids: List[int]) -> bool:
        """Appelé sous verrou d'état ; le reset attend les requêtes engagées."""
        writable_ids = self._manageable_roles(member.guild, role_ids)
        roles_to_add = []
        roles_to_remove = []
        blocked = False
        for role_id in dict.fromkeys(role_ids):
            role = member.guild.get_role(role_id)
            if role is None:
                continue
            has_role = role in member.roles
            if should_have_roles and not has_role:
                if role_id in writable_ids:
                    roles_to_add.append(role)
                else:
                    blocked = True
            elif not should_have_roles and has_role:
                if role_id in writable_ids:
                    roles_to_remove.append(role)
                else:
                    blocked = True
        if blocked:
            self._note_permission_issue(member.guild.id, member.id)

        changed = False
        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason='Server tag detected')
                changed = True
            except discord.Forbidden:
                self._note_permission_issue(member.guild.id, member.id)
            except discord.HTTPException:
                logger.error('A role assignment request failed')
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason='Server tag removed')
                changed = True
            except discord.Forbidden:
                self._note_permission_issue(member.guild.id, member.id)
            except discord.HTTPException:
                logger.error('A role removal request failed')

        cache = self.member_cache.get(member.guild.id)
        if cache is not None:
            if should_have_roles:
                cache.add(member.id)
            else:
                cache.discard(member.id)
        return changed

    async def ensure_chunked(self, guild: discord.Guild):
        if not self.chunking_enabled or guild.chunked:
            return
        try:
            await guild.chunk(cache=True)
            logger.info('Member cache loaded')
        except Exception:
            logger.error('Member cache loading failed')

    def _scan_is_current(self, guild: discord.Guild, revision: int, active: tuple) -> bool:
        return (
            self.bot.get_guild(guild.id) is guild
            and self._revisions.get(guild.id, 0) == revision
            and self._active_config(guild.id) == active
        )

    async def scan_guild(self, guild: discord.Guild, tag_to_watch: str,
                         role_ids: List[int]) -> Optional[Dict[str, int]]:
        """Scanner une config précise ; toute mutation invalide ce travail."""
        lock = self._get_scan_lock(guild.id)
        if lock.locked():
            return None
        async with lock:
            async with self._get_state_lock(guild.id):
                active = self._active_config(guild.id)
                if active != (tag_to_watch, list(role_ids)):
                    return {'cancelled': True}
                revision = self._revisions.get(guild.id, 0)
                if not self._scan_is_current(guild, revision, active):
                    return {'cancelled': True}
                self.permission_issues.pop(guild.id, None)
                # Ce set reste partagé avec les listeners : une mise à jour
                # traitée après le passage du scan ne doit pas être écrasée.
                tagged: Set[int] = set()
                self.member_cache[guild.id] = tagged

            await self.ensure_chunked(guild)
            async with self._get_state_lock(guild.id):
                if not self._scan_is_current(guild, revision, active):
                    return {'cancelled': True}

            async def iter_members():
                if guild.chunked:
                    for member in list(guild.members):
                        yield member
                else:
                    iterator = guild.fetch_members(limit=None).__aiter__()
                    try:
                        while True:
                            # Ne pas lancer la page REST suivante après une
                            # désactivation intervenue au traitement précédent.
                            async with self._get_state_lock(guild.id):
                                if not self._scan_is_current(guild, revision, active):
                                    return
                            try:
                                member = await anext(iterator)
                            except StopAsyncIteration:
                                return
                            yield member
                    finally:
                        await iterator.aclose()

            checked = 0
            updated = 0
            async for fetched_member in iter_members():
                async with self._get_state_lock(guild.id):
                    if not self._scan_is_current(guild, revision, active):
                        return {'cancelled': True}
                    # Préférer le cache vivant au snapshot du scan REST.
                    member = guild.get_member(fetched_member.id) or fetched_member
                    has_tag = self._member_has_tag(member, tag_to_watch)
                    if await self._update_member_roles(member, has_tag, role_ids):
                        updated += 1
                    checked += 1
                await asyncio.sleep(0)

            async with self._get_state_lock(guild.id):
                if not self._scan_is_current(guild, revision, active):
                    return {'cancelled': True}
                try:
                    await self.bot.db.record_tag_stat(guild.id, len(tagged), checked)
                except Exception:
                    logger.error('Recording aggregate tag statistics failed')
                return {'checked': checked, 'tagged': len(tagged), 'updated': updated}

    async def check_all_tags(self):
        if self._global_scan_lock.locked():
            return
        async with self._global_scan_lock:
            for guild in list(self.bot.guilds):
                active = self._active_config(guild.id)
                if active is None:
                    continue
                try:
                    stats = await self.scan_guild(guild, *active)
                    if stats and not stats.get('cancelled'):
                        logger.info('Tag scan completed')
                except Exception:
                    logger.error('A tag scan failed')

    @tasks.loop(hours=24)
    async def daily_check(self):
        logger.info('Starting daily tag verification')
        try:
            await self.bot.db.purge_expired_stats()
        except Exception:
            logger.error('Purging expired statistics failed')
        await self.check_all_tags()
        logger.info('Daily tag verification completed')

    @daily_check.before_loop
    async def before_daily_check(self):
        await self.bot.wait_until_ready()



async def setup(bot):
    await bot.add_cog(TagMonitor(bot))
