from __future__ import annotations
import discord
from discord.ext import commands, tasks
import asyncio
from typing import Set, Optional, List
import logging

logger = logging.getLogger('PickTag2GetRole.TagMonitor')

class TagMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.processing = False
        self.member_cache: dict[int, Set[int]] = {}  # guild_id -> set of member_ids with tag
        
    async def cog_load(self):
        """Démarrer la surveillance après le chargement du cog"""
        # Vérifier la version de discord.py et le support de primary_guild
        logger.info(f"Discord.py version: {discord.__version__}")
        
        # Tester si primary_guild est supporté
        test_member = None
        for guild in self.bot.guilds:
            if guild.members:
                test_member = guild.members[0]
                break
        
        if test_member:
            has_primary_guild = hasattr(test_member, 'primary_guild')
            logger.info(f"Primary guild support: {has_primary_guild}")
            if has_primary_guild:
                logger.info("Primary guild attribute is available")
        
        # Attendre un peu pour s'assurer que tout est chargé
        await asyncio.sleep(2)
        self.check_tags.start()
        
    async def cog_unload(self):
        """Arrêter la surveillance lors du déchargement"""
        self.check_tags.cancel()
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Événement déclenché lors de la mise à jour d'un membre"""
        if self.processing:
            return
            
        # Vérifier si le serveur a une configuration
        config = self.bot.get_guild_config_cached(after.guild.id)
        if not config or not config.get('enabled', False):
            return
        
        tag_to_watch = config.get('tag_to_watch')
        role_ids = config.get('role_ids', [])
        
        if not tag_to_watch or not role_ids:
            return
        
        # Vérifier si le tag a changé
        before_has_tag = self._member_has_tag(before, tag_to_watch)
        after_has_tag = self._member_has_tag(after, tag_to_watch)
        
        if before_has_tag != after_has_tag:
            logger.debug(f"Tag change detected for {after.name}: {before_has_tag} -> {after_has_tag}")
            await self._update_member_roles(after, after_has_tag, role_ids)
    
    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Événement déclenché lors de la mise à jour de la présence (inclut primary_guild)"""
        if self.processing:
            return
            
        # Vérifier si le serveur a une configuration
        config = self.bot.get_guild_config_cached(after.guild.id)
        if not config or not config.get('enabled', False):
            return
        
        tag_to_watch = config.get('tag_to_watch')
        role_ids = config.get('role_ids', [])
        
        if not tag_to_watch or not role_ids:
            return
        
        # Comparer les primary guilds
        before_pg = getattr(before, 'primary_guild', None)
        after_pg = getattr(after, 'primary_guild', None)
        
        # Logger les changements pour debug
        if before_pg != after_pg:
            logger.debug(f"Primary guild change detected for {after.name}")
            if before_pg:
                logger.debug(f"  Before: ID={before_pg.id}, Tag={before_pg.tag}, Enabled={before_pg.identity_enabled}")
            else:
                logger.debug(f"  Before: None")
            if after_pg:
                logger.debug(f"  After: ID={after_pg.id}, Tag={after_pg.tag}, Enabled={after_pg.identity_enabled}")
            else:
                logger.debug(f"  After: None")
        
        # Vérifier si le tag a changé
        before_has_tag = self._member_has_tag(before, tag_to_watch)
        after_has_tag = self._member_has_tag(after, tag_to_watch)
        
        if before_has_tag != after_has_tag:
            logger.debug(f"Tag change detected in presence update for {after.name}: {before_has_tag} -> {after_has_tag}")
            await self._update_member_roles(after, after_has_tag, role_ids)
    
    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        """Événement déclenché lors de la mise à jour d'un utilisateur (inclut primary_guild)"""
        logger.debug(f"User update detected for {after.name}")
        
        # Vérifier les changements de primary_guild
        before_pg = getattr(before, 'primary_guild', None)
        after_pg = getattr(after, 'primary_guild', None)
        
        # Si le primary guild a changé
        if before_pg != after_pg:
            logger.debug(f"Primary guild change detected via on_user_update for {after.name}")
            if before_pg:
                logger.debug(f"  Before: ID={before_pg.id}, Tag={before_pg.tag}, Enabled={before_pg.identity_enabled}")
            else:
                logger.debug(f"  Before: None")
            if after_pg:
                logger.debug(f"  After: ID={after_pg.id}, Tag={after_pg.tag}, Enabled={after_pg.identity_enabled}")
            else:
                logger.debug(f"  After: None")
            
            # Traiter tous les serveurs où cet utilisateur est membre
            for guild in self.bot.guilds:
                # Vérifier si l'utilisateur est membre de ce serveur
                member = guild.get_member(after.id)
                if not member:
                    continue
                
                # Vérifier si le serveur a une configuration
                config = self.bot.get_guild_config_cached(guild.id)
                if not config or not config.get('enabled', False):
                    continue
                
                tag_to_watch = config.get('tag_to_watch')
                role_ids = config.get('role_ids', [])
                
                if not tag_to_watch or not role_ids:
                    continue
                
                # Vérifier si le tag correspond maintenant
                has_tag = self._member_has_tag(member, tag_to_watch)
                
                # Pour vérifier le tag avant, on doit créer un "faux" membre avec les données de before
                # car on ne peut pas obtenir l'ancien membre depuis le cache
                before_has_tag = False
                if before_pg and before_pg.tag and before_pg.identity_enabled != False:
                    # Comparaison directe des tags
                    if before_pg.tag.lower() == tag_to_watch.lower():
                        before_has_tag = True
                    elif '#' in tag_to_watch and tag_to_watch.lower() in before_pg.tag.lower():
                        before_has_tag = True
                
                # Si le statut du tag a changé, mettre à jour les rôles
                if before_has_tag != has_tag:
                    logger.debug(f"Tag change detected for {member.name} in {guild.name}: {before_has_tag} -> {has_tag}")
                    await self._update_member_roles(member, has_tag, role_ids)
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Événement déclenché quand un membre rejoint le serveur"""
        # Vérifier si le serveur a une configuration
        config = self.bot.get_guild_config_cached(member.guild.id)
        if not config or not config.get('enabled', False):
            return
        
        tag_to_watch = config.get('tag_to_watch')
        role_ids = config.get('role_ids', [])
        
        if not tag_to_watch or not role_ids:
            return
        
        # Vérifier si le nouveau membre a le tag
        if self._member_has_tag(member, tag_to_watch):
            logger.info(f"New member {member.name} joined with matching tag")
            await self._update_member_roles(member, True, role_ids)
    
    async def _fetch_fresh_member(self, guild: discord.Guild, member_id: int) -> Optional[discord.Member]:
        """Récupérer un membre avec des données fraîches depuis l'API"""
        try:
            return await guild.fetch_member(member_id)
        except discord.NotFound:
            return None
        except Exception as e:
            logger.error(f"Error fetching member {member_id}: {e}")
            return None
    
    def _member_has_tag(self, member: discord.Member, tag: str) -> bool:
        """Vérifier si un membre a le tag de serveur (guild tag) spécifié"""
        try:
            logger.debug(f"Checking member: {member.name} (ID: {member.id})")
            
            # Vérifier si l'attribut primary_guild existe
            if not hasattr(member, 'primary_guild'):
                logger.warning(f"{member.name} - No primary_guild attribute found. Discord.py version might be too old or member data is incomplete.")
                return False
            
            # Accéder à primary_guild
            pg = member.primary_guild
            if pg is None:
                logger.debug(f"{member.name} - primary_guild is None")
                return False
                
            logger.debug(f"{member.name} - Primary Guild found: ID={pg.id}, Tag={pg.tag}, Identity enabled={pg.identity_enabled}")
            
            # Vérifier si l'identité est activée (publiquement affichée)
            if pg.identity_enabled == False:
                logger.debug(f"{member.name} has identity_enabled=False, skipping")
                return False
            
            # Vérifier si le tag existe
            if not pg.tag:
                logger.debug(f"{member.name} has no tag set (tag is None or empty)")
                return False
                
            # Comparaison du tag
            logger.debug(f"{member.name} - Comparing tags: member_tag='{pg.tag}' vs looking_for='{tag}'")
            
            # Comparaison exacte du tag (insensible à la casse)
            if pg.tag.lower() == tag.lower():
                logger.debug(f"✅ {member.name} has matching tag: {pg.tag}")
                return True
            # Si le tag configuré contient un #, essayer une correspondance partielle
            elif '#' in tag and tag.lower() in pg.tag.lower():
                logger.debug(f"✅ {member.name} has partial matching tag: {pg.tag} (looking for {tag})")
                return True
            else:
                logger.debug(f"{member.name} has different tag: '{pg.tag}' (looking for '{tag}')")
            
        except AttributeError as e:
            # En cas d'erreur d'attribut, log pour debug
            logger.error(f"AttributeError accessing primary_guild for {member.name}: {e}")
            logger.debug(f"Member attributes: {dir(member)}")
        except Exception as e:
            logger.error(f"Unexpected error checking tag for {member.name}: {type(e).__name__}: {e}")
            
        return False
    
    async def _update_member_roles(self, member: discord.Member, should_have_roles: bool, role_ids: List[int]):
        """Mettre à jour les rôles d'un membre"""
        roles_to_update = []
        
        for role_id in role_ids:
            role = member.guild.get_role(role_id)
            if not role:
                continue
                
            has_role = role in member.roles
            
            if should_have_roles and not has_role:
                roles_to_update.append(role)
            elif not should_have_roles and has_role:
                # Pour retirer, on doit modifier la liste des rôles
                try:
                    await member.remove_roles(role, reason="Tag de serveur retiré")
                    logger.debug(f"Removed role {role.name} from {member.name}")
                except discord.HTTPException as e:
                    logger.error(f"Error removing role {role.name} from {member}: {e}")
        
        # Ajouter les rôles en une seule fois
        if should_have_roles and roles_to_update:
            try:
                await member.add_roles(*roles_to_update, reason="Tag de serveur détecté")
                logger.debug(f"Added roles {[r.name for r in roles_to_update]} to {member.name}")
            except discord.HTTPException as e:
                logger.error(f"Error adding roles to {member}: {e}")
    
    @tasks.loop(minutes=30)  # Vérification toutes les 30 minutes (backup seulement)
    async def check_tags(self):
        """Tâche périodique pour vérifier les tags (backup au cas où les événements sont manqués)"""
        if self.processing:
            return
            
        self.processing = True
        try:
            for guild in self.bot.guilds:
                config = self.bot.get_guild_config_cached(guild.id)
                if not config or not config.get('enabled', False):
                    continue
                
                tag_to_watch = config.get('tag_to_watch')
                role_ids = config.get('role_ids', [])
                
                if not tag_to_watch or not role_ids:
                    continue
                
                # Traiter par batch pour économiser les ressources
                current_members_with_tag = set()
                
                # Utiliser chunk_guild pour charger les membres progressivement
                async for member in guild.fetch_members(limit=None):
                    if self._member_has_tag(member, tag_to_watch):
                        current_members_with_tag.add(member.id)
                        await self._update_member_roles(member, True, role_ids)
                    else:
                        # Vérifier si le membre avait le tag avant
                        if guild.id in self.member_cache and member.id in self.member_cache[guild.id]:
                            await self._update_member_roles(member, False, role_ids)
                    
                    # Petite pause pour ne pas surcharger
                    await asyncio.sleep(0.1)
                
                # Mettre à jour le cache
                self.member_cache[guild.id] = current_members_with_tag
                
        except Exception as e:
            logger.error(f"Error in check_tags: {e}")
        finally:
            self.processing = False
    
    @check_tags.before_loop
    async def before_check_tags(self):
        """Attendre que le bot soit prêt avant de démarrer la tâche"""
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(TagMonitor(bot))