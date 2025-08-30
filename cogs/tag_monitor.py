import discord
from discord.ext import commands, tasks
import asyncio
from typing import Set, Optional

class TagMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.processing = False
        self.member_cache: dict[int, Set[int]] = {}  # guild_id -> set of member_ids with tag
        
    async def cog_load(self):
        """Démarrer la surveillance après le chargement du cog"""
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
        config = self.bot.get_guild_config(after.guild.id)
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
            await self._update_member_roles(after, after_has_tag, role_ids)
    
    def _member_has_tag(self, member: discord.Member, tag: str) -> bool:
        """Vérifier si un membre a le tag spécifié"""
        if not member.guild_avatar:
            return False
            
        # Discord stocke les tags dans la description de l'avatar de serveur
        # ou dans le statut personnalisé
        member_tag = getattr(member, 'guild_avatar_decoration', None)
        if member_tag and tag.lower() in str(member_tag).lower():
            return True
            
        # Vérifier aussi dans le nom d'affichage
        if member.display_name and tag.lower() in member.display_name.lower():
            return True
            
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
                except discord.HTTPException as e:
                    print(f"Erreur lors du retrait du rôle {role.name} à {member}: {e}")
        
        # Ajouter les rôles en une seule fois
        if should_have_roles and roles_to_update:
            try:
                await member.add_roles(*roles_to_update, reason="Tag de serveur détecté")
            except discord.HTTPException as e:
                print(f"Erreur lors de l'ajout des rôles à {member}: {e}")
    
    @tasks.loop(minutes=5)  # Vérification toutes les 5 minutes pour économiser les ressources
    async def check_tags(self):
        """Tâche périodique pour vérifier les tags (backup au cas où les événements sont manqués)"""
        if self.processing:
            return
            
        self.processing = True
        try:
            for guild in self.bot.guilds:
                config = self.bot.get_guild_config(guild.id)
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
            print(f"Erreur dans check_tags: {e}")
        finally:
            self.processing = False
    
    @check_tags.before_loop
    async def before_check_tags(self):
        """Attendre que le bot soit prêt avant de démarrer la tâche"""
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(TagMonitor(bot))