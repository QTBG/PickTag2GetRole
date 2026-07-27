from __future__ import annotations
import discord
from discord.ext import commands, tasks
import asyncio
import os
from typing import Dict, Set, Optional, List
import logging

from tag_utils import is_unmatchable_tag

logger = logging.getLogger('PickTag2GetRole.TagMonitor')

def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')

# Charger en cache la liste complète des membres des serveurs où la surveillance
# est activée ("chunking"). Nécessaire pour que les événements temps réel
# (on_member_update / on_presence_update) couvrent tous les membres des gros
# serveurs (>250 membres). Coût : ~1 Ko de RAM par membre mis en cache.
CHUNK_ENABLED_GUILDS = _env_flag('CHUNK_ENABLED_GUILDS', True)

class TagMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chunking_enabled = CHUNK_ENABLED_GUILDS
        self.member_cache: Dict[int, Set[int]] = {}  # guild_id -> member_ids ayant le tag (dernier scan)
        self.permission_issues: Dict[int, int] = {}  # guild_id -> membres non modifiables (403)
        self.invalid_tag_guilds: Set[int] = set()  # guild_id -> configuration impossible à satisfaire
        self._scan_locks: Dict[int, asyncio.Lock] = {}  # guild_id -> verrou anti-scans concurrents
        self._global_scan_lock = asyncio.Lock()

    async def cog_load(self):
        """Démarrer les tâches périodiques après le chargement du cog"""
        logger.info(f"Discord.py version: {discord.__version__}")
        # La première itération de daily_check (juste après on_ready) sert de scan initial
        self.daily_check.start()
        # Démarrer le log des statistiques serveur
        self.server_count_log.start()

    async def cog_unload(self):
        """Arrêter la surveillance lors du déchargement"""
        self.daily_check.cancel()
        self.server_count_log.cancel()

    def _get_scan_lock(self, guild_id: int) -> asyncio.Lock:
        lock = self._scan_locks.get(guild_id)
        if lock is None:
            lock = asyncio.Lock()
            self._scan_locks[guild_id] = lock
        return lock

    def get_tagged_count(self, guild_id: int) -> Optional[int]:
        """Nombre de membres ayant le tag au dernier scan (None si aucun scan encore fait)"""
        members = self.member_cache.get(guild_id)
        return len(members) if members is not None else None

    def _active_config(self, guild_id: int) -> Optional[tuple]:
        """Configuration exploitable d'un serveur, ou None.

        Renvoie None si la surveillance est désactivée, la configuration incomplète,
        ou le tag impossible à satisfaire (typiquement une mention de rôle collée dans
        le champ tag). Dans ce dernier cas le bot ne touche à AUCUN rôle : sinon il
        conclurait que plus personne ne porte le tag et les retirerait à tout le serveur.
        """
        config = self.bot.get_guild_config_cached(guild_id)
        if not config or not config.get('enabled', False):
            return None

        tag_to_watch = config.get('tag_to_watch')
        role_ids = config.get('role_ids', [])
        if not tag_to_watch or not role_ids:
            return None

        if is_unmatchable_tag(tag_to_watch):
            if guild_id not in self.invalid_tag_guilds:
                self.invalid_tag_guilds.add(guild_id)
                logger.warning(
                    "Guild %s: configured tag %r is a mention, not a server tag — "
                    "monitoring paused for this guild to avoid mass role removal",
                    guild_id, tag_to_watch
                )
            return None

        self.invalid_tag_guilds.discard(guild_id)
        return tag_to_watch, role_ids

    def _note_permission_issue(self, guild_id: int):
        """Comptabiliser un 403 et n'en logger qu'un seul par serveur"""
        seen = self.permission_issues.get(guild_id, 0)
        self.permission_issues[guild_id] = seen + 1
        if seen == 0:
            logger.warning(
                "Guild %s: missing permissions to manage roles — my role is probably "
                "below the configured roles, or I lack Manage Roles",
                guild_id
            )

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Nettoyer les caches en mémoire quand le bot quitte un serveur"""
        self.member_cache.pop(guild.id, None)
        self.permission_issues.pop(guild.id, None)
        self.invalid_tag_guilds.discard(guild.id)
        self._scan_locks.pop(guild.id, None)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Événement déclenché lors de la mise à jour d'un membre"""
        active = self._active_config(after.guild.id)
        if not active:
            return
        tag_to_watch, role_ids = active

        # Vérifier si le tag a changé
        before_has_tag = self._member_has_tag(before, tag_to_watch)
        after_has_tag = self._member_has_tag(after, tag_to_watch)

        if before_has_tag != after_has_tag:
            logger.debug("Tag change detected for member_id=%s: %s -> %s", after.id, before_has_tag, after_has_tag)
            await self._update_member_roles(after, after_has_tag, role_ids)

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Événement déclenché lors de la mise à jour de la présence (inclut primary_guild)"""
        active = self._active_config(after.guild.id)
        if not active:
            return
        tag_to_watch, role_ids = active

        # Vérifier si le tag a changé
        before_has_tag = self._member_has_tag(before, tag_to_watch)
        after_has_tag = self._member_has_tag(after, tag_to_watch)

        if before_has_tag != after_has_tag:
            logger.debug("Tag change detected in presence update for member_id=%s: %s -> %s",
                         after.id, before_has_tag, after_has_tag)
            await self._update_member_roles(after, after_has_tag, role_ids)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        """Événement déclenché lors de la mise à jour d'un utilisateur (inclut primary_guild)"""
        before_pg = getattr(before, 'primary_guild', None)
        after_pg = getattr(after, 'primary_guild', None)

        if before_pg == after_pg:
            return

        logger.debug("Primary guild change detected via on_user_update for user_id=%s", after.id)

        # Traiter tous les serveurs où cet utilisateur est membre
        for guild in self.bot.guilds:
            member = guild.get_member(after.id)
            if not member:
                continue

            active = self._active_config(guild.id)
            if not active:
                continue
            tag_to_watch, role_ids = active

            # Vérifier si le tag correspond maintenant
            has_tag = self._member_has_tag(member, tag_to_watch)

            # Reconstituer l'état précédent à partir des données de before
            # (l'ancien membre n'est plus disponible dans le cache)
            before_has_tag = False
            if before_pg and before_pg.tag and before_pg.identity_enabled != False:
                if before_pg.tag.lower() == tag_to_watch.lower():
                    before_has_tag = True
                elif '#' in tag_to_watch and tag_to_watch.lower() in before_pg.tag.lower():
                    before_has_tag = True

            if before_has_tag != has_tag:
                logger.debug("Tag change detected for member_id=%s in guild_id=%s: %s -> %s",
                             member.id, guild.id, before_has_tag, has_tag)
                await self._update_member_roles(member, has_tag, role_ids)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Événement déclenché quand un membre rejoint le serveur"""
        active = self._active_config(member.guild.id)
        if not active:
            return
        tag_to_watch, role_ids = active

        # Vérifier si le nouveau membre a le tag
        if self._member_has_tag(member, tag_to_watch):
            logger.info("New member joined with matching tag: member_id=%s", member.id)
            await self._update_member_roles(member, True, role_ids)

    def _member_has_tag(self, member: discord.Member, tag: str) -> bool:
        """Vérifier si un membre a le tag de serveur (guild tag) spécifié"""
        try:
            pg = getattr(member, 'primary_guild', None)
            if pg is None:
                return False

            # Vérifier si l'identité est activée (publiquement affichée)
            if pg.identity_enabled == False:
                return False

            if not pg.tag:
                return False

            logger.debug("Member %s: tag=%r vs looking_for=%r", member.id, pg.tag, tag)

            # Comparaison exacte du tag (insensible à la casse)
            if pg.tag.lower() == tag.lower():
                return True
            # Si le tag configuré contient un #, essayer une correspondance partielle
            if '#' in tag and tag.lower() in pg.tag.lower():
                return True

        except Exception as e:
            logger.error("Unexpected error checking tag for member_id=%s: %s: %s",
                         member.id, type(e).__name__, e)

        return False

    async def _update_member_roles(self, member: discord.Member, should_have_roles: bool,
                                   role_ids: List[int]) -> bool:
        """Mettre à jour les rôles d'un membre. Retourne True si quelque chose a changé."""
        roles_to_add = []
        roles_to_remove = []

        for role_id in role_ids:
            role = member.guild.get_role(role_id)
            if not role:
                continue

            has_role = role in member.roles

            if should_have_roles and not has_role:
                roles_to_add.append(role)
            elif not should_have_roles and has_role:
                roles_to_remove.append(role)

        changed = False
        # Un seul appel API pour tous les ajouts, un seul pour tous les retraits
        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="Server tag detected")
                logger.debug("Added roles %s to member_id=%s", [r.id for r in roles_to_add], member.id)
                changed = True
            except discord.Forbidden:
                # Rôle au-dessus du bot ou permission manquante : signalé une fois par
                # serveur plutôt qu'une ligne d'erreur par membre
                self._note_permission_issue(member.guild.id)
            except discord.HTTPException as e:
                logger.error("Error adding roles in guild_id=%s to member_id=%s: %s",
                             member.guild.id, member.id, e)
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason="Server tag removed")
                logger.debug("Removed roles %s from member_id=%s", [r.id for r in roles_to_remove], member.id)
                changed = True
            except discord.Forbidden:
                self._note_permission_issue(member.guild.id)
            except discord.HTTPException as e:
                logger.error("Error removing roles in guild_id=%s from member_id=%s: %s",
                             member.guild.id, member.id, e)

        # Tenir à jour le compteur de membres taggés (stats)
        cache = self.member_cache.get(member.guild.id)
        if cache is not None:
            if should_have_roles:
                cache.add(member.id)
            else:
                cache.discard(member.id)

        return changed

    async def ensure_chunked(self, guild: discord.Guild):
        """Charger tous les membres du serveur en cache pour la détection temps réel"""
        if not self.chunking_enabled or guild.chunked:
            return
        try:
            await guild.chunk(cache=True)
            logger.info("Chunked guild %s: %s members cached", guild.id, len(guild.members))
        except Exception as e:
            logger.error("Error chunking guild %s: %s", guild.id, e)

    async def scan_guild(self, guild: discord.Guild, tag_to_watch: str,
                         role_ids: List[int]) -> Optional[Dict[str, int]]:
        """Scanner tous les membres d'un serveur et corriger les rôles.

        Retourne des statistiques, ou None si un scan est déjà en cours pour ce serveur.
        """
        lock = self._get_scan_lock(guild.id)
        if lock.locked():
            return None

        if is_unmatchable_tag(tag_to_watch):
            logger.warning("Guild %s: refusing to scan, configured tag %r is a mention",
                           guild.id, tag_to_watch)
            return None

        async with lock:
            # Repartir d'un compteur neuf : /status doit refléter le dernier scan
            self.permission_issues.pop(guild.id, None)
            await self.ensure_chunked(guild)

            async def iter_members():
                if guild.chunked:
                    # Cache complet : zéro appel REST
                    for m in list(guild.members):
                        yield m
                else:
                    async for m in guild.fetch_members(limit=None):
                        yield m

            checked = 0
            updated = 0
            tagged: Set[int] = set()

            async for member in iter_members():
                has_tag = self._member_has_tag(member, tag_to_watch)
                if has_tag:
                    tagged.add(member.id)
                if await self._update_member_roles(member, has_tag, role_ids):
                    updated += 1

                checked += 1
                # Petite pause toutes les 10 vérifications pour lisser la charge
                if checked % 10 == 0:
                    await asyncio.sleep(0.1)

            self.member_cache[guild.id] = tagged

            # Statistiques agrégées journalières (compteurs uniquement)
            try:
                await self.bot.db.record_tag_stat(guild.id, len(tagged), checked)
            except Exception as e:
                logger.error("Error recording stats for guild %s: %s", guild.id, e)

            return {'checked': checked, 'tagged': len(tagged), 'updated': updated}

    async def check_all_tags(self):
        """Vérifier tous les tags pour tous les serveurs (au premier démarrage puis quotidiennement)"""
        if self._global_scan_lock.locked():
            return

        async with self._global_scan_lock:
            for guild in self.bot.guilds:
                active = self._active_config(guild.id)
                if not active:
                    continue
                tag_to_watch, role_ids = active

                try:
                    stats = await self.scan_guild(guild, tag_to_watch, role_ids)
                    if stats:
                        blocked = self.permission_issues.get(guild.id, 0)
                        logger.info("Guild %s: %s members checked, %s tagged, %s updated%s",
                                    guild.id, stats['checked'], stats['tagged'], stats['updated'],
                                    f", {blocked} blocked by permissions" if blocked else "")
                except Exception as e:
                    logger.error("Error scanning guild %s: %s", guild.id, e)

    @tasks.loop(hours=24)  # Vérification une fois par jour
    async def daily_check(self):
        """Tâche quotidienne pour vérifier les tags"""
        logger.info("Starting daily tag verification...")
        await self.check_all_tags()
        logger.info("Daily tag verification completed")

    @daily_check.before_loop
    async def before_daily_check(self):
        """Attendre que le bot soit prêt avant de démarrer la tâche"""
        await self.bot.wait_until_ready()

    @tasks.loop(hours=12)  # Log server count every 12 hours
    async def server_count_log(self):
        """Log server count and basic statistics"""
        enabled_count = len(self.bot.config_cache)
        logger.info(f"Server Statistics: Total={len(self.bot.guilds)} | Enabled={enabled_count}")

    @server_count_log.before_loop
    async def before_server_count_log(self):
        """Wait for bot to be ready"""
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(TagMonitor(bot))
