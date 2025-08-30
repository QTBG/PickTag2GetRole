import discord
from discord import app_commands
from discord.ext import commands
from typing import List

class ConfigCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="config", description="Configurer le bot pour surveiller un tag")
    @app_commands.describe(
        tag="Le tag de serveur à surveiller",
        roles="Les rôles à attribuer (mentionner les rôles séparés par des espaces)"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def config(self, interaction: discord.Interaction, tag: str, roles: str):
        """Configurer le tag à surveiller et les rôles à attribuer"""
        # Vérifier les permissions
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ Vous devez avoir la permission de gérer les rôles pour utiliser cette commande.",
                ephemeral=True
            )
            return
        
        # Parser les rôles mentionnés
        role_mentions = roles.split()
        role_ids = []
        role_names = []
        
        for mention in role_mentions:
            # Extraire l'ID du rôle depuis la mention
            if mention.startswith('<@&') and mention.endswith('>'):
                role_id = int(mention[3:-1])
                role = interaction.guild.get_role(role_id)
                if role:
                    role_ids.append(role_id)
                    role_names.append(role.name)
        
        if not role_ids:
            await interaction.response.send_message(
                "❌ Aucun rôle valide trouvé. Veuillez mentionner les rôles avec @.",
                ephemeral=True
            )
            return
        
        # Sauvegarder la configuration
        config = {
            'tag_to_watch': tag,
            'role_ids': role_ids,
            'enabled': True
        }
        
        await self.bot.set_guild_config(interaction.guild.id, config)
        
        # Réponse
        embed = discord.Embed(
            title="✅ Configuration mise à jour",
            color=discord.Color.green(),
            description=f"Le bot surveillera maintenant le tag **{tag}**"
        )
        embed.add_field(
            name="Rôles à attribuer",
            value="\n".join([f"• {name}" for name in role_names]),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="status", description="Voir la configuration actuelle du bot")
    @app_commands.default_permissions(manage_roles=True)
    async def status(self, interaction: discord.Interaction):
        """Afficher la configuration actuelle"""
        config = self.bot.get_guild_config(interaction.guild.id)
        
        if not config:
            await interaction.response.send_message(
                "❌ Aucune configuration trouvée pour ce serveur. Utilisez `/config` pour configurer le bot.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📊 Configuration actuelle",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Tag surveillé",
            value=config.get('tag_to_watch', 'Non défini'),
            inline=False
        )
        
        role_ids = config.get('role_ids', [])
        if role_ids:
            role_names = []
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_names.append(role.name)
                else:
                    role_names.append(f"Rôle supprimé (ID: {role_id})")
            
            embed.add_field(
                name="Rôles attribués",
                value="\n".join([f"• {name}" for name in role_names]),
                inline=False
            )
        else:
            embed.add_field(name="Rôles", value="Aucun rôle configuré", inline=False)
        
        embed.add_field(
            name="État",
            value="✅ Activé" if config.get('enabled', False) else "❌ Désactivé",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="toggle", description="Activer ou désactiver la surveillance des tags")
    @app_commands.default_permissions(manage_roles=True)
    async def toggle(self, interaction: discord.Interaction):
        """Activer/désactiver le bot pour ce serveur"""
        config = self.bot.get_guild_config(interaction.guild.id)
        
        if not config:
            await interaction.response.send_message(
                "❌ Aucune configuration trouvée. Utilisez `/config` d'abord.",
                ephemeral=True
            )
            return
        
        # Inverser l'état
        config['enabled'] = not config.get('enabled', False)
        await self.bot.set_guild_config(interaction.guild.id, config)
        
        status = "✅ activée" if config['enabled'] else "❌ désactivée"
        await interaction.response.send_message(
            f"La surveillance des tags a été {status}.",
            ephemeral=True
        )
    
    @app_commands.command(name="scan", description="Scanner manuellement tous les membres maintenant")
    @app_commands.default_permissions(manage_roles=True)
    async def scan(self, interaction: discord.Interaction):
        """Forcer un scan immédiat de tous les membres"""
        config = self.bot.get_guild_config(interaction.guild.id)
        
        if not config or not config.get('enabled', False):
            await interaction.response.send_message(
                "❌ Le bot n'est pas activé pour ce serveur. Utilisez `/toggle` pour l'activer.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        tag_to_watch = config.get('tag_to_watch')
        role_ids = config.get('role_ids', [])
        
        if not tag_to_watch or not role_ids:
            await interaction.followup.send(
                "❌ Configuration incomplète. Veuillez reconfigurer avec `/config`.",
                ephemeral=True
            )
            return
        
        # Obtenir le cog TagMonitor
        tag_monitor = self.bot.get_cog('TagMonitor')
        if not tag_monitor:
            await interaction.followup.send(
                "❌ Module de surveillance non chargé.",
                ephemeral=True
            )
            return
        
        # Scanner tous les membres
        members_updated = 0
        total_members = 0
        
        async for member in interaction.guild.fetch_members(limit=None):
            total_members += 1
            has_tag = tag_monitor._member_has_tag(member, tag_to_watch)
            
            # Vérifier si le membre doit avoir les rôles
            needs_update = False
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    has_role = role in member.roles
                    if has_tag and not has_role:
                        needs_update = True
                    elif not has_tag and has_role:
                        needs_update = True
            
            if needs_update:
                await tag_monitor._update_member_roles(member, has_tag, role_ids)
                members_updated += 1
        
        embed = discord.Embed(
            title="✅ Scan terminé",
            color=discord.Color.green(),
            description=f"**{total_members}** membres scannés\n**{members_updated}** membres mis à jour"
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ConfigCommands(bot))