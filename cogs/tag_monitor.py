from __future__ import annotations
import discord
from discord.ext import commands, tasks
import asyncio
import os
from typing import Dict, Set, Optional, List
import logging

from tag_utils import DISCORD_TAG_MAX_LENGTH, is_role_mention, is_unmatchable_tag

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
        self.permission_issues: Dict[int, Set[int]] = {}  # guild_id -> IDs des membres non modifiables
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
                # Ne jamais logger la valeur du tag : c'est un champ libre qui peut
                # contenir n'importe quoi (la policy promet « IDs only » dans les
                # logs). L'admin voit la valeur via /status dans son serveur.
                reason = ("a role mention" if is_role_mention(tag_to_watch)
                          else f"{len(tag_to_watch)} characters (server tags are at "
                               f"most {DISCORD_TAG_MAX_LENGTH})")
                logger.warning(
                    "Guild %s: configured tag is %s — it can never match a server tag; "
                    "monitoring paused for this guild to avoid mass role removal",
                    guild_id, reason
                )
            return None

        self.invalid_tag_guilds.discard(guild_id)
        return tag_to_watch, role_ids

    def _note_permission_issue(self, guild_id: int, member_id: int):
        """Comptabiliser un membre non modifiable et ne logger qu'une fois par serveur.

        Un set d'IDs et non un compteur : les listeners temps réel peuvent
        repasser plusieurs fois sur le même membre entre deux scans, et un
        compteur gonflerait au-delà du nombre réel de membres concernés
        (/status affichait « 13 membres » sur un serveur de 10).
        """
        members = self.permission_issues.setdefault(guild_id, set())
        if not members:
            logger.warning(
                "Guild %s: missing permissions to manage roles — my role is probably "
                "below the configured roles, or I lack Manage Roles",
                guild_id
            )
        members.add(member_id)

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

            # Comparaison exacte (insensible à la casse), ou partielle si le tag
            # configuré contient un '#'
            matched = (pg.tag.lower() == tag.lower()
                       or ('#' in tag and tag.lower() in pg.tag.lower()))
            # Valeurs volontairement absentes du log, même en DEBUG : le tag du
            # membre est une donnée de profil et la policy promet « IDs only ».
            # Pour comparer les valeurs, un admin utilise /check dans son serveur.
            logger.debug("Member %s: displayed server tag %s the configured tag",
                         member.id, "matches" if matched else "does not match")
            if matched:
                return True

        except Exception as e:
            logger.error("Unexpected error checking tag for member_id=%s: %s: %s",
                         member.id, type(e).__name__, e)

        return False

    def _manageable_roles(self, guild: discord.Guild, role_ids: List[int]) -> Set[int]:
        """IDs des rôles configurés que le bot peut réellement modifier.

        Trois causes de refus, toutes lisibles depuis le cache sans appel API :
        permission Manage Roles absente, rôle situé au-dessus du bot dans la
        hiérarchie, rôle géré par une intégration ou par le boost serveur
        (Discord refuse toujours de l'attribuer à la main).

        Les filtrer évite d'envoyer des requêtes dont l'échec est certain : un
        403 consomme le rate limit de Discord comme un succès, soit environ une
        seconde par membre sur un serveur mal configuré.

        Tout ou rien : si un seul des rôles configurés est intouchable, aucun
        n'est renvoyé. Appliquer la configuration à moitié laisserait le serveur
        incohérent (des membres gardant un rôle et perdant l'autre) et retirerait
        des rôles à des membres que le rôle bloquant protégeait jusqu'ici —
        discord.py envoyant une requête par rôle, le premier refus interrompait
        la séquence avant d'atteindre les rôles suivants.
        """
        me = guild.me
        if me is None or not me.guild_permissions.manage_roles:
            return set()

        top = me.top_role
        writable = set()
        existing = set()  # en set : role_ids peut contenir des doublons (anciennes configs)
        for role_id in role_ids:
            role = guild.get_role(role_id)
            if role is None:
                # Rôle supprimé du serveur : rien à écrire, et pas un blocage
                continue
            existing.add(role_id)
            if not role.managed and role < top:
                writable.add(role_id)

        if writable != existing:
            return set()
        return writable

    async def _update_member_roles(self, member: discord.Member, should_have_roles: bool,
                                   role_ids: List[int],
                                   writable_ids: Optional[Set[int]] = None) -> bool:
        """Mettre à jour les rôles d'un membre. Retourne True si quelque chose a changé.

        `writable_ids` est le sous-ensemble de `role_ids` que le bot peut modifier,
        calculé une seule fois par scan. Un rôle qui devrait changer mais n'y figure
        pas est comptabilisé comme bloqué sans qu'aucune requête ne soit envoyée.
        None (chemin des listeners temps réel) le fait résoudre à la volée.
        """
        if writable_ids is None:
            writable_ids = self._manageable_roles(member.guild, role_ids)

        roles_to_add = []
        roles_to_remove = []
        blocked = False

        # dict.fromkeys : dédoublonner en préservant l'ordre — les anciennes
        # configs peuvent contenir un même rôle deux fois, et chaque occurrence
        # coûterait une requête HTTP de plus
        for role_id in dict.fromkeys(role_ids):
            role = member.guild.get_role(role_id)
            if not role:
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

        # Changement nécessaire sur un rôle non modifiable : on le comptabilise
        # pour /status, mais sans appeler l'API puisque la requête échouerait
        if blocked:
            self._note_permission_issue(member.guild.id, member.id)

        changed = False
        # discord.py envoie une requête par rôle (add_roles/remove_roles sont
        # atomiques par défaut), et non une seule pour la liste entière
        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="Server tag detected")
                logger.debug("Added roles %s to member_id=%s", [r.id for r in roles_to_add], member.id)
                changed = True
            except discord.Forbidden:
                # Rôle au-dessus du bot ou permission manquante : signalé une fois par
                # serveur plutôt qu'une ligne d'erreur par membre
                self._note_permission_issue(member.guild.id, member.id)
            except discord.HTTPException as e:
                logger.error("Error adding roles in guild_id=%s to member_id=%s: %s",
                             member.guild.id, member.id, e)
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason="Server tag removed")
                logger.debug("Removed roles %s from member_id=%s", [r.id for r in roles_to_remove], member.id)
                changed = True
            except discord.Forbidden:
                self._note_permission_issue(member.guild.id, member.id)
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
            logger.warning("Guild %s: refusing to scan, the configured tag can never match a server tag",
                           guild.id)
            return None

        async with lock:
            # Repartir d'un compteur neuf : /status doit refléter le dernier scan
            self.permission_issues.pop(guild.id, None)
            await self.ensure_chunked(guild)

            # Une seule fois pour tout le serveur : la hiérarchie des rôles et la
            # permission du bot ne changent pas d'un membre à l'autre
            writable_ids = self._manageable_roles(guild, role_ids)

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
                if await self._update_member_roles(member, has_tag, role_ids, writable_ids):
                    updated += 1

                checked += 1
                # Céder la main à la boucle d'événements sans temporiser. La
                # vérification d'un membre en cache est du calcul mémoire : quand
                # rien ne change — le cas dominant — il n'y a aucun trafic API à
                # lisser, et les écritures sont déjà limitées par discord.py.
                await asyncio.sleep(0)

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
                        blocked = len(self.permission_issues.get(guild.id, ()))
                        logger.info("Guild %s: %s members checked, %s tagged, %s updated%s",
                                    guild.id, stats['checked'], stats['tagged'], stats['updated'],
                                    f", {blocked} blocked by permissions" if blocked else "")
                except Exception as e:
                    logger.error("Error scanning guild %s: %s", guild.id, e)

    @tasks.loop(hours=24)  # Vérification une fois par jour
    async def daily_check(self):
        """Tâche quotidienne pour vérifier les tags"""
        logger.info("Starting daily tag verification...")
        # Purge globale des stats expirées : record_tag_stat ne purge que les
        # serveurs scannés, un serveur désactivé ou en pause y échapperait
        try:
            await self.bot.db.purge_expired_stats()
        except Exception as e:
            logger.error("Error purging expired stats: %s", e)
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
