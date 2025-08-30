import discord
from discord import app_commands
from discord.ext import commands
from typing import List
import logging

logger = logging.getLogger('PickTag2GetRole.Commands')

class ConfigCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="config", description="Configure the bot to monitor a server tag")
    @app_commands.describe(
        tag="The server tag to monitor",
        roles="Roles to assign (mention roles separated by spaces)"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def config(self, interaction: discord.Interaction, tag: str, roles: str):
        """Configure the tag to monitor and roles to assign"""
        # Vérifier les permissions
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ You must have the Manage Roles permission to use this command.",
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
                "❌ No valid roles found. Please mention roles with @.",
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
            title="✅ Configuration updated",
            color=discord.Color.green(),
            description=f"The bot will now monitor the tag **{tag}**"
        )
        embed.add_field(
            name="Roles to assign",
            value="\n".join([f"• {name}" for name in role_names]),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="status", description="View the current bot configuration")
    @app_commands.default_permissions(manage_roles=True)
    async def status(self, interaction: discord.Interaction):
        """Display current configuration"""
        config = await self.bot.get_guild_config(interaction.guild.id)
        
        if not config:
            await interaction.response.send_message(
                "❌ No configuration found for this server. Use `/config` to configure the bot.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📊 Current configuration",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Monitored tag",
            value=config.get('tag_to_watch', 'Not set'),
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
                    role_names.append(f"Deleted role (ID: {role_id})")
            
            embed.add_field(
                name="Assigned roles",
                value="\n".join([f"• {name}" for name in role_names]),
                inline=False
            )
        else:
            embed.add_field(name="Roles", value="No roles configured", inline=False)
        
        embed.add_field(
            name="Status",
            value="✅ Enabled" if config.get('enabled', False) else "❌ Disabled",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="toggle", description="Enable or disable tag monitoring")
    @app_commands.default_permissions(manage_roles=True)
    async def toggle(self, interaction: discord.Interaction):
        """Enable/disable the bot for this server"""
        config = await self.bot.get_guild_config(interaction.guild.id)
        
        if not config:
            await interaction.response.send_message(
                "❌ No configuration found. Use `/config` first.",
                ephemeral=True
            )
            return
        
        # Inverser l'état
        config['enabled'] = not config.get('enabled', False)
        await self.bot.set_guild_config(interaction.guild.id, config)
        
        status = "✅ enabled" if config['enabled'] else "❌ disabled"
        await interaction.response.send_message(
            f"Tag monitoring has been {status}.",
            ephemeral=True
        )
    
    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        """Display help for all commands"""
        embed = discord.Embed(
            title="📚 PickTag2GetRole - Commands",
            description="Here are all available commands:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="/config `tag` `@role1 @role2...`",
            value="Configure the bot to monitor a specific server tag and assign roles to members who have it.",
            inline=False
        )
        
        embed.add_field(
            name="/status",
            value="View the current configuration (monitored tag, assigned roles, enabled/disabled status).",
            inline=False
        )
        
        embed.add_field(
            name="/toggle",
            value="Enable or disable tag monitoring for this server.",
            inline=False
        )
        
        embed.add_field(
            name="/scan",
            value="Manually scan all server members and update their roles based on the current configuration.",
            inline=False
        )
        
        embed.add_field(
            name="/check `@member`",
            value="Check a specific member's tag status and see if they should have the configured roles.",
            inline=False
        )
        
        embed.add_field(
            name="/help",
            value="Show this help message.",
            inline=False
        )
        
        embed.set_footer(text="Note: Most commands require the 'Manage Roles' permission.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="scan", description="Manually scan all members now")
    @app_commands.default_permissions(manage_roles=True)
    async def scan(self, interaction: discord.Interaction):
        """Force an immediate scan of all members"""
        config = await self.bot.get_guild_config(interaction.guild.id)
        
        if not config or not config.get('enabled', False):
            await interaction.response.send_message(
                "❌ The bot is not enabled for this server. Use `/toggle` to enable it.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        tag_to_watch = config.get('tag_to_watch')
        role_ids = config.get('role_ids', [])
        
        if not tag_to_watch or not role_ids:
            await interaction.followup.send(
                "❌ Incomplete configuration. Please reconfigure with `/config`.",
                ephemeral=True
            )
            return
        
        # Obtenir le cog TagMonitor
        tag_monitor = self.bot.get_cog('TagMonitor')
        if not tag_monitor:
            await interaction.followup.send(
                "❌ Monitoring module not loaded.",
                ephemeral=True
            )
            return
        
        # Scanner tous les membres
        members_updated = 0
        total_members = 0
        members_with_tag = 0
        
        logger.info(f"Starting scan for tag: {tag_to_watch}")
        
        async for member in interaction.guild.fetch_members(limit=None):
            total_members += 1
            has_tag = tag_monitor._member_has_tag(member, tag_to_watch)
            
            if has_tag:
                members_with_tag += 1
            
            # Vérifier si le membre doit avoir les rôles
            needs_update = False
            roles_to_add = []
            roles_to_remove = []
            
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    has_role = role in member.roles
                    if has_tag and not has_role:
                        needs_update = True
                        roles_to_add.append(role.name)
                    elif not has_tag and has_role:
                        needs_update = True
                        roles_to_remove.append(role.name)
            
            if needs_update:
                await tag_monitor._update_member_roles(member, has_tag, role_ids)
                members_updated += 1
        
        embed = discord.Embed(
            title="✅ Scan completed",
            color=discord.Color.green(),
            description=f"**{total_members}** members scanned\n**{members_with_tag}** members with tag '{tag_to_watch}'\n**{members_updated}** members updated"
        )
        
        logger.info(f"Scan completed: {total_members} scanned, {members_with_tag} with tag, {members_updated} updated")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="check", description="Check a specific member's tag status")
    @app_commands.describe(member="The member to check")
    @app_commands.default_permissions(manage_roles=True)
    async def check_member(self, interaction: discord.Interaction, member: discord.Member):
        """Check if a specific member has the configured tag"""
        config = await self.bot.get_guild_config(interaction.guild.id)
        
        if not config:
            await interaction.response.send_message(
                "❌ No configuration found for this server.",
                ephemeral=True
            )
            return
        
        tag_to_watch = config.get('tag_to_watch', 'Not configured')
        
        embed = discord.Embed(
            title=f"🔍 Tag check for {member.name}",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Looking for tag", value=tag_to_watch, inline=False)
        
        # Vérifier primary_guild
        if hasattr(member, 'primary_guild'):
            pg = member.primary_guild
            if pg:
                embed.add_field(name="Primary Guild ID", value=pg.id or "None", inline=True)
                embed.add_field(name="Primary Guild Tag", value=pg.tag or "None", inline=True)
                embed.add_field(name="Identity Enabled", value=str(pg.identity_enabled), inline=True)
                
                # Vérifier si le tag correspond
                tag_monitor = self.bot.get_cog('TagMonitor')
                if tag_monitor and tag_to_watch != 'Not configured':
                    has_tag = tag_monitor._member_has_tag(member, tag_to_watch)
                    embed.add_field(name="Has matching tag?", value="✅ Yes" if has_tag else "❌ No", inline=False)
            else:
                embed.add_field(name="Primary Guild", value="None", inline=False)
        else:
            embed.add_field(name="Error", value="Primary guild attribute not found. Check discord.py version.", inline=False)
        
        # Afficher les rôles actuels
        role_ids = config.get('role_ids', [])
        if role_ids:
            assigned_roles = []
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role and role in member.roles:
                    assigned_roles.append(role.name)
            
            embed.add_field(
                name="Currently has configured roles",
                value=", ".join(assigned_roles) if assigned_roles else "None",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ConfigCommands(bot))